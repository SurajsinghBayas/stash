import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.jobs import enqueue
from app.data.models import Canvas, Item, User
from app.db import get_session
from app.errors import AppError, NotFound, ValidationFailed
from app.middleware.auth import current_user
from app.middleware.rate_limit import limiter
from app.schemas import UploadIn, data
from app.services.auth import tokens
from app.services.items import service as items
from app.services.uploads.storage import LocalStorage, storage

router = APIRouter(tags=["uploads"])


@router.post("/canvases/{canvas_id}/uploads", status_code=201)
async def start_upload(canvas_id: uuid.UUID, body: UploadIn, user: User = Depends(current_user),
                       session: AsyncSession = Depends(get_session)):
    limiter.hit(f"upload:user:{user.id}", 60, 3600)
    if body.bytes > settings.upload_max_bytes:
        raise ValidationFailed(f"bytes: images can be up to {settings.upload_max_bytes // (1024 * 1024)} MB",
                               code="file_too_large")
    canvas = await items.get_canvas(session, user.id, canvas_id, lock=True)
    used = await session.scalar(select(func.coalesce(func.sum(Item.bytes), 0))
                                .where(Item.owner_id == user.id, Item.deleted_at.is_(None)))
    if int(used or 0) + body.bytes > settings.user_storage_quota_mb * 1024 * 1024:
        raise AppError("Your storage is full. Delete some images to upload more.", code="quota_exceeded",
                       status=409)
    item_id = uuid.uuid4()
    key = f"uploads/{user.id}/{item_id}/original"
    item = Item(id=item_id, canvas_id=canvas.id, owner_id=user.id, kind="image", x=body.x, y=body.y, w=260,
                content={"caption": body.caption, "filename": body.filename[:200], "mime": body.mime,
                         "storage_key": key, "upload_state": "awaiting_upload"},
                bytes=body.bytes, version=1, safety_categories=[])
    session.add(item)
    await session.flush()
    await items.reindex_if_needed(session, item)  # the filename and caption get a safety verdict like any card
    canvas.updated_at = func.now()
    await session.commit()
    await session.refresh(item)
    upload = await storage().presign_put(key, body.mime, body.bytes)
    return data({"item": items.item_out(item), "upload": upload})


@router.post("/items/{item_id}/uploaded")
async def finish_upload(item_id: uuid.UUID, user: User = Depends(current_user),
                        session: AsyncSession = Depends(get_session)):
    item = await session.scalar(select(Item).where(Item.id == item_id, Item.owner_id == user.id,
                                                   Item.kind == "image", Item.deleted_at.is_(None)).with_for_update())
    if not item:
        raise NotFound("Image not found")
    if item.content.get("upload_state") != "awaiting_upload":
        return data(items.item_out(item))
    size = await storage().exists(item.content["storage_key"])
    if not size:
        raise AppError("The upload did not arrive. Try again.", code="upload_missing", status=409)
    item.content = {**item.content, "upload_state": "processing"}
    item.bytes = size
    item.version += 1
    await enqueue(session, "process_image", {"item_id": str(item.id)}, dedupe_key=f"img:{item.id}")
    await session.commit()
    await session.refresh(item)
    return data(items.item_out(item))


@router.get("/items/{item_id}/image")
async def image(item_id: uuid.UUID, size: str = Query("thumb", pattern="^(thumb|display)$"),
                user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    item = await session.scalar(
        select(Item).join(Canvas, Canvas.id == Item.canvas_id)
        .where(Item.id == item_id, Item.owner_id == user.id, Item.kind == "image", Item.deleted_at.is_(None))
    )
    # Never serve an image that has not passed the image safety check.
    if not item or item.content.get("upload_state") != "ready":
        raise NotFound("Image not found")
    key = item.content["thumb_key" if size == "thumb" else "display_key"]
    response = RedirectResponse(await storage().presign_get(key), status_code=302)
    response.headers["Cache-Control"] = "private, max-age=300"
    return response


# ---------- development storage endpoint (LocalStorage only) ----------

@router.api_route("/_local_storage/{token}", methods=["GET", "PUT"], include_in_schema=False)
async def local_storage(token: str, request: Request):
    store = storage()
    claims = tokens.read_state(token, "storage")
    if not isinstance(store, LocalStorage) or not claims or claims.get("op") != request.method.lower():
        raise NotFound()
    if request.method == "PUT":
        if request.headers.get("content-type") != claims["mime"]:
            raise ValidationFailed("Content-Type does not match the upload")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > claims["size"]:
                raise ValidationFailed("Upload is larger than declared")
        await store.put(claims["key"], bytes(body), claims["mime"])
        return Response(status_code=200)
    return Response(await store.get(claims["key"], settings.upload_max_bytes * 2), media_type="image/webp",
                    headers={"Cache-Control": "private, max-age=600"})
