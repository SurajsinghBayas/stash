"""Background worker: `python -m app.worker`. Runs as its own PM2 process next to the API.

Job handlers drain the Postgres queue; a scheduler loop queues due reminders and digests, returns stuck jobs to
the queue and prunes old ones. Several workers can run at once: claims use SKIP LOCKED and every scheduled job
has a dedupe key.
"""

import asyncio
import json
import logging
import signal
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data import jobs
from app.data.models import Canvas, Item, ModerationEvent, Reminder, User
from app.db import SessionLocal, capabilities, detect_capabilities, engine
from app.logging_setup import setup_logging
from app.services.agents import cache as agent_cache
from app.services.agents import ingest, memory
from app.services.ai import client as ai
from app.services.digests import service as digests
from app.services.items.service import reindex_if_needed
from app.services.items.text import snippet_of, title_of
from app.services.links.fetch import BlockedURL, fetch_page
from app.services.mail import sender, templates
from app.services.reminders.service import queue_due
from app.services.safety.service import check_text, from_checked_item
from app.services.uploads import images

log = logging.getLogger("stash.worker")

CONCURRENCY = 4
IDLE_SLEEP_S = 1.0
TICK_S = 30
LINK_FETCH_ATTEMPTS = 3


class Retry(Exception):
    """Raise to retry later without counting it as an error in the logs."""

    def __init__(self, reason: str, after: timedelta | None = None):
        super().__init__(reason)
        self.after = after


Handler = Callable[[AsyncSession, dict, dict], Awaitable[None]]


# ---------- links ----------

async def fetch_link(session: AsyncSession, payload: dict, job: dict) -> None:
    item = await session.scalar(select(Item).where(Item.id == uuid.UUID(payload["item_id"]),
                                                   Item.deleted_at.is_(None), Item.kind == "link"))
    if not item or item.content.get("fetch_state") != "pending":
        return
    url = item.content["url"]
    page = None
    try:
        page = await fetch_page(url)
        meta, state = page.meta, "ready"
    except BlockedURL as exc:
        meta, state = {}, "failed"
        log.info("link fetch refused", extra={"item_id": str(item.id), "reason": str(exc)})
    except (httpx.HTTPError, OSError) as exc:
        if job["attempts"] < LINK_FETCH_ATTEMPTS:
            raise Retry(type(exc).__name__) from exc
        meta, state = {}, "failed"

    await session.refresh(item, with_for_update=True)
    if item.deleted_at or item.content.get("url") != url:
        return  # the user changed the URL meanwhile; a newer fetch job handles it
    item.content = {**item.content, **{k: v for k, v in meta.items() if v}, "fetch_state": state}
    if page and page.body and item.content.get("url_norm"):
        await session.execute(text(
            "insert into link_cache (url_norm, final_url, meta, body, word_count, fetched_at) "
            "values (:u, :f, cast(:m as jsonb), :b, :w, now()) "
            "on conflict (url_norm) do update set final_url = excluded.final_url, meta = excluded.meta, "
            "body = excluded.body, word_count = excluded.word_count, fetched_at = now()"),
            {"u": item.content["url_norm"], "f": page.final_url, "m": json.dumps(page.meta),
             "b": page.body, "w": len(page.body.split())})
    item.version += 1
    await reindex_if_needed(session, item)
    await session.commit()


# ---------- safety + search index ----------

async def _write_index(session: AsyncSession, item_id: uuid.UUID, content_hash: str, *, state: str,
                       categories: list[str], index: str, ai_doc: dict | None, understood: bool) -> int:
    """Returns rows updated. `ai_doc` is stored only when `understood` (None means try the reader again later)."""
    result = await session.execute(text(
        "update items set safety_state = :state, safety_categories = :cats, safety_hash = :h, index_state = :index, "
        "ai = case when cast(:understood as boolean) then cast(:ai as jsonb) else ai end, "
        "ai_hash = case when cast(:understood as boolean) then :ai_hash else null end "
        "where id = :id and content_hash = :h and deleted_at is null"),
        {"id": item_id, "h": content_hash, "state": state, "cats": categories, "index": index,
         "understood": understood, "ai": json.dumps(ai_doc or {}),
         "ai_hash": ingest.understood_hash(content_hash) if understood else None})
    return result.rowcount or 0


