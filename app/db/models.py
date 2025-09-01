from datetime import datetime
import json
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.db.session import Base


class Lead(Base):
    __tablename__ = "leads"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Challenge fields (Spanish)
    nombre = Column(String(200), nullable=False)
    correo = Column(String(320), nullable=False, index=True)  # index for quick lookup by email
    telefono = Column(String(50), nullable=True)
    # Store as JSON text for portability (SQLite doesn't have native JSON type)
    intereses_servicios_json = Column("intereses_servicios", Text, nullable=False)
    mensaje = Column(Text, nullable=True)

    # Idempotency key (unique to avoid duplicates on webhook retries)
    dedupe_key = Column(String(128), nullable=False, unique=True)

    # --- NEW: ClickUp persistence ---
    external_task_id = Column(String(64), nullable=True)
    external_subtask_ids_json = Column("external_subtask_ids", Text, nullable=True)

    external_task_url = Column(Text, nullable=True)
    status_api = Column(Integer, nullable=True)

    # Convenience property: expose intereses_servicios as a Python list
    @property
    def intereses_servicios(self) -> list[str]:
        try:
            return json.loads(self.intereses_servicios_json) if self.intereses_servicios_json else []
        except json.JSONDecodeError:
            return []

    @intereses_servicios.setter
    def intereses_servicios(self, value: list[str]) -> None:
        self.intereses_servicios_json = json.dumps(value or [])


    # Convenience property: expose external_subtask_ids as list[str]
    @property
    def external_subtask_ids(self) -> list[str]:
        try:
            return json.loads(self.external_subtask_ids_json) if self.external_subtask_ids_json else []
        except json.JSONDecodeError:
            return []

    @external_subtask_ids.setter
    def external_subtask_ids(self, value: list[str]) -> None:
        self.external_subtask_ids_json = json.dumps(value or [])
