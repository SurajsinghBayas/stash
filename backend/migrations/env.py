"""Alembic runs against DATABASE_URL_DIRECT (Neon's non-pooled URL) when set, else DATABASE_URL."""

import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import _asyncpg_url, settings

url = os.environ.get("ALEMBIC_DATABASE_URL") or settings.database_url_direct or settings.database_url


def run_offline() -> None:
    context.configure(url=_asyncpg_url(url)[0], literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    async_url, connect_args = _asyncpg_url(url)
    engine = create_async_engine(async_url, connect_args=connect_args)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
        await conn.commit()
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
