"""Save by email. Mail sent to save+<token>@INBOUND_EMAIL_DOMAIN reaches this endpoint through a forwarder
(deploy/inbound-email-worker.js) that posts the raw message with the shared INBOUND_SECRET.

A message is saved only when the address token matches an account AND the sender is that account's verified email,
so a leaked address alone is not enough to write into someone's canvas. Links become link cards, the rest a note,
on the person's "Inbox" canvas. Everything then goes through the same safety check and indexing as typed cards.
"""

import email
import hmac
import html
import re
from email.message import EmailMessage
from email.policy import default as default_policy
from email.utils import getaddresses, parseaddr

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.models import Canvas, Item, User
from app.db import get_session
from app.errors import AppError, Forbidden, NotFound
from app.middleware.rate_limit import limiter
from app.schemas import ItemIn, data
from app.services.items import service as items

router = APIRouter(prefix="/inbound", tags=["inbound"])

MAX_BYTES = 5 * 1024 * 1024
MAX_LINKS = 5
NOTE_MAX = 8000
INBOX_TITLE = "Inbox"
ADDRESS = re.compile(r"^save\+([a-f0-9]{20})@", re.I)
URL = re.compile(r"https?://[^\s<>\"'()\[\]]+", re.I)
SKIP_URL = re.compile(r"unsubscribe|/track/|mailchi\.mp/|list-manage\.com", re.I)


def _token(recipients: list[str]) -> str | None:
    for address in recipients:
        match = ADDRESS.match(address.strip().lower())
        if match:
            return match.group(1)
    return None


def _html_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|head).*?</\1>", " ", markup)
    markup = re.sub(r'(?is)<a\s[^>]*href="(https?://[^"]+)"[^>]*>', r" \1 ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", markup)
    return html.unescape(re.sub(r"<[^>]+>", " ", markup))


def _body(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        content = part.get_content()
    except (LookupError, UnicodeError):
        return ""
    if part.get_content_type() == "text/html":
        content = _html_text(content)
    lines = []
    for line in content.replace("\r\n", "\n").split("\n"):
        if line.strip() in ("--", "-- "):
            break  # signature
        if line.lstrip().startswith(">"):
            continue  # quoted reply
        lines.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _links(text: str) -> list[str]:
    found: list[str] = []
    for url in URL.findall(text):
        url = url.rstrip(".,;:!?*_")
        if len(url) <= 2048 and not SKIP_URL.search(url) and url not in found:
            found.append(url)
    return found[:MAX_LINKS]


async def _inbox(session: AsyncSession, user: User) -> Canvas:
    canvas = await session.scalar(select(Canvas).where(Canvas.owner_id == user.id, Canvas.title == INBOX_TITLE,
                                                       Canvas.deleted_at.is_(None)).order_by(Canvas.created_at))
    if not canvas:
        canvas = Canvas(owner_id=user.id, title=INBOX_TITLE)
        session.add(canvas)
        await session.commit()
        await session.refresh(canvas)
    return canvas


@router.post("/email", status_code=202)
async def receive(request: Request, session: AsyncSession = Depends(get_session)):
    secret = settings.inbound_secret
    if not (secret and settings.inbound_email_domain):
        raise NotFound("Not found")
    if not hmac.compare_digest(request.headers.get("x-inbound-secret", "").encode(), secret.encode()):
        raise Forbidden("Not allowed")
    raw = await request.body()
    if len(raw) > MAX_BYTES:
        raise AppError("Message is too large", code="too_large", status=413)
    msg = email.message_from_bytes(raw, policy=default_policy)
    assert isinstance(msg, EmailMessage)

    # The forwarder passes the envelope; the headers are a fallback for forwarders that don't.
    recipients = [request.headers.get("x-inbound-to", "")]
    recipients += [a for _, a in getaddresses(msg.get_all("to", []) + msg.get_all("delivered-to", []))]
    token = _token(recipients)
    sender = (request.headers.get("x-inbound-from") or parseaddr(str(msg.get("from", "")))[1]).strip().lower()
    user = await session.scalar(select(User).where(User.inbound_token == token)) if token else None
    if not user or user.suspended_at or not user.email_verified or (user.email or "").lower() != sender:
        raise NotFound("Unknown address, or the sender isn't the account's email.")
    limiter.hit(f"inbound:{user.id}", 60, 3600)

    subject = " ".join(str(msg.get("subject", "")).split())[:300]
    body = _body(msg)
    links = _links(f"{subject}\n{body}")
    rest = URL.sub("", body).strip()

    canvas = await _inbox(session, user)
    bottom = await session.scalar(select(func.max(Item.y + func.coalesce(Item.h, 240))).where(
        Item.canvas_id == canvas.id, Item.deleted_at.is_(None)))
    y = float(bottom) + 60 if bottom is not None else 0.0
    saved = 0
    for i, url in enumerate(links):
        await items.create_item(session, user.id, canvas.id, ItemIn(
            kind="link", x=i * 300, y=y, content={"url": url, "comment": subject if not rest else ""}))
        saved += 1
    if rest or not links:
        markdown = f"**{subject or 'Saved by email'}**\n\n{rest}".strip()[:NOTE_MAX]
        await items.create_item(session, user.id, canvas.id, ItemIn(
            kind="note", x=0, y=y + (300 if links else 0), w=420, content={"markdown": markdown, "color": "blue"}))
        saved += 1
    return data({"saved": saved, "canvas_id": str(canvas.id)})
