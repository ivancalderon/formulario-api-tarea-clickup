import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import Lead
from app.schemas.lead import LeadCreate
from app.services import lead_service
from app.integrations.clickup_client import ClickUpClient


# ---------- Fixtures: in-memory DB session ----------
@pytest.fixture()
def db_session():
    # In-memory SQLite for fast, isolated tests
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True
    )

    # Create tables
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Fixture: disable ClickUp calls ----------
@pytest.fixture(autouse=True)
def disable_clickup(monkeypatch):
    """
    Ensure tests never hit ClickUp. We replace ClickUpClient.from_settings()
    with a version that returns a fake client whose is_configured() is False,
    causing the integration path to no-op.
    """

    class _FakeClient:
        def is_configured(self) -> bool:
            return False

    monkeypatch.setattr(ClickUpClient, "from_settings", classmethod(lambda cls: _FakeClient()))
    yield


# ---------- Helpers ----------
def _make_payload(
    nombre="Jose Guerrero",
    correo="jose@ejemplo.com",
    telefono="+593 3131313",
    intereses=None,
    mensaje="Siembra de palmeras y sistema de riego",
) -> LeadCreate:
    intereses = intereses or ["diseño", "riego"]
    return LeadCreate(
        nombre=nombre,
        correo=correo,
        telefono=telefono,
        intereses_servicios=intereses,
        mensaje=mensaje,
    )


# ---------- Tests ----------
def test_create_lead_returns_created_true(db_session):
    payload = _make_payload(correo="alice@example.com")
    lead_obj, created = lead_service.create_or_get_lead(db=db_session, data=payload)

    assert created is True
    assert isinstance(lead_obj.id, int)
    assert lead_obj.nombre == "Jose Guerrero"
    # Service lowercases email
    assert lead_obj.correo == "alice@example.com"
    # Round-trip intereses_servicios via property (JSON stored under the hood)
    assert lead_obj.intereses_servicios == ["diseño", "riego"]


def test_idempotent_duplicate_returns_existing_false(db_session):
    payload = _make_payload(correo="bob@example.com")

    first_obj, first_created = lead_service.create_or_get_lead(db=db_session, data=payload)
    second_obj, second_created = lead_service.create_or_get_lead(db=db_session, data=payload)

    assert first_created is True
    assert second_created is False
    # Same row returned (idempotency)
    assert second_obj.id == first_obj.id


def test_different_email_creates_new_row(db_session):
    p1 = _make_payload(correo="charlie@example.com")
    p2 = _make_payload(correo="dave@example.com")

    lead1, created1 = lead_service.create_or_get_lead(db=db_session, data=p1)
    lead2, created2 = lead_service.create_or_get_lead(db=db_session, data=p2)

    assert created1 is True
    assert created2 is True
    assert lead1.id != lead2.id


def test_intereses_servicios_roundtrip(db_session):
    payload = _make_payload(intereses=["mantenimiento", "hardscaping"])
    lead_obj, created = lead_service.create_or_get_lead(db=db_session, data=payload)

    assert created is True
    # Stored as JSON internally, exposed as list via property
    assert lead_obj.intereses_servicios == ["mantenimiento", "hardscaping"]