async def index_item(session: AsyncSession, payload: dict, job: dict) -> None:
    item = await session.scalar(select(Item).where(Item.id == uuid.UUID(payload["item_id"]),
                                                   Item.deleted_at.is_(None)))
    if not item or item.content_hash is None or payload.get("hash", item.content_hash) != item.content_hash:
        return  # deleted, or the text changed since this job was queued (a newer job covers it)
    item_id, content_hash, body = item.id, item.content_hash, item.search_text or ""
    owner_id, was_flagged = item.owner_id, item.safety_state == "flagged"

    if item.safety_hash == content_hash and item.safety_state in ("ok", "flagged"):
        state, categories = item.safety_state, list(item.safety_categories)
        safe = from_checked_item(body, state, item.safety_hash, content_hash) if state == "ok" else None
    elif item.kind == "link" and item.content.get("blocked_domain"):
        state, categories, safe = "flagged", ["ADULT_DOMAIN"], None
    else:
        verdict = await check_text(body, "input")  # SafetyUnavailable → job retries, card stays unchecked
        state, categories, safe = ("ok", [], verdict.safe) if verdict.ok else ("flagged", verdict.categories, None)

    embed_error = None
    vectors: list[list[float]] | None = None
    ai_doc: dict | None = {}
    understood = True
    saved = False
    if state == "ok" and safe and safe.value.strip():
        result = await ingest.run(session, item, safe, force=bool(payload.get("force")))
        if result.state == "flagged":
            state, categories, ai_doc = "flagged", result.categories, {}
        else:
            ai_doc = result.ai if result.ai is not None else None
            understood = result.ai is not None
            if result.chunks and capabilities.vector and settings.embeddings_configured:
                try:
                    vectors = await ingest.embed_chunks(session, result)
                except ai.AIUnavailable as exc:
                    embed_error = exc
            await ingest.save(session, item, result, vectors)
            saved = True
    if not saved:
        await session.execute(text("delete from chunks where item_id = :id"), {"id": item_id})
        if item in session:
            session.expunge(item)

    # Only write if the card still has the text we checked; otherwise a newer index job is queued.
    # The safety verdict is saved even when embedding fails, so keyword search can use the chunks meanwhile.
    wrote = await _write_index(session, item_id, content_hash, state=state, categories=categories,
                               index="pending" if embed_error else "ready", ai_doc=ai_doc, understood=understood)
    if wrote and vectors and capabilities.vector:
        await session.execute(
            text("update items set embedding = cast(:v as vector), embed_model = :m where id = :id"),
            {"v": ingest.json_vec(vectors[0]), "m": settings.embed_model, "id": item_id})
    if wrote and state == "flagged" and not was_flagged:
        source = "link_domain" if "ADULT_DOMAIN" in categories else "item"
        session.add(ModerationEvent(user_id=owner_id, source=source, item_id=item_id, action="flagged",
                                    categories=categories))
    await session.commit()
    if embed_error and wrote:
        raise Retry("embeddings unavailable", timedelta(minutes=2)) from embed_error


# ---------- images ----------

async def process_image(session: AsyncSession, payload: dict, job: dict) -> None:
    await images.process(session, uuid.UUID(payload["item_id"]))


async def delete_image(session: AsyncSession, payload: dict, job: dict) -> None:
    await images.delete_files(session, uuid.UUID(payload["item_id"]))


async def remember(session: AsyncSession, payload: dict, job: dict) -> None:
    await memory.extract(session, uuid.UUID(payload["user_id"]), int(payload["message_id"]))


# ---------- email ----------

async def _reminder_mail(session: AsyncSession, payload: dict) -> tuple[str, templates.Mail] | None:
    reminder = await session.scalar(select(Reminder).where(Reminder.id == uuid.UUID(payload["reminder_id"]))
                                    .with_for_update())
    if not reminder or reminder.state != "pending" or int(reminder.remind_at.timestamp()) != payload["at"]:
        return None  # cancelled, already sent, or rescheduled (a new job exists for the new time)
    user = await session.get(User, reminder.user_id)
    if not user or not user.email or user.suspended_at:
        reminder.state = "failed"
        await session.commit()
        return None
    card_title, card_snippet, canvas_title, link = "", "", "Stash", f"{settings.app_url}/app"
    if reminder.item_id:
        item = await session.get(Item, reminder.item_id)
        if item and not item.deleted_at:
            canvas = await session.get(Canvas, item.canvas_id)
            canvas_title = canvas.title if canvas else canvas_title
            link = f"{settings.app_url}/c/{item.canvas_id}?item={item.id}"
            if item.safety_state == "flagged":
                card_title = "A card on this canvas"  # flagged text never goes out by email
            else:
                card_title, card_snippet = title_of(item.kind, item.content), snippet_of(item.kind, item.content)
    return user.email, templates.reminder(card_title or "Reminder", card_snippet, reminder.note, canvas_title,
                                          link)


