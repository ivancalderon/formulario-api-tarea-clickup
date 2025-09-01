from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4
import structlog
from contextlib import asynccontextmanager

from app.api.routers.health import router as health_router
from app.api.routers.webhook import router as webhook_router
from app.logging_config import configure_logging
from app.db.session import init_db, engine
from app.db.migrations import run_startup_migrations
from app.db import models



# Configure logging at import time (before app starts handling requests)
configure_logging()
log = structlog.get_logger()

class RequestContextLogMiddleware(BaseHTTPMiddleware):
    """Binds request/trace IDs to logs for each request."""
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        trace_id = str(uuid4())

        # Bind per-request context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=str(request.url.path),
        )

        log.info("request_start")
        try:
            response = await call_next(request)
            log.info("request_end", status_code=response.status_code)
            return response
        except Exception:
            log.exception("unhandled_exception")
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    init_db()  # creates tables if missing; no destructive changes
    run_startup_migrations(engine)
    log.info("app_started")
    yield
    # --- Shutdown ---
    log.info("app_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Formulario DB Clickup", lifespan=lifespan)

    # Middlewares
    app.add_middleware(RequestContextLogMiddleware)

    # Routers
    app.include_router(health_router, tags=["health"])
    app.include_router(webhook_router, tags=["webhook"])

    

    return app

app = create_app()
