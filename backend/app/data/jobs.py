"""Postgres-backed job queue. `enqueue` joins the caller's transaction, so a job exists only if the write did."""

import json
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_ATTEMPTS = 5


async def enqueue(session: AsyncSession, kind: str, payload: dict, *, dedupe_key: str | None = None,
                  run_after: datetime | None = None) -> None:
    await session.execute(
        text(
            "insert into jobs (kind, payload, dedupe_key, run_after) "
            "values (:kind, cast(:payload as jsonb), :dedupe, coalesce(:run_after, now())) "
            "on conflict (dedupe_key) do nothing"
        ),
        {"kind": kind, "payload": json.dumps(payload, default=str), "dedupe": dedupe_key, "run_after": run_after},
    )


async def claim(session: AsyncSession) -> dict | None:
    row = (
        await session.execute(
            text(
                "update jobs set state = 'running', attempts = attempts + 1, locked_at = now(), updated_at = now() "
                "where id = (select id from jobs where state = 'queued' and run_after <= now() "
                "            order by run_after, id for update skip locked limit 1) "
                "returning id, kind, payload, attempts"
            )
        )
    ).mappings().first()
    await session.commit()
    return dict(row) if row else None


async def complete(session: AsyncSession, job_id: int) -> None:
    await session.execute(text("update jobs set state = 'done', updated_at = now() where id = :id"), {"id": job_id})
    await session.commit()


async def fail(session: AsyncSession, job_id: int, attempts: int, error: str, *,
               retry_in: timedelta | None = None) -> None:
    dead = attempts >= MAX_ATTEMPTS
    delay = retry_in or timedelta(seconds=min(3600, 15 * 2 ** attempts))
    await session.execute(
        text(
            "update jobs set state = :state, last_error = :err, run_after = now() + :delay, "
            "locked_at = null, updated_at = now() where id = :id"
        ),
        {"state": "dead" if dead else "queued", "err": error[:2000], "delay": delay, "id": job_id},
    )
    await session.commit()


async def recover_stuck(session: AsyncSession) -> int:
    """Jobs left `running` by a crashed worker go back to the queue."""
    result = await session.execute(
        text("update jobs set state = 'queued', locked_at = null "
             "where state = 'running' and locked_at < now() - interval '10 minutes'")
    )
    await session.commit()
    return result.rowcount or 0


async def prune(session: AsyncSession) -> None:
    await session.execute(text("delete from jobs where state = 'done' and updated_at < now() - interval '7 days'"))
    await session.commit()
