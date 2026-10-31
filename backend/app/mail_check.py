"""Check that email works end to end: `python -m app.mail_check you@example.com`.

1. Connects and signs in to the SMTP server (fails fast with the server's reason if the login is wrong).
2. If the address belongs to an account: creates a reminder due now and runs it through the real pipeline
   (scheduler → job → reminder email), exactly like a reminder set in the app.
   Otherwise: sends the reminder email template straight to the address.
Prints what happened. Never prints the SMTP password.
"""

import asyncio
import smtplib
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.config import settings
from app.data.models import Reminder, User
from app.db import SessionLocal, engine
from app.services.mail import sender, templates


def check_login() -> bool:
    if not settings.smtp_host:
        print("SMTP_HOST is not set: emails are only printed to the worker log (development mode).")
        return False
    print(f"SMTP: {settings.smtp_host}:{settings.smtp_port} as {settings.smtp_user!r}, from {settings.mail_from!r}")
    try:
        if settings.smtp_port == 465:
            client = smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=20)
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
            client.starttls()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password or "")
        client.quit()
    except smtplib.SMTPAuthenticationError as exc:
        print(f"SMTP login FAILED: {exc.smtp_code} {exc.smtp_error.decode(errors='replace')[:300]}")
        return False
    except Exception as exc:  # noqa: BLE001 - report any connection problem as-is
        print(f"SMTP connection FAILED: {type(exc).__name__}: {exc}")
        return False
    print("SMTP login OK")
    return True


async def run(address: str) -> int:
    from app.worker import run_one, tick

    if not check_login() and settings.smtp_host:
        return 1
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(func.lower(User.email) == address.lower()))
        if user is None:
            mail = templates.reminder("Test reminder", "If you can read this, Stash email works.", "", "Stash",
                                      f"{settings.app_url}/app")
            await sender.send(address, mail.subject, mail.html, mail.text)
            print(f"No account uses {address}; sent the reminder template directly. Check the inbox (and spam).")
            return 0
        reminder = Reminder(user_id=user.id, remind_at=datetime.now(UTC), state="pending",
                            note="Test reminder: if you can read this, Stash reminders work.")
        session.add(reminder)
        await session.commit()
        reminder_id = reminder.id

    await tick()  # the scheduler queues the due reminder
    state = "pending"
    for _ in range(60):  # run queued jobs until ours is done; a running worker may pick it up instead
        async with SessionLocal() as session:
            state = await session.scalar(select(Reminder.state).where(Reminder.id == reminder_id))
        if state != "pending":
            break
        if not await run_one():
            await asyncio.sleep(1)
    where = "Check the inbox (and spam)." if settings.smtp_host else "It was printed to the log (no SMTP_HOST)."
    print(f"Reminder {reminder_id}: {state}.", where if state == "sent" else
          "Not sent: see the job's last_error in the jobs table, or the log above.")
    await engine.dispose()
    return 0 if state == "sent" else 1


if __name__ == "__main__":
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        sys.exit("usage: python -m app.mail_check you@example.com")
    sys.exit(asyncio.run(run(sys.argv[1])))
