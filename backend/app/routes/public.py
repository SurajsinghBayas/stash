"""Read-only views of canvases their owners chose to share. No sign-in; the share token is the only key.

Only cards that passed the safety check are shown, images only after the image check, and nothing that identifies
the owner (ids, email, storage keys) or that we did not check ourselves (link preview images from other sites).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import Canvas, Item
from app.db import get_session
from app.errors import NotFound
from app.middleware.rate_limit import limit
from app.schemas import data
from app.services.uploads.storage import storage

router = APIRouter(prefix="/public", tags=["public"])

LINK_FIELDS = ("url", "title", "description", "site_name", "comment", "fetch_state")


def _public_content(item: Item) -> dict | None:
    c = item.content
    if item.kind == "link":
        if c.get("blocked_domain"):
            return None
        return {k: c[k] for k in LINK_FIELDS if k in c}
    if item.kind == "image":
        if c.get("upload_state") != "ready":
            return None
        return {"caption": c.get("caption", ""), "width": c.get("width"), "height": c.get("height"),
                "upload_state": "ready"}
    return dict(c)


async def _shared(session: AsyncSession, token: str) -> Canvas:
    canvas = await session.scalar(select(Canvas).where(Canvas.share_token == token, Canvas.deleted_at.is_(None)))
    if not canvas or len(token) < 16:
        raise NotFound("This link doesn't work. The canvas may no longer be shared.")
    return canvas


@router.get("/canvases/{token}", dependencies=[Depends(limit("public", 120, 60))])
async def shared_canvas(token: str, session: AsyncSession = Depends(get_session)):
    canvas = await _shared(session, token)
    rows = await session.scalars(select(Item).where(Item.canvas_id == canvas.id, Item.deleted_at.is_(None),
                                                    Item.safety_state == "ok").order_by(Item.z, Item.created_at))
    cards = []
    for item in rows:
        content = _public_content(item)
        if content is not None:
            cards.append({"id": str(item.id), "kind": item.kind, "x": item.x, "y": item.y, "w": item.w, "h": item.h,
                          "z": item.z, "content": content})
    return data({"title": canvas.title, "updated_at": canvas.updated_at.isoformat(), "items": cards})


@router.get("/canvases/{token}/items/{item_id}/image", dependencies=[Depends(limit("public-img", 600, 60))])
async def shared_image(token: str, item_id: uuid.UUID, size: str = Query("thumb", pattern="^(thumb|display)$"),
                       session: AsyncSession = Depends(get_session)):
    canvas = await _shared(session, token)
    item = await session.scalar(select(Item).where(Item.id == item_id, Item.canvas_id == canvas.id,
                                                   Item.kind == "image", Item.deleted_at.is_(None),
                                                   Item.safety_state == "ok"))
    if not item or item.content.get("upload_state") != "ready":
        raise NotFound("Image not found")
    key = item.content["thumb_key" if size == "thumb" else "display_key"]
    response = RedirectResponse(await storage().presign_get(key), status_code=302)
    response.headers["Cache-Control"] = "public, max-age=300"
    return response
