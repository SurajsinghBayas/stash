import base64
import json
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.models import Canvas, Item, User
from app.db import get_session
from app.errors import ValidationFailed
from app.middleware.auth import current_user
from app.schemas import CanvasIn, CanvasOut, CanvasPatch, ItemBatch, ItemIn, data, page
from app.services.canvases import templates
from app.services.items import service as items

router = APIRouter(prefix="/canvases", tags=["canvases"])


def _cursor(updated_at: datetime, canvas_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([updated_at.isoformat(), str(canvas_id)]).encode()).decode()


def _parse_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        ts, cid = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(ts), uuid.UUID(cid)
    except (ValueError, TypeError) as exc:
        raise ValidationFailed("cursor: invalid") from exc


PREVIEW_SQL = text("""
  select canvas_id, count(*) as n,
         jsonb_agg(jsonb_build_object('kind', kind, 'x', x, 'y', y, 'w', w, 'h', h,
                                      'color', content->>'color') order by z desc, updated_at desc) as preview
  from items where canvas_id = any(:ids) and deleted_at is null group by canvas_id
""")


async def _canvas_out(session: AsyncSession, canvases: list[Canvas]) -> list[dict]:
    if not canvases:
        return []
    stats = {r.canvas_id: r for r in await session.execute(PREVIEW_SQL, {"ids": [c.id for c in canvases]})}
    out = []
    for c in canvases:
        row = stats.get(c.id)
        model = CanvasOut.model_validate(c)
        model.item_count = row.n if row else 0
        model.preview = list(row.preview)[:8] if row else []
        out.append(model.model_dump(mode="json"))
    return out