async def send_email(session: AsyncSession, payload: dict, job: dict) -> None:
    template = payload["template"]
    headers: dict[str, str] = {}
    if template in ("verify_email", "reset_password"):
        to = payload["to"]
        mail = getattr(templates, template)(payload["link"])
    elif template == "reminder":
        found = await _reminder_mail(session, payload)
        if not found:
            return
        to, mail = found
    elif template == "digest":
        user = await session.get(User, uuid.UUID(payload["user_id"]))
        if not user or not user.email:
            return
        built = await digests.build(session, user.id, payload["kind"], date.fromisoformat(payload["period_start"]))
        if not built:
            return
        to, mail = user.email, built
        from app.routes.users import unsubscribe_token

        token = unsubscribe_token(user.id, payload["kind"])
        headers = {"List-Unsubscribe": f"<{settings.app_url}/api/v1/email/unsubscribe?token={token}>",
                   "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    else:
        raise ValueError(f"unknown email template {template}")

    await sender.send(to, mail.subject, mail.html, mail.text, headers)

    if template == "reminder":
        await session.execute(text("update reminders set state = 'sent', sent_at = now() where id = :id"),
                              {"id": uuid.UUID(payload["reminder_id"])})
    elif template == "digest":
        await session.execute(text("update digest_runs set sent_at = now() where user_id = :u and kind = :k "
                                   "and period_start = :p"),
                              {"u": uuid.UUID(payload["user_id"]), "k": payload["kind"],
                               "p": date.fromisoformat(payload["period_start"])})
    else:
        # Sign-in links are secrets: drop them from the stored job once sent.
        await session.execute(text("update jobs set payload = payload - 'link' where id = :id"), {"id": job["id"]})
    await session.commit()


HANDLERS: dict[str, Handler] = {
    "fetch_link": fetch_link,
    "index_item": index_item,
    "process_image": process_image,
    "delete_image": delete_image,
    "send_email": send_email,
    "remember": remember,
}


# ---------- loops ----------

async def run_one() -> bool:
    async with SessionLocal() as session:
        job = await jobs.claim(session)
    if not job:
        return False
    payload = job["payload"] if isinstance(job["payload"], dict) else json.loads(job["payload"])
    handler = HANDLERS.get(job["kind"])
    started = asyncio.get_running_loop().time()
    async with SessionLocal() as session:
        try:
            if handler is None:
                raise ValueError(f"no handler for {job['kind']}")
            await handler(session, payload, job)
            await session.rollback()  # anything a handler left uncommitted is discarded
            await jobs.complete(session, job["id"])
            log.info("job done", extra={"job_id": job["id"], "kind": job["kind"],
                                        "ms": int((asyncio.get_running_loop().time() - started) * 1000)})
        except Retry as exc:
            await session.rollback()
            await jobs.fail(session, job["id"], job["attempts"], f"retry: {exc}", retry_in=exc.after)
        except Exception as exc:
            await session.rollback()
            log.exception("job failed", extra={"job_id": job["id"], "kind": job["kind"],
                                               "attempt": job["attempts"]})
            await jobs.fail(session, job["id"], job["attempts"], f"{type(exc).__name__}: {exc}")
    return True


async def job_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            busy = await run_one()
        except Exception:
            log.exception("job loop error")
            busy = False
        if not busy:
            try:
                await asyncio.wait_for(stop.wait(), IDLE_SLEEP_S)
            except TimeoutError:
                pass


_last_run: dict[str, datetime] = {}


def _due(task: str, every: timedelta, now: datetime) -> bool:
    if now - _last_run.get(task, datetime.min.replace(tzinfo=UTC)) < every:
        return False
    _last_run[task] = now
    return True


async def tick(now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    async with SessionLocal() as session:
        await queue_due(session)
        if _due("digests", timedelta(minutes=5), now):
            await digests.schedule(session, now)
        if _due("recover", timedelta(minutes=1), now):
            await jobs.recover_stuck(session)
        if _due("prune", timedelta(hours=1), now):
            await jobs.prune(session)
            await agent_cache.prune(session)
        if _due("understand", timedelta(minutes=15), now) and settings.chat_ai_configured:
            await queue_understanding(session, now)


async def queue_understanding(session: AsyncSession, now: datetime, limit: int = 50) -> None:
    """Cards whose reader/vision step failed, was capped, or predates the current pipeline get another try,
    at most once an hour each."""
    rows = await session.execute(text(
        "select id, content_hash from items where deleted_at is null and content_hash is not null "
        "and safety_state = 'ok' and index_state = 'ready' "
        "and (ai_hash is null or ai_hash <> content_hash || '@' || :pipeline) "
        "order by updated_at desc limit :limit"), {"pipeline": ingest.PIPELINE, "limit": limit})
    for item_id, content_hash in rows:
        await jobs.enqueue(session, "index_item", {"item_id": str(item_id), "hash": content_hash},
                           dedupe_key=f"understand:{item_id}:{content_hash}:{now:%Y%m%d%H}")
    await session.commit()


async def scheduler_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await tick()
        except Exception:
            log.exception("scheduler tick failed")
        try:
            await asyncio.wait_for(stop.wait(), TICK_S)
        except TimeoutError:
            pass


async def main() -> None:
    setup_logging(settings.log_level)
    await detect_capabilities()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    log.info("worker started", extra={"concurrency": CONCURRENCY, "vector": capabilities.vector})
    await asyncio.gather(scheduler_loop(stop), *(job_loop(stop) for _ in range(CONCURRENCY)))
    await engine.dispose()
    log.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
