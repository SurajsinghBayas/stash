import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import Reminder, User
from app.db import get_session
from app.middleware.auth import current_user
from app.schemas import ReminderIn, ReminderOut, ReminderPatch, data, page
from app.services.reminders import service

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _out(r: Reminder) -> dict:
    return ReminderOut.model_validate(r).model_dump(mode="json")


@router.get("")
async def list_reminders(state: Literal["pending", "sent", "cancelled", "all"] = "pending",
                         canvas_id: uuid.UUID | None = None, limit: int = Query(50, ge=1, le=100),
                         cursor: int = Query(0, ge=0), user: User = Depends(current_user),
                         session: AsyncSession = Depends(get_session)):
    q = select(Reminder).where(Reminder.user_id == user.id)
    if state != "all":
        q = q.where(Reminder.state == state)
    if canvas_id:
        q = q.where(Reminder.canvas_id == canvas_id)
    order = Reminder.remind_at.asc() if state == "pending" else Reminder.remind_at.desc()
    rows = list(await session.scalars(q.order_by(order, Reminder.id).offset(cursor).limit(limit + 1)))
    next_cursor = str(cursor + limit) if len(rows) > limit else None
    return page([_out(r) for r in rows[:limit]], limit, next_cursor)


@router.post("", status_code=201)
async def create(body: ReminderIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return data(_out(await service.create(session, user.id, body.remind_at, body.item_id, body.note)))


@router.patch("/{reminder_id}")
async def update(reminder_id: uuid.UUID, body: ReminderPatch, user: User = Depends(current_user),
                 session: AsyncSession = Depends(get_session)):
    return data(_out(await service.update(session, user.id, reminder_id, body.remind_at, body.note)))


@router.delete("/{reminder_id}", status_code=204)
async def cancel(reminder_id: uuid.UUID, user: User = Depends(current_user),
                 session: AsyncSession = Depends(get_session)):
    await service.cancel(session, user.id, reminder_id)