@router.get("")
async def list_canvases(limit: int = Query(20, ge=1, le=100), cursor: str | None = None,
                        q: str | None = Query(None, max_length=120),
                        user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    query = select(Canvas).where(Canvas.owner_id == user.id, Canvas.deleted_at.is_(None))
    if q:
        query = query.where(Canvas.title.ilike("%" + q.replace("%", r"\%").replace("_", r"\_") + "%"))
    if cursor:
        ts, cid = _parse_cursor(cursor)
        query = query.where((Canvas.updated_at < ts) | ((Canvas.updated_at == ts) & (Canvas.id < cid)))
    rows = list(await session.scalars(query.order_by(Canvas.updated_at.desc(), Canvas.id.desc()).limit(limit + 1)))
    next_cursor = _cursor(rows[limit - 1].updated_at, rows[limit - 1].id) if len(rows) > limit else None
    return page(await _canvas_out(session, rows[:limit]), limit, next_cursor)


@router.get("/templates")
async def list_templates(user: User = Depends(current_user)):
    return data(templates.listing())


@router.get("/trash")
async def canvas_trash(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = await items.list_canvas_trash(session, user.id)
    out = await _canvas_out_with_deleted(session, rows)
    return data(out)


async def _canvas_out_with_deleted(session: AsyncSession, canvases: list[Canvas]) -> list[dict]:
    """Trash listing: the card count is what restoring brings back (cards deleted with the canvas)."""
    out = []
    for c in canvases:
        n = await session.scalar(select(func.count()).select_from(Item)
                                 .where(Item.canvas_id == c.id, Item.deleted_at == c.deleted_at))
        model = CanvasOut.model_validate(c).model_dump(mode="json")
        out.append({**model, "item_count": int(n or 0), "deleted_at": c.deleted_at.isoformat()})
    return out


@router.post("", status_code=201)
async def create_canvas(body: CanvasIn, user: User = Depends(current_user),
                        session: AsyncSession = Depends(get_session)):
    template = templates.TEMPLATES.get(body.template) if body.template else None
    if body.template and not template:
        raise ValidationFailed("template: unknown template")
    title = template["title"] if template and body.title == "Untitled" else body.title
    canvas = Canvas(owner_id=user.id, title=title)
    session.add(canvas)
    await session.commit()
    await session.refresh(canvas)
    for card in template["cards"] if template else []:
        await items.create_item(session, user.id, canvas.id, ItemIn(**card))
    await session.refresh(canvas)
    return data((await _canvas_out(session, [canvas]))[0])


@router.get("/{canvas_id}")
async def get_canvas(canvas_id: uuid.UUID, user: User = Depends(current_user),
                     session: AsyncSession = Depends(get_session)):
    canvas = await items.get_canvas(session, user.id, canvas_id)
    return data((await _canvas_out(session, [canvas]))[0])


@router.patch("/{canvas_id}")
async def update_canvas(canvas_id: uuid.UUID, body: CanvasPatch, user: User = Depends(current_user),
                        session: AsyncSession = Depends(get_session)):
    canvas = await items.get_canvas(session, user.id, canvas_id, lock=True)
    if body.title is not None:
        canvas.title = body.title
        canvas.updated_at = func.now()
    if body.viewport is not None:
        canvas.viewport = body.viewport.model_dump()  # viewport changes don't reorder the dashboard
    await session.commit()
    await session.refresh(canvas)
    return data((await _canvas_out(session, [canvas]))[0])


@router.delete("/{canvas_id}", status_code=204)
async def delete_canvas(canvas_id: uuid.UUID, user: User = Depends(current_user),
                        session: AsyncSession = Depends(get_session)):
    canvas = await items.get_canvas(session, user.id, canvas_id, lock=True)
    canvas.deleted_at = func.now()
    canvas.share_token = None  # a deleted canvas is never public, and restoring does not re-share it
    canvas.shared_at = None
    # Cards go with the canvas (same timestamp, so restoring brings back exactly these): no reminders for them,
    # and their images stop counting against storage. Files stay until the purge job, so restore works.
    await session.execute(text("update items set deleted_at = now() where canvas_id = :c and deleted_at is null"),
                          {"c": canvas.id})
    await session.execute(text("update reminders set state = 'cancelled' where canvas_id = :c and state = 'pending'"),
                          {"c": canvas.id})
    await session.commit()


@router.post("/{canvas_id}/restore")
async def restore_canvas(canvas_id: uuid.UUID, user: User = Depends(current_user),
                         session: AsyncSession = Depends(get_session)):
    canvas = await items.restore_canvas(session, user.id, canvas_id)
    return data((await _canvas_out(session, [canvas]))[0])


@router.get("/{canvas_id}/trash")
async def item_trash(canvas_id: uuid.UUID, user: User = Depends(current_user),
                     session: AsyncSession = Depends(get_session)):
    rows = await items.list_trash(session, user.id, canvas_id)
    return data([{**items.item_out(i), "deleted_at": i.deleted_at.isoformat()} for i in rows])


def share_url(token: str) -> str:
    return f"{settings.app_url}/s/{token}"


@router.post("/{canvas_id}/share")
async def share_canvas(canvas_id: uuid.UUID, user: User = Depends(current_user),
                       session: AsyncSession = Depends(get_session)):
    """Turn on the read-only public link (idempotent: the same link while sharing stays on)."""
    canvas = await items.get_canvas(session, user.id, canvas_id, lock=True)
    if not canvas.share_token:
        canvas.share_token = secrets.token_urlsafe(18)
        canvas.shared_at = func.now()
        await session.commit()
        await session.refresh(canvas)
    return data({"token": canvas.share_token, "url": share_url(canvas.share_token)})


@router.delete("/{canvas_id}/share", status_code=204)
async def unshare_canvas(canvas_id: uuid.UUID, user: User = Depends(current_user),
                         session: AsyncSession = Depends(get_session)):
    canvas = await items.get_canvas(session, user.id, canvas_id, lock=True)
    canvas.share_token = None
    canvas.shared_at = None
    await session.commit()


@router.get("/{canvas_id}/items")
async def list_items(canvas_id: uuid.UUID, limit: int = Query(1000, ge=1, le=2000), cursor: str | None = None,
                     user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """A canvas loads in one or two pages; the cap keeps a runaway canvas from loading 100k cards at once."""
    canvas = await items.get_canvas(session, user.id, canvas_id)
    query = select(Item).where(Item.canvas_id == canvas.id, Item.deleted_at.is_(None))
    if cursor:
        try:
            query = query.where(Item.id > uuid.UUID(cursor))
        except ValueError as exc:
            raise ValidationFailed("cursor: invalid") from exc
    rows = list(await session.scalars(query.order_by(Item.id).limit(limit + 1)))
    next_cursor = str(rows[limit - 1].id) if len(rows) > limit else None
    return page([items.item_out(i) for i in rows[:limit]], limit, next_cursor)


@router.post("/{canvas_id}/items", status_code=201)
async def create_item(canvas_id: uuid.UUID, body: ItemIn, user: User = Depends(current_user),
                      session: AsyncSession = Depends(get_session)):
    duplicate = None
    if body.kind == "link" and isinstance(body.content.get("url"), str):
        duplicate = await items.find_duplicate_link(session, user.id, body.content["url"])
    item = await items.create_item(session, user.id, canvas_id, body)
    return {"data": items.item_out(item), "meta": {"duplicate_of": duplicate}}


@router.patch("/{canvas_id}/items")
async def patch_items(canvas_id: uuid.UUID, body: ItemBatch, user: User = Depends(current_user),
                      session: AsyncSession = Depends(get_session)):
    updated, conflicts = await items.patch_items(session, user.id, canvas_id, body.items)
    return data({"updated": [items.item_out(i) for i in updated],
                 "conflicts": [items.item_out(i) for i in conflicts]})
