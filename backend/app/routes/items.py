import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import User
from app.db import get_session
from app.middleware.auth import current_user
from app.schemas import In, data
from app.services.items import service as items
from app.services.search import service as search

router = APIRouter(tags=["items"])


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: uuid.UUID, user: User = Depends(current_user),
                      session: AsyncSession = Depends(get_session)):
    await items.delete_item(session, user.id, item_id)


@router.post("/items/{item_id}/restore")
async def restore_item(item_id: uuid.UUID, user: User = Depends(current_user),
                       session: AsyncSession = Depends(get_session)):
    """Bring a card back from the canvas trash."""
    return data(items.item_out(await items.restore_item(session, user.id, item_id)))


@router.get("/items/{item_id}/versions")
async def versions(item_id: uuid.UUID, user: User = Depends(current_user),
                   session: AsyncSession = Depends(get_session)):
    return data(await items.list_versions(session, user.id, item_id))


class RestoreVersionIn(In):
    version: int  # the card's current version, so a stale tab cannot overwrite newer edits


@router.post("/items/{item_id}/versions/{version_id}/restore")
async def restore_version(item_id: uuid.UUID, version_id: int, body: RestoreVersionIn,
                          user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    item = await items.restore_version(session, user.id, item_id, version_id, body.version)
    return data(items.item_out(item))


@router.get("/search")
async def quick_find(q: str = Query(min_length=1, max_length=200), canvas_id: uuid.UUID | None = None,
                     limit: int = Query(20, ge=1, le=50), user: User = Depends(current_user),
                     session: AsyncSession = Depends(get_session)):
    """Ctrl+K: keyword search across the user's own cards. Nothing leaves the database, so no AI and no
    safety filter is involved."""
    return data(await search.keyword(session, user.id, q, canvas_id=canvas_id, limit=limit))


@router.get("/items/{item_id}/related")
async def related(item_id: uuid.UUID, user: User = Depends(current_user),
                  session: AsyncSession = Depends(get_session)):
    return data(await search.related(session, user.id, item_id))
