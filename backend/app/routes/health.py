from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import capabilities, engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Liveness: the process answers. No dependencies, so a database blip does not restart the app."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready():
    """Readiness: the database answers. Feature flags show what this instance can do; no secrets."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        db = "ok"
    except Exception:
        db = "down"
    body = {
        "status": "ok" if db == "ok" else "degraded",
        "database": db,
        "features": {
            "vector_search": capabilities.vector,
            "chat": settings.chat_ai_configured,
            "embeddings": settings.embeddings_configured,
            "guardrail": settings.guardrail_configured,
            "mail": settings.mail_enabled,
        },
    }
    return JSONResponse(body, status_code=200 if db == "ok" else 503)
