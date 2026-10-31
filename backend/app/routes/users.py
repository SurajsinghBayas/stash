import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import Item, Memory, User
from app.db import get_session
from app.errors import NotFound
from app.middleware.auth import current_user
from app.schemas import UserPatch, data
from app.services.auth import service as auth_service
from app.services.auth import tokens
from app.services.usage import snapshot
from app.services.users import user_out

router = APIRouter(tags=["users"])


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
