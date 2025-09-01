from fastapi import APIRouter, Depends, Header, HTTPException, status, Response
from sqlalchemy.orm import Session
import structlog
import time
from typing import Optional

from app.config import get_settings
from app.db.session import SessionLocal
from app.schemas.lead import LeadCreate, LeadResponse
from app.services import lead_service


router = APIRouter()
log = structlog.get_logger()
settings = get_settings()

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post(
    "/api/form/webhook",
    response_model=LeadResponse,
    summary="Recibe el webhook de Google Forms (Apps Script) con datos del lead",
)
def receive_webhook(
    payload: LeadCreate,
    response: Response,
    x_form_secret: Optional[str] = Header(default=None, alias="X-Form-Secret"),
    db: Session = Depends(get_db),
):
    t0 = time.perf_counter()
    log.info("webhook_received", has_secret=bool(x_form_secret))

    if not settings.FORM_SHARED_SECRET or x_form_secret != settings.FORM_SHARED_SECRET:
        log.warning("webhook_unauthorized", reason="missing_or_invalid_secret")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    normalized = LeadCreate(
        nombre=payload.nombre.strip(),
        correo=str(payload.correo).strip().lower(),
        telefono=payload.telefono.strip() if payload.telefono else None,
        intereses_servicios=[s.strip() for s in (payload.intereses_servicios or [])],
        mensaje=payload.mensaje.strip() if payload.mensaje else None,
    )

    lead_obj, created = lead_service.create_or_get_lead(db=db, data=normalized)
    log.info("webhook_payload_normalized", correo=normalized.correo, intereses=normalized.intereses_servicios)

    # Pydantic v2 + FastAPI encoder will handle datetimes if we return the model
    resp = LeadResponse.model_validate(lead_obj)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if created:
        response.status_code = status.HTTP_201_CREATED
        log.info("lead_persisted", lead_id=lead_obj.id, status_api=response.status_code, elapsed_ms=elapsed_ms)
    else:
        response.status_code = status.HTTP_200_OK
        log.info("lead_existing", lead_id=lead_obj.id, status_api=response.status_code, elapsed_ms=elapsed_ms)

    return resp
