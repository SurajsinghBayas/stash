"""Chat over the user's own cards, streamed as server-sent events.

Events: `status` {stage}, `sources` [cards], `delta` {text}, `blocked` {message}, `error` {code, message},
`done` {message_id, cited}. Everything that can fail before the model runs is answered as a normal JSON error.
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.models import ChatMessage, ModerationEvent, User
from app.db import SessionLocal, get_session
from app.errors import AppError, ValidationFailed
from app.middleware.auth import current_user
from app.middleware.rate_limit import limiter
from app.schemas import ChatIn, data
from app.services.agents.chat import OUTPUT_BLOCKED, Ask, Conversation, _OutputBlocked
from app.services.ai import client as ai
from app.services.items import service as items
from app.services.safety.service import SafetyUnavailable, check_text
from app.services.usage import require_allowance

log = logging.getLogger("stash.chat")
router = APIRouter(tags=["chat"])

BLOCKED_REPLY = "I can't help with that."
STRIKES, STRIKE_WINDOW, COOLDOWN = 3, timedelta(hours=24), timedelta(hours=1)


def _sse(event: str, payload) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


async def _record_block(session: AsyncSession, user_id: uuid.UUID, source: str, categories: list[str],
                        request_id: str | None) -> None:
    session.add(ModerationEvent(user_id=user_id, source=source, action="blocked", categories=categories,
                                request_id=request_id))
    if source == "chat_input":
        await session.flush()
        recent = await session.scalar(
            select(func.count()).select_from(ModerationEvent)
            .where(ModerationEvent.user_id == user_id, ModerationEvent.source == "chat_input",
                   ModerationEvent.created_at >= datetime.now(UTC) - STRIKE_WINDOW)
        )
        if recent >= STRIKES:
            await session.execute(text("update users set chat_blocked_until = :t where id = :u"),
                                  {"t": datetime.now(UTC) + COOLDOWN, "u": user_id})
    await session.commit()


@router.post("/chat")
async def chat(body: ChatIn, request: Request, user: User = Depends(current_user),
               session: AsyncSession = Depends(get_session)):
    request_id = getattr(request.state, "request_id", None)
    if not settings.ai_enabled or not settings.chat_ai_configured:
        raise AppError("The assistant is turned off right now.", code="ai_disabled", status=503)
    if user.chat_blocked_until and user.chat_blocked_until > datetime.now(UTC):
        wait = int((user.chat_blocked_until - datetime.now(UTC)).total_seconds()) + 1
        raise AppError("Chat is paused for a while after several blocked messages.", code="chat_paused",
                       status=429, headers={"Retry-After": str(wait)})
    limiter.hit(f"chat:user:{user.id}", settings.chat_requests_per_hour, 3600)
    await require_allowance(session, user.id)
    canvas_id = None
    if body.scope == "canvas":
        if not body.canvas_id:
            raise ValidationFailed("canvas_id: required when scope is canvas")
        canvas_id = (await items.get_canvas(session, user.id, body.canvas_id)).id

    # Input guardrail. SafetyUnavailable propagates as 503: an unchecked question is never sent anywhere.
    verdict = await check_text(body.question, "input")
    user_id = user.id
    memory_on = bool(user.memory_enabled and settings.memory_enabled)
    await session.commit()  # end the read transaction before streaming

    async def blocked() -> AsyncIterator[bytes]:
        async with SessionLocal() as s:
            await _record_block(s, user_id, "chat_input", verdict.categories, request_id)
        yield _sse("blocked", {"message": BLOCKED_REPLY})
        yield _sse("done", {"message_id": None, "cited": []})

    async def answer() -> AsyncIterator[bytes]:
        async with SessionLocal() as s:
            conv = Conversation(s, Ask(
                user_id=user_id, question=verdict.safe, scope=body.scope, canvas_id=canvas_id,
                request_id=request_id, memory_on=memory_on,
            ))
            try:
                async for event, payload in conv.stream():
                    yield _sse(event, payload)
            except _OutputBlocked as exc:
                conv.result.outcome = "blocked_output"
                conv.result.final, conv.result.cited = OUTPUT_BLOCKED, []
                await _record_block(s, user_id, "chat_output", exc.categories, request_id)
                yield _sse("blocked", {"message": OUTPUT_BLOCKED})
            except (ai.AIUnavailable, SafetyUnavailable) as exc:
                conv.result.outcome = "provider_error"
                log.warning("chat failed", extra={"error": type(exc).__name__, "request_id": request_id})
                yield _sse("error", {"code": exc.code, "message": exc.message})
            await conv.save()
            yield _sse("done", {"message_id": conv.result.message_id,
                                "cited": [str(i) for i in conv.result.cited]})

    headers = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    stream = answer() if verdict.ok else blocked()
    return StreamingResponse(stream, media_type="text/event-stream", headers=headers)


@router.get("/chat/history")
async def history(canvas_id: uuid.UUID | None = None, limit: int = Query(30, ge=1, le=100),
                  user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if canvas_id:
        await items.get_canvas(session, user.id, canvas_id)
    rows = list(await session.scalars(
        select(ChatMessage).where(ChatMessage.user_id == user.id, ChatMessage.canvas_id == canvas_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit)
    ))[::-1]
    return data([{"id": r.id, "role": r.role, "content": r.content, "cited": [str(i) for i in r.cited_items],
                  "created_at": r.created_at.isoformat()} for r in rows])


@router.delete("/chat/history", status_code=204)
async def clear_history(canvas_id: uuid.UUID | None = None, user: User = Depends(current_user),
                        session: AsyncSession = Depends(get_session)):
    await session.execute(delete(ChatMessage).where(ChatMessage.user_id == user.id,
                                                    ChatMessage.canvas_id == canvas_id))
    await session.commit()

