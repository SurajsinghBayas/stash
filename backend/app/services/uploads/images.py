"""Validate, clean and moderate an uploaded image. Runs in the worker."""

import asyncio
import io
import logging
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.jobs import enqueue
from app.data.models import Item, ModerationEvent
from app.services.safety.service import check_image
from app.services.uploads.storage import storage

log = logging.getLogger("stash.images")

Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard
ALLOWED = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}
DISPLAY_MAX = 2400
THUMB_MAX = 800
CHECK_MAX = 1024


class RejectedImage(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _render(data: bytes, declared_mime: str) -> tuple[bytes, bytes, bytes, int, int]:
    """Returns (display webp, thumb webp, jpeg for the safety check, width, height)."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(data))
        fmt = img.format
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise RejectedImage("not_an_image") from exc
    if fmt not in ALLOWED or ALLOWED[fmt] != declared_mime:
        raise RejectedImage("type_mismatch")
    img.seek(0)
    img = ImageOps.exif_transpose(img)  # also drops EXIF (and GPS) from the copies we write
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
    width, height = img.size

    def encode(max_side: int, fmt_out: str, quality: int) -> bytes:
        copy = img.copy()
        copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        if fmt_out == "JPEG" and copy.mode != "RGB":
            copy = copy.convert("RGB")
        out = io.BytesIO()
        copy.save(out, fmt_out, quality=quality, method=4) if fmt_out == "WEBP" else copy.save(out, fmt_out,
                                                                                               quality=quality)
        return out.getvalue()

    return encode(DISPLAY_MAX, "WEBP", 85), encode(THUMB_MAX, "WEBP", 80), encode(CHECK_MAX, "JPEG", 85), width, height


async def process(session: AsyncSession, item_id: uuid.UUID) -> None:
    item = await session.scalar(select(Item).where(Item.id == item_id, Item.deleted_at.is_(None)).with_for_update())
    if not item or item.content.get("upload_state") != "processing":
        return
    store = storage()
    original = item.content["storage_key"]
    base = original.rsplit("/", 1)[0]
    try:
        data = await store.get(original, settings.upload_max_bytes)
        display, thumb, check_copy, width, height = await asyncio.to_thread(_render, data, item.content["mime"])
    except (RejectedImage, ValueError) as exc:
        reason = exc.reason if isinstance(exc, RejectedImage) else "too_large"
        await store.delete(original)
        item.content = {**item.content, "upload_state": "rejected", "reject_reason": reason}
        item.bytes = 0
        item.version += 1
        await session.commit()
        return

    verdict = await check_image(check_copy, "jpeg")  # raises SafetyUnavailable → job retries, image stays hidden
    if not verdict.ok:
        await store.delete(original)
        item.content = {**item.content, "upload_state": "blocked"}
        item.bytes = 0
        item.safety_categories = verdict.categories
        item.version += 1
        session.add(ModerationEvent(user_id=item.owner_id, source="image", item_id=item.id, action="deleted",
                                    categories=verdict.categories))
        await session.commit()
        return

    display_key, thumb_key = f"{base}/display.webp", f"{base}/thumb.webp"
    await store.put(display_key, display, "image/webp")
    await store.put(thumb_key, thumb, "image/webp")
    await store.delete(original)
    item.content = {**item.content, "upload_state": "ready", "display_key": display_key, "thumb_key": thumb_key,
                    "width": width, "height": height}
    item.bytes = len(display) + len(thumb)
    item.version += 1
    if item.content_hash:  # the vision agent can now see the image: understand the card again
        await enqueue(session, "index_item", {"item_id": str(item.id), "hash": item.content_hash, "force": True},
                      dedupe_key=f"index:{item.id}:{item.content_hash}:image")
    await session.commit()


async def delete_files(session: AsyncSession, item_id: uuid.UUID) -> None:
    item = await session.get(Item, item_id)
    if not item:
        return
    store = storage()
    for key in ("storage_key", "display_key", "thumb_key"):
        if item.content.get(key):
            await store.delete(item.content[key])


IMAGE_KEYS = ("storage_key", "display_key", "thumb_key")


def image_keys(rows) -> list[str]:
    """Storage keys of every image among (kind, content) rows."""
    return [content[k] for kind, content in rows if kind == "image" for k in IMAGE_KEYS if content.get(k)]


async def queue_object_deletes(session: AsyncSession, keys: list[str], label: str) -> None:
    """For rows being deleted for good: the files go in the same transaction's job, 300 keys a job."""
    for start in range(0, len(keys), 300):
        await enqueue(session, "delete_objects", {"keys": keys[start:start + 300]},
                      dedupe_key=f"objects:{label}:{start}")
