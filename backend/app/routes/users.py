import json
import logging
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.models import Canvas, ChatMessage, Item, Memory, OAuthAccount, Reminder, User
from app.db import get_session
from app.errors import Forbidden, NotFound
from app.middleware.auth import ACCESS_COOKIE, REFRESH_COOKIE, current_user
from app.middleware.rate_limit import limit
from app.schemas import DeleteAccountIn, UserPatch, data
from app.services.auth import service as auth_service
from app.services.auth import tokens
from app.services.auth.passwords import verify_password
from app.services.uploads import images
from app.services.usage import snapshot
from app.services.users import user_out

router = APIRouter(tags=["users"])
log = logging.getLogger("stash.users")



@router.get("/users/me")
async def me(user: User = Depends(current_user)):
    return data(user_out(user))


@router.patch("/users/me")
async def update_me(body: UserPatch, user: User = Depends(current_user),
                    session: AsyncSession = Depends(get_session)):
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, field, value)
    session.add(user)
    await session.commit()
    return data(user_out(user))


@router.get("/users/me/usage")
async def usage(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return data(await snapshot(session, user.id))


@router.get("/users/me/storage")
async def storage(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    from app.config import settings

    used = await session.scalar(select(func.coalesce(func.sum(Item.bytes), 0))
                                .where(Item.owner_id == user.id, Item.deleted_at.is_(None)))
    return data({"used_bytes": int(used or 0), "quota_bytes": settings.user_storage_quota_mb * 1024 * 1024})


@router.get("/users/me/profile")
async def profile(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """Account overview for the profile page: how they sign in, and what they have in Stash."""
    providers = list(await session.scalars(
        select(OAuthAccount.provider).where(OAuthAccount.user_id == user.id).order_by(OAuthAccount.created_at)))
    canvases = await session.scalar(
        select(func.count()).select_from(Canvas).where(Canvas.owner_id == user.id, Canvas.deleted_at.is_(None)))
    kinds = dict((await session.execute(
        select(Item.kind, func.count()).join(Canvas, Canvas.id == Item.canvas_id)
        .where(Item.owner_id == user.id, Item.deleted_at.is_(None), Canvas.deleted_at.is_(None))
        .group_by(Item.kind))).all())
    upcoming = await session.scalar(
        select(func.count()).select_from(Reminder).where(Reminder.user_id == user.id, Reminder.state == "pending",
                                                         Reminder.remind_at > func.now()))
    questions = await session.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.user_id == user.id, ChatMessage.role == "user"))
    return data({
        "sign_in": {"password": bool(user.password_hash), "providers": sorted(set(providers))},
        "member_since": user.created_at,
        "counts": {"canvases": int(canvases or 0), "cards": int(sum(kinds.values())),
                   "by_kind": {k: int(v) for k, v in kinds.items()}, "upcoming_reminders": int(upcoming or 0),
                   "questions_asked": int(questions or 0)},
    })


def _memory_out(row: Memory) -> dict:
    return {"id": str(row.id), "fact": row.fact, "kind": row.kind, "created_at": row.created_at.isoformat()}


@router.get("/users/me/memories")
async def list_memories(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = list(await session.scalars(
        select(Memory).where(Memory.user_id == user.id).order_by(Memory.created_at.desc())))
    return data([_memory_out(row) for row in rows])


@router.delete("/users/me/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: uuid.UUID, user: User = Depends(current_user),
                        session: AsyncSession = Depends(get_session)):
    result = await session.execute(delete(Memory).where(Memory.id == memory_id, Memory.user_id == user.id))
    if not result.rowcount:
        raise NotFound("Memory not found")
    await session.commit()


@router.delete("/users/me/memories", status_code=204)
async def clear_memories(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await session.execute(delete(Memory).where(Memory.user_id == user.id))
    await session.commit()


@router.post("/users/me/logout-all", status_code=204)
async def logout_all(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await auth_service.logout_everywhere(session, user.id)


# ---------- your data ----------

def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@router.get("/users/me/export", dependencies=[Depends(limit("export", 5, 3600))])
async def export(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """Everything Stash stores about the account, as one JSON file. Image links work for an hour."""
    from app.services.uploads.storage import storage

    store = storage()
    canvases = list(await session.scalars(select(Canvas).where(Canvas.owner_id == user.id)
                                          .order_by(Canvas.created_at)))
    cards = list(await session.scalars(select(Item).where(Item.owner_id == user.id).order_by(Item.created_at)))
    out_cards = []
    for item in cards:
        content = {k: v for k, v in item.content.items() if k not in images.IMAGE_KEYS}
        if item.kind == "image" and item.content.get("storage_key") and item.content.get("upload_state") == "ready":
            content["download_url"] = await store.presign_get(item.content["storage_key"])
        out_cards.append({"id": str(item.id), "canvas_id": str(item.canvas_id), "kind": item.kind, "content": content,
                          "position": {"x": item.x, "y": item.y, "w": item.w, "h": item.h},
                          "created_at": _iso(item.created_at), "updated_at": _iso(item.updated_at),
                          "deleted_at": _iso(item.deleted_at)})
    reminders = await session.scalars(select(Reminder).where(Reminder.user_id == user.id)
                                      .order_by(Reminder.remind_at))
    memories = await session.scalars(select(Memory).where(Memory.user_id == user.id).order_by(Memory.created_at))
    chat = await session.scalars(select(ChatMessage).where(ChatMessage.user_id == user.id)
                                 .order_by(ChatMessage.id))
    providers = await session.scalars(select(OAuthAccount.provider).where(OAuthAccount.user_id == user.id))
    body = {
        "exported_at": datetime.now(UTC).isoformat(),
        "account": {**user_out(user), "sign_in_providers": sorted(set(providers))},
        "canvases": [{"id": str(c.id), "title": c.title, "created_at": _iso(c.created_at),
                      "updated_at": _iso(c.updated_at), "deleted_at": _iso(c.deleted_at)} for c in canvases],
        "cards": out_cards,
        "reminders": [{"id": str(r.id), "card_id": str(r.item_id) if r.item_id else None,
                       "canvas_id": str(r.canvas_id) if r.canvas_id else None, "note": r.note,
                       "remind_at": _iso(r.remind_at), "state": r.state} for r in reminders],
        "memories": [{"fact": m.fact, "kind": m.kind, "created_at": _iso(m.created_at)} for m in memories],
        "chat": [{"canvas_id": str(m.canvas_id) if m.canvas_id else None, "role": m.role, "content": m.content,
                  "cited_cards": [str(i) for i in m.cited_items or []], "created_at": _iso(m.created_at)}
                 for m in chat],
    }
    name = f"stash-export-{datetime.now(UTC):%Y-%m-%d}.json"
    return Response(json.dumps(body, ensure_ascii=False, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


@router.delete("/users/me", status_code=204, dependencies=[Depends(limit("account-delete", 10, 3600))])
async def delete_account(body: DeleteAccountIn, response: Response, user: User = Depends(current_user),
                         session: AsyncSession = Depends(get_session)):
    """Deletes the account and everything in it right away. Uploaded files are removed by the worker."""
    if user.password_hash and not await verify_password(body.password or "", user.password_hash):
        raise Forbidden("That password is incorrect.", code="invalid_credentials")
    rows = (await session.execute(select(Item.kind, Item.content).where(Item.owner_id == user.id))).all()
    keys = images.image_keys((r.kind, r.content) for r in rows)
    user_id = user.id
    await session.execute(delete(User).where(User.id == user_id))  # every table cascades from users
    await images.queue_object_deletes(session, keys, f"account:{user_id}")
    await session.commit()
    log.info("account deleted", extra={"user_id": str(user_id), "files": len(keys)})
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


# ---------- save by email ----------

def inbound_address(token: str | None) -> str | None:
    if not token or not settings.inbound_email_domain:
        return None
    return f"save+{token}@{settings.inbound_email_domain}"


@router.get("/users/me/inbound")
async def inbound(user: User = Depends(current_user)):
    return data({"enabled": bool(settings.inbound_email_domain and settings.inbound_secret),
                 "address": inbound_address(user.inbound_token)})


@router.post("/users/me/inbound", dependencies=[Depends(limit("inbound-rotate", 10, 3600))])
async def rotate_inbound(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """Creates the save-by-email address, or replaces it so the old one stops working."""
    if not (settings.inbound_email_domain and settings.inbound_secret):
        raise NotFound("Save by email isn't set up on this server.")
    user.inbound_token = secrets.token_hex(10)
    session.add(user)
    await session.commit()
    return data({"enabled": True, "address": inbound_address(user.inbound_token)})


def unsubscribe_token(user_id, kind: str) -> str:
    return tokens.sign_state({"sub": str(user_id), "kind": kind}, 60 * 24 * 90, "unsubscribe")


async def _unsubscribe(token: str, session: AsyncSession) -> bool:
    claims = tokens.read_state(token, "unsubscribe")
    if not claims or claims.get("kind") not in ("daily", "weekly"):
        return False
    try:
        user = await session.get(User, uuid.UUID(claims["sub"]))
    except ValueError:
        return False
    if not user:
        return False
    setattr(user, f"digest_{claims['kind']}", False)
    await session.commit()
    return True


@router.get("/email/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_page(token: str, session: AsyncSession = Depends(get_session)):
    ok = await _unsubscribe(token, session)
    message = "You're unsubscribed. You can turn digests back on in Settings." if ok else \
        "This unsubscribe link has expired. Change email settings inside Stash."
    return HTMLResponse(
        "<!doctype html><meta name=viewport content='width=device-width'><title>Stash</title>"
        "<body style='margin:0;background:#09090B;color:#EDEDEF;font:15px/1.6 -apple-system,Segoe UI,sans-serif;"
        "display:grid;place-items:center;min-height:100vh'><p style='max-width:40ch;padding:24px'>"
        f"{message}</p></body>"
    )


@router.post("/email/unsubscribe", status_code=204)
async def unsubscribe_one_click(request: Request, session: AsyncSession = Depends(get_session)):
    await _unsubscribe(request.query_params.get("token", ""), session)
