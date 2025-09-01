import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.api.routers import webhook as webhook_router
from app.main import app
from app.config import get_settings
from app.integrations.clickup_client import ClickUpClient


# ----------------------------
# Shared in-memory engine for this test module
# ----------------------------
@pytest.fixture(scope="module")
def test_engine():
    """
    One in-memory SQLite database shared across threads:
    - StaticPool: reuse the SAME connection
    - check_same_thread=False: allow access from TestClient thread
    """
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create schema once
    Base.metadata.create_all(bind=engine)
    yield engine
    # (optional) engine.dispose()


@pytest.fixture(autouse=True)
def configure_settings_and_disable_clickup(monkeypatch):
    """
    - Set a known shared secret for the webhook.
    - Ensure ClickUp integration is a no-op during tests.
    """
    settings = get_settings()
    settings.FORM_SHARED_SECRET = "testsecret"

    class _FakeClient:
        def is_configured(self) -> bool:
            return False

    monkeypatch.setattr(ClickUpClient, "from_settings", classmethod(lambda cls: _FakeClient()))
    yield


@pytest.fixture()
def client(test_engine):
    """
    Build a TestClient and override the webhook's DB dependency
    to yield sessions bound to the shared in-memory engine.
    """
    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Override only the webhook router's get_db
    app.dependency_overrides[webhook_router.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    # Clean up overrides
    app.dependency_overrides.pop(webhook_router.get_db, None)


# ----------------------------
# Helpers
# ----------------------------
def _payload(email: str) -> dict:
    return {
        "nombre": "Roman Riquelme",
        "correo": email,
        "telefono": "+57 899898998",
        "intereses_servicios": ["diseño", "riego"],
        "mensaje": "Proyecto de jardín frontal",
    }


# ----------------------------
# Tests
# ----------------------------
def test_webhook_creates_lead_returns_201(client: TestClient):
    resp = client.post(
        "/api/form/webhook",
        headers={"X-Form-Secret": "testsecret"},
        json=_payload("test1@example.com"),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["correo"] == "test1@example.com"
    assert body["nombre"] == "Roman Riquelme"
    assert body["intereses_servicios"] == ["diseño", "riego"]


def test_webhook_duplicate_returns_200_same_id(client: TestClient):
    first = client.post(
        "/api/form/webhook",
        headers={"X-Form-Secret": "testsecret"},
        json=_payload("dup@example.com"),
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.post(
        "/api/form/webhook",
        headers={"X-Form-Secret": "testsecret"},
        json=_payload("dup@example.com"),
    )
    assert second.status_code == 200
    assert second.json()["id"] == first_id


def test_webhook_unauthorized_without_secret(client: TestClient):
    resp = client.post(
        "/api/form/webhook",
        json=_payload("noauth@example.com"),
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Unauthorized"


def test_webhook_unauthorized_with_wrong_secret(client: TestClient):
    resp = client.post(
        "/api/form/webhook",
        headers={"X-Form-Secret": "wrong"},
        json=_payload("wrongsec@example.com"),
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Unauthorized"
