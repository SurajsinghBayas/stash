"""Card rules: content validation, indexing triggers, optimistic concurrency."""

import uuid
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.jobs import enqueue
from app.data.models import Canvas, Item
from app.errors import NotFound, ValidationFailed
from app.schemas import CONTENT_MODELS, ItemIn, ItemOut, ItemPatch
from app.services.items.text import normalize_url, search_text, text_hash
from app.services.safety.local import is_adult_domain

# Fields the server fills in; a client can never set them.
SERVER_LINK_FIELDS = {"title", "description", "image", "site_name", "favicon", "fetch_state", "url_norm",
                      "blocked_domain"}
SERVER_IMAGE_FIELDS = {"storage_key", "thumb_key", "display_key", "mime", "bytes", "width", "height", "filename",
                       "upload_state"}


def item_out(item: Item) -> dict:
    return ItemOut.model_validate(item).model_dump(mode="json")


async def get_canvas(session: AsyncSession, owner_id: uuid.UUID, canvas_id: uuid.UUID, *, lock=False) -> Canvas:
    q = select(Canvas).where(Canvas.id == canvas_id, Canvas.owner_id == owner_id, Canvas.deleted_at.is_(None))
    canvas = await session.scalar(q.with_for_update() if lock else q)
    if not canvas:
        raise NotFound("Canvas not found")
    return canvas


def _validated_content(kind: str, raw: dict, existing: dict | None = None) -> dict:
    """A patch may carry only the fields it changes; the rest keep their current values."""
    model = CONTENT_MODELS[kind]
    server_fields = SERVER_LINK_FIELDS if kind == "link" else SERVER_IMAGE_FIELDS if kind == "image" else set()
    if existing:
        raw = {**{k: v for k, v in existing.items() if k not in server_fields}, **raw}
    try:
        clean = model.model_validate(raw).model_dump()
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(p) for p in first["loc"])
        raise ValidationFailed(f"content.{field}: {first['msg']}") from exc
    if kind == "link":
        parts = urlsplit(clean["url"].strip())
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValidationFailed("content.url: use a full http or https address")
        clean["url"] = clean["url"].strip()
    if existing:
        clean = {**{k: v for k, v in existing.items() if k in server_fields}, **clean}
    return clean


async def reindex_if_needed(session: AsyncSession, item: Item) -> None:
    text = search_text(item.kind, item.content)
    digest = text_hash(text)
    if digest == item.content_hash:
        return
    item.search_text = text
    item.content_hash = digest
    item.index_state = "pending"
    if item.safety_hash != digest:
        item.safety_state = "unchecked"
        item.safety_categories = []
    await enqueue(session, "index_item", {"item_id": str(item.id), "hash": digest},
                  dedupe_key=f"index:{item.id}:{digest}")


def _prepare_link(item: Item, old_url_norm: str | None) -> bool:
    """Returns True when the URL changed and metadata must be fetched again."""
    url_norm = normalize_url(item.content["url"])
    host = (urlsplit(item.content["url"]).hostname or "").lower()
    content = dict(item.content)
    content["url_norm"] = url_norm
    content["blocked_domain"] = is_adult_domain(host)
    changed = url_norm != old_url_norm
    if changed:
        for key in ("title", "description", "image", "site_name", "favicon"):
            content.pop(key, None)
        content["fetch_state"] = "blocked" if content["blocked_domain"] else "pending"
    item.content = content
    return changed and not content["blocked_domain"]


async def create_item(session: AsyncSession, owner_id: uuid.UUID, canvas_id: uuid.UUID, body: ItemIn) -> Item:
    canvas = await get_canvas(session, owner_id, canvas_id)
    content = _validated_content(body.kind, body.content)
    item = Item(id=body.id or uuid.uuid4(), canvas_id=canvas.id, owner_id=owner_id, kind=body.kind, x=body.x,
                y=body.y, w=body.w, h=body.h, z=body.z, content=content, version=1, safety_categories=[])
    fetch = body.kind == "link" and _prepare_link(item, None)
    if await session.scalar(select(Item.id).where(Item.id == item.id)):
        raise ValidationFailed("id: already used")
    session.add(item)
    await session.flush()
    if fetch:
        await enqueue(session, "fetch_link", {"item_id": str(item.id)}, dedupe_key=f"fetch:{item.id}:1")
    await reindex_if_needed(session, item)
    canvas.updated_at = func.now()
    await session.commit()
    await session.refresh(item)
    return item


async def patch_items(session: AsyncSession, owner_id: uuid.UUID, canvas_id: uuid.UUID,
                      patches: list[ItemPatch]) -> tuple[list[Item], list[Item]]:
    canvas = await get_canvas(session, owner_id, canvas_id)
    ids = [p.id for p in patches]
    rows = {
        i.id: i for i in await session.scalars(
            select(Item).where(Item.id.in_(ids), Item.owner_id == owner_id, Item.canvas_id == canvas.id,
                               Item.deleted_at.is_(None)).with_for_update()
        )
    }
    updated: list[Item] = []
    conflicts: list[Item] = []
    for patch in patches:
        item = rows.get(patch.id)
        if not item:
            raise NotFound(f"Card {patch.id} not found")
        if item.version != patch.version:
            conflicts.append(item)
            continue
        for field in ("x", "y", "w", "h", "z"):
            value = getattr(patch, field)
            if value is not None:
                setattr(item, field, value)
        if patch.content is not None:
            old_norm = item.content.get("url_norm")
            item.content = _validated_content(item.kind, patch.content, existing=item.content)
            if item.kind == "link" and _prepare_link(item, old_norm):
                await enqueue(session, "fetch_link", {"item_id": str(item.id)},
                              dedupe_key=f"fetch:{item.id}:{item.version + 1}")
            await reindex_if_needed(session, item)
        item.version += 1
        item.updated_at = func.now()
        updated.append(item)
    if updated:
        canvas.updated_at = func.now()
    await session.commit()
    for item in updated:
        await session.refresh(item)
    return updated, conflicts


async def delete_item(session: AsyncSession, owner_id: uuid.UUID, item_id: uuid.UUID) -> None:
    item = await session.scalar(select(Item).where(Item.id == item_id, Item.owner_id == owner_id,
                                                   Item.deleted_at.is_(None)))
    if not item:
        raise NotFound("Card not found")
    item.deleted_at = func.now()
    await session.execute(update(Canvas).where(Canvas.id == item.canvas_id).values(updated_at=func.now()))
    if item.kind == "image":
        await enqueue(session, "delete_image", {"item_id": str(item.id)}, dedupe_key=f"delimg:{item.id}")
    from app.data.models import Reminder

    await session.execute(update(Reminder).where(Reminder.item_id == item.id, Reminder.state == "pending")
                          .values(state="cancelled"))
    await session.commit()


async def find_duplicate_link(session: AsyncSession, owner_id: uuid.UUID, url: str) -> dict | None:
    norm = normalize_url(url)
    row = (await session.execute(
        select(Item.id, Item.canvas_id, Canvas.title, Item.created_at)
        .join(Canvas, Canvas.id == Item.canvas_id)
        .where(Item.owner_id == owner_id, Item.kind == "link", Item.deleted_at.is_(None),
               Canvas.deleted_at.is_(None), Item.content["url_norm"].astext == norm)
        .order_by(Item.created_at.desc()).limit(1)
    )).first()
    if not row:
        return None
    return {"item_id": str(row.id), "canvas_id": str(row.canvas_id), "canvas_title": row.title,
            "created_at": row.created_at.isoformat()}
