"""Tests run against a local Postgres database (`stash_test`) with every external provider turned off.

Environment variables override backend/.env, so no test can reach Neon, Mantle, Voyage, Bedrock, S3 or SMTP.
"""

import os
import subprocess
import sys
from pathlib import Path

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@/stash_test?host=/tmp")
os.environ.update({
    "APP_ENV": "test",
    "APP_URL": "http://localhost:5173",
    "DATABASE_URL": TEST_DB,
    "DATABASE_URL_DIRECT": TEST_DB,
    "JWT_SECRET": "test-secret-" + "x" * 40,
    "SAFETY_REQUIRED": "false",
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "VOYAGER_API_KEY": "",
    "SMTP_HOST": "",
    "S3_BUCKET": "",
    "AWS_ENDPOINT_URL_S3": "",
    "AWS_ACCESS_KEY_ID": "",
    "AWS_SECRET_ACCESS_KEY": "",
    "GOOGLE_CLIENT_ID": "",
    "X_CLIENT_ID": "",
    "LOCAL_UPLOAD_DIR": str(Path(__file__).parent / ".uploads"),
})

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.rate_limit import limiter  # noqa: E402
from app.services.mail import sender  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
TABLES = ("answer_cache", "memories", "embedding_cache", "chunks", "link_cache", "digest_runs", "reminders",
          "ai_requests", "moderation_events", "chat_messages", "jobs", "item_versions", "items", "canvases",
          "email_tokens", "refresh_tokens", "oauth_accounts", "users")


@pytest.fixture(scope="session", autouse=True)
def schema():
    import asyncio

    import asyncpg

    async def reset():
        conn = await asyncpg.connect(TEST_DB)
        await conn.execute("drop schema public cascade; create schema public;")
        await conn.close()

    asyncio.run(reset())
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True,
                   env={**os.environ, "ALEMBIC_DATABASE_URL": TEST_DB})
    yield


@pytest.fixture(autouse=True)
async def clean():
    async with engine.begin() as conn:
        await conn.execute(text(f"truncate {', '.join(TABLES)} restart identity cascade"))
    limiter.reset()
    sender.outbox.clear()
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:5173") as c:
        yield c


def link_from_outbox(path: str) -> str:
    for mail in reversed(sender.outbox):
        for word in mail["text"].split():
            if path in word:
                return word.split("token=", 1)[1]
    raise AssertionError(f"no {path} link in outbox")


async def make_user(client: AsyncClient, email: str = "ada@example.com", password: str = "correct horse 1") -> dict:
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    await drain()
    token = link_from_outbox("/verify-email")
    r = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def drain(limit: int = 50) -> int:
    """Run queued jobs inline, like the worker would."""
    from app.worker import run_one

    done = 0
    while done < limit and await run_one():
        done += 1
    return done


@pytest.fixture
async def user(client):
    return await make_user(client)


@pytest.fixture
async def canvas(client, user):
    r = await client.post("/api/v1/canvases", json={"title": "Research"})
    assert r.status_code == 201, r.text
    return r.json()["data"]
