"""API process: `uvicorn app.main:app --port 4000 --proxy-headers`. Background work runs in `app.worker`."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import capabilities, detect_capabilities, engine
from app.errors import install_error_handlers
from app.logging_setup import setup_logging
from app.middleware.request_context import RequestContextMiddleware
from app.routes import admin, auth, canvases, chat, health, inbound, items, public, reminders, uploads, users
from app.services.admin import seed_admin

log = logging.getLogger("stash.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(settings.log_level)
    await detect_capabilities()
    try:
        await seed_admin()
    except Exception:
        log.exception("admin account could not be seeded")
    log.info("api started", extra={"env": settings.app_env, "vector": capabilities.vector,
                                   "chat": settings.chat_ai_configured, "moderator": settings.moderation_model_enabled})
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    docs = None if settings.is_production else "/api/docs"
    app = FastAPI(title="Stash API", version="1.0.0", lifespan=lifespan, docs_url=docs, redoc_url=None,
                  openapi_url=None if settings.is_production else "/api/openapi.json")
    install_error_handlers(app)
    for module in (health, auth, users, canvases, items, uploads, reminders, chat, public, inbound, admin):
        app.include_router(module.router, prefix="/api/v1")
    app.add_middleware(RequestContextMiddleware)
    return app


app = create_app()
