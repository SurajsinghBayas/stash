from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_url, _connect_args = settings.async_database_url
engine = create_async_engine(
    _url,
    connect_args={**_connect_args, "timeout": 10, "command_timeout": 15},
    pool_size=settings.db_pool_size,
    max_overflow=0,
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


class Capabilities:
    """Database features detected at startup. Neon has pgvector; a bare local Postgres may not."""

    vector: bool = False


capabilities = Capabilities()


async def detect_capabilities() -> None:
    async with engine.connect() as conn:
        found = await conn.scalar(
            text(
                "select count(*) from information_schema.columns "
                "where table_name = 'items' and column_name = 'embedding'"
            )
        )
    capabilities.vector = bool(found)
