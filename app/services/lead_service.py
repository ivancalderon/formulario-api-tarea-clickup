from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
from typing import Tuple

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session

from app.db.models import Lead
from app.schemas.lead import LeadCreate
from app.config import get_settings
from app.integrations.clickup_client import ClickUpClient, ClickUpError

log = structlog.get_logger()


def _generate_dedupe_key(data: LeadCreate) -> str:
    """
    Simple, deterministic key to avoid duplicates caused by webhook retries.
    Strategy: hash of (correo lowercase) + (UTC date YYYYMMDD) + (nombre trimmed).
    """
    correo = str(data.correo).strip().lower()
    nombre = data.nombre.strip()
    yyyymmdd = datetime.utcnow().strftime("%Y%m%d")
    raw = f"{correo}|{yyyymmdd}|{nombre}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _subtasks_from_env() -> list[str]:
    s = get_settings()
    raw = (s.SUBTASKS or "").strip()
    if not raw:
        return [
            "Contactar lead (24h)",
            "Enviar información",
            "Proponer 3 horarios",
            "Agendar reunión inicial",
        ]
    return [part.strip() for part in raw.split(";") if part.strip()]


def create_or_get_lead(db: Session, data: LeadCreate) -> Tuple[Lead, bool]:
    """
    Persist a lead if it's new; if the same payload (per dedupe key) arrives again,
    return the existing record instead (idempotent behavior).

    Returns:
        (lead_obj, created_bool)
    """
    dedupe_key = _generate_dedupe_key(data)

    # Try to create a new row
    lead = Lead(
        nombre=data.nombre,
        correo=str(data.correo).lower(),
        telefono=data.telefono,
        mensaje=data.mensaje,
        dedupe_key=dedupe_key,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    # Use the convenience property to serialize JSON under the hood
    lead.intereses_servicios = list(data.intereses_servicios or [])

    db.add(lead)
    try:
        db.commit()
        db.refresh(lead)
        log.info("lead_created", lead_id=lead.id)
        created = True
    except IntegrityError:
        # Unique constraint hit → fetch the existing row and return it
        db.rollback()
        stmt = select(Lead).where(Lead.dedupe_key == dedupe_key).limit(1)
        existing = db.execute(stmt).scalar_one_or_none()
        if existing:
            log.info("lead_duplicate_returning_existing", lead_id=existing.id)
            return existing, False

        # Extremely rare edge-case: unique error but row not found; fall back by correo (latest)
        stmt_fallback = (
            select(Lead)
            .where(Lead.correo == str(data.correo).lower())
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        fallback = db.execute(stmt_fallback).scalar_one_or_none()
        if fallback:
            log.warning("lead_duplicate_fallback_by_email", lead_id=fallback.id)
            return fallback, False

        # If we genuinely can't find it, re-raise to surface the failure
        raise

    # If created now, optionally create ClickUp tasks
    if created:
        _maybe_create_clickup_items(lead, data)

    return lead, created


def _maybe_create_clickup_items(lead: Lead, data: LeadCreate) -> None:
    """
    Create a parent task and subtasks in ClickUp.
    - If ClickUp is not configured, skip and log.
    - If API calls fail after retries, log an error; do not raise (lead already stored).
    """
    client = ClickUpClient.from_settings()
    if not client.is_configured():
        log.info("tm_skipped", reason="missing_token_or_list_id")
        return

    # Parent task content
    intereses = ", ".join(lead.intereses_servicios) if lead.intereses_servicios else "-"
    descripcion = (
        f"**Nombre:** {lead.nombre}\n"
        f"**Correo:** {lead.correo}\n"
        f"**Teléfono:** {lead.telefono or '-'}\n"
        f"**Intereses:** {intereses}\n"
        f"**Mensaje:** {lead.mensaje or '-'}\n"
    )
    task_name = f"Nuevo lead: {lead.nombre}"

    try:
        parent = client.create_task(name=task_name, description=descripcion)
        if parent.get("skipped"):
            # Config missing; nothing else to do.
            log.info("tm_skipped", reason="missing_token_or_list_id")
            return

        parent_id = parent.get("id")
        log.info("tm_task_created", parent_id=parent_id)

        # Subtasks
        subtasks = _subtasks_from_env()
        sub_ids: list[str] = []
        # First subtask due in 24h
        due_ms = _epoch_ms(datetime.now(timezone.utc) + timedelta(hours=24)) if subtasks else None

        for idx, title in enumerate(subtasks):
            if idx == 0:
                sub = client.create_subtask(parent_task_id=parent_id, name=title, due_date_ms=due_ms)
            else:
                sub = client.create_subtask(parent_task_id=parent_id, name=title)
            sid = str(sub.get("id") or "")
            sub_ids.append(sid)
            log.info("tm_subtask_created", parent_id=parent_id, subtask_id=sub.get("id"), title=title)
    
        # --- Persist IDs on the same Lead row ---
        sess = object_session(lead)
        if not sess:
            log.warning("tm_persist_ids_no_session", lead_id=lead.id)
            return

        lead.external_task_id = parent_id
        lead.external_subtask_ids = sub_ids  # property writes JSON under the hood

        sess.add(lead)
        sess.commit()
        sess.refresh(lead)
        log.info("tm_persisted_ids", lead_id=lead.id, parent_id=parent_id, count=len(sub_ids))

    except ClickUpError as e:
        log.error("tm_error", error=str(e))
    except Exception as e:
        # Catch-all to ensure webhook continues even if ClickUp payload changes
        log.exception("tm_unexpected_error", error=str(e))
