# app/api/routers/health.py
from fastapi import APIRouter
import structlog

from app.config import get_settings

router = APIRouter()
log = structlog.get_logger()

@router.get("/health")
def health():
    settings = get_settings()
    log.info("health_check", env=settings.APP_ENV)
    return {"status": "ok", "env": settings.APP_ENV}
