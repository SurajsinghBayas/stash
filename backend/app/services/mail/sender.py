"""SMTP (SES) in production; in development without SMTP_HOST, emails are written to the log instead."""

import logging
from email.message import EmailMessage
from email.utils import make_msgid

import aiosmtplib

from app.config import settings

log = logging.getLogger("stash.mail")

# Development only: the last messages, so tests and the dev console can read links.
outbox: list[dict] = []


async def send(to: str, subject: str, html: str, text: str, headers: dict[str, str] | None = None) -> None:
    if not settings.mail_enabled:
        if settings.is_production:
            raise RuntimeError("SMTP is not configured")
        outbox.append({"to": to, "subject": subject, "html": html, "text": text, "headers": headers or {}})
        del outbox[:-50]
        log.info("email (dev console)", extra={"to": to, "subject": subject, "body": text})
        return

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=settings.mail_from.rsplit("@", 1)[-1].strip("> "))
    for key, value in (headers or {}).items():
        message[key] = value
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=settings.smtp_port == 587,
        use_tls=settings.smtp_port == 465,
        timeout=10,
    )
