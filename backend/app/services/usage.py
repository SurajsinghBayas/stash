"""One monthly assistant allowance for every account.

The count lives in `ai_requests`, so chat, card reading, memory and digests share it,
and a restart does not reset it. The same limit applies to every user.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.models import AIRequest
from app.errors import AppError

ALLOWANCE_MESSAGE = "You've used this month's assistant allowance. It resets on the 1st."


class AllowanceUsed(AppError):
    status, code = 429, "ai_budget_exceeded"

    def __init__(self) -> None:
        super().__init__(ALLOWANCE_MESSAGE)


def month_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month(start: datetime) -> datetime:
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


async def tokens_used(session: AsyncSession, user_id: uuid.UUID, *, now: datetime | None = None) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(func.coalesce(AIRequest.input_tokens, 0)
                                      + func.coalesce(AIRequest.output_tokens, 0)), 0))
        .where(AIRequest.user_id == user_id, AIRequest.created_at >= month_start(now))
    )
    return int(total or 0)


async def over_allowance(session: AsyncSession, user_id: uuid.UUID) -> bool:
    return await tokens_used(session, user_id) >= settings.ai_monthly_token_budget


async def require_allowance(session: AsyncSession, user_id: uuid.UUID) -> None:
    if await over_allowance(session, user_id):
        raise AllowanceUsed()


async def snapshot(session: AsyncSession, user_id: uuid.UUID) -> dict:
    start = month_start()
    used = await tokens_used(session, user_id, now=start)
    return {
        "used_tokens": used,
        "limit_tokens": settings.ai_monthly_token_budget,
        "resets_at": next_month(start).isoformat(),
    }
