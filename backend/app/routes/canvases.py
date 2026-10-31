import base64
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.jobs import enqueue
from app.data.models import Canvas, Item, User
from app.db import get_session
from app.errors import ValidationFailed
from app.middleware.auth import current_user
from app.schemas import CanvasIn, CanvasOut, CanvasPatch, ItemBatch, ItemIn, data, page
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


@router.post("", status_code=201)
async def create_canvas(body: CanvasIn, user: User = Depends(current_user),
                        session: AsyncSession = Depends(get_session)):
    canvas = Canvas(owner_id=user.id, title=body.title)
    session.add(canvas)
    await session.commit()
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
    # Cards go with the canvas: no reminders for them, and their images stop counting against storage.
    images = (await session.execute(
        text("update items set deleted_at = now() where canvas_id = :c and deleted_at is null "
             "returning id, kind"), {"c": canvas.id})).all()
    await session.execute(text("update reminders set state = 'cancelled' where canvas_id = :c and state = 'pending'"),
                          {"c": canvas.id})
    for row in images:
        if row.kind == "image":
            await enqueue(session, "delete_image", {"item_id": str(row.id)}, dedupe_key=f"delimg:{row.id}")
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
