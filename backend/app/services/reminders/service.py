import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.jobs import enqueue
from app.data.models import Item, Reminder
from app.errors import NotFound, ValidationFailed

MIN_LEAD = timedelta(seconds=30)
MAX_LEAD = timedelta(days=366)


def _check_time(remind_at: datetime) -> datetime:
    if remind_at.tzinfo is None:
        raise ValidationFailed("remind_at: include a time zone offset, e.g. 2026-11-02T09:00:00+05:30")
    remind_at = remind_at.astimezone(UTC)
    now = datetime.now(UTC)
    if remind_at < now + MIN_LEAD:
        raise ValidationFailed("remind_at: pick a time in the future")
    if remind_at > now + MAX_LEAD:
        raise ValidationFailed("remind_at: reminders can be at most a year ahead")
    return remind_at


async def create(session: AsyncSession, user_id: uuid.UUID, remind_at: datetime, item_id: uuid.UUID | None,
                 note: str) -> Reminder:
    canvas_id = None
    if item_id:
        item = await session.scalar(select(Item).where(Item.id == item_id, Item.owner_id == user_id,
                                                       Item.deleted_at.is_(None)))
        if not item:
            raise NotFound("Card not found")
        canvas_id = item.canvas_id
    elif not note:
        raise ValidationFailed("note: add a note or pick a card")
    pending = await session.scalar(text("select count(*) from reminders where user_id = :u and state = 'pending'"),
                                   {"u": user_id})
    if pending >= 500:
        raise ValidationFailed("You have 500 pending reminders. Clear some first.", code="too_many_reminders")
    reminder = Reminder(user_id=user_id, item_id=item_id, canvas_id=canvas_id, note=note,
                        remind_at=_check_time(remind_at))
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    return reminder


async def get(session: AsyncSession, user_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder:
    reminder = await session.scalar(select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id))
    if not reminder:
        raise NotFound("Reminder not found")
    return reminder


async def update(session: AsyncSession, user_id: uuid.UUID, reminder_id: uuid.UUID, remind_at: datetime | None,
                 note: str | None) -> Reminder:
    reminder = await get(session, user_id, reminder_id)
    if remind_at is not None:
        reminder.remind_at = _check_time(remind_at)
        reminder.state = "pending"  # rescheduling a sent reminder sets it again
        reminder.sent_at = None
    if note is not None:
        reminder.note = note
    await session.commit()
    await session.refresh(reminder)
    return reminder


async def cancel(session: AsyncSession, user_id: uuid.UUID, reminder_id: uuid.UUID) -> None:
    reminder = await get(session, user_id, reminder_id)
    if reminder.state == "pending":
        reminder.state = "cancelled"
        await session.commit()


async def queue_due(session: AsyncSession) -> int:
    """Scheduler tick. The dedupe key includes the time, so a rescheduled reminder sends again, but a reminder
    never sends twice for the same time even with two workers."""
    rows = (await session.execute(
        text("select id, remind_at from reminders where state = 'pending' and remind_at <= now() "
             "order by remind_at limit 200")
    )).all()
    for row in rows:
        stamp = int(row.remind_at.timestamp())
        await enqueue(session, "send_email", {"template": "reminder", "reminder_id": str(row.id), "at": stamp},
                      dedupe_key=f"reminder:{row.id}:{stamp}")
    await session.commit()
    return len(rows)
