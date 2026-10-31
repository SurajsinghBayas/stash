"""Admin panel: the seeded account, who can read the metrics, and that the numbers add up."""

from contextlib import asynccontextmanager

import pytest
from conftest import drain
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services.admin import seed_admin

ADMIN_EMAIL, ADMIN_PASSWORD = "admin@example.com", "a long admin password"


@pytest.fixture
async def seeded(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", ADMIN_EMAIL)
    monkeypatch.setattr(settings, "admin_password", ADMIN_PASSWORD)
    await seed_admin()


@asynccontextmanager
async def _admin_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:5173",
                           headers={"Origin": "http://localhost:5173"}) as c:
        r = await c.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        yield c


async def test_seeded_admin_can_sign_in_and_read_metrics(seeded, client, user):
    cid = (await client.post("/api/v1/canvases", json={"title": "Plans"})).json()["data"]["id"]
    for kind, content in [("note", {"markdown": "hello"}), ("note", {"markdown": "again"}),
                          ("link", {"url": "https://example.com/"})]:
        await client.post(f"/api/v1/canvases/{cid}/items", json={"kind": kind, "x": 0, "y": 0, "content": content})
    await drain()

    async with _admin_client() as admin:
        me = (await admin.get("/api/v1/users/me")).json()["data"]
        assert me["is_admin"] is True
        r = await admin.get("/api/v1/admin/metrics")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    m = r.json()["data"]
    assert m["totals"]["users"] == 2 and m["totals"]["canvases"] == 1 and m["totals"]["cards"] == 3
    assert {k["kind"]: k["count"] for k in m["cards_by_kind"]} == {"note": 2, "link": 1}
    assert len(m["daily"]) == 30 and m["daily"][-1]["cards"] == 3 and m["daily"][-1]["signups"] == 2
    assert m["active"]["dau"] >= 1
    assert any(u["email"] == "ada@example.com" for u in m["recent_users"])


async def test_everyone_else_gets_not_found(seeded, client, user):
    me = (await client.get("/api/v1/users/me")).json()["data"]
    assert me["is_admin"] is False
    assert (await client.get("/api/v1/admin/metrics")).status_code == 404
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:5173") as anon:
        assert (await anon.get("/api/v1/admin/metrics")).status_code == 401


async def test_no_admin_configured_means_no_admin(monkeypatch, client, user):
    monkeypatch.setattr(settings, "admin_email", None)
    assert (await client.get("/api/v1/admin/metrics")).status_code == 404


async def test_seeding_is_idempotent_and_a_new_password_signs_the_admin_out(seeded, monkeypatch):
    await seed_admin()  # second start: nothing changes, the session stays
    async with _admin_client() as admin:
        monkeypatch.setattr(settings, "admin_password", "a different long password")
        await seed_admin()
        admin.cookies.delete("stash_at")  # access token expires; the refresh token must no longer work
        r = await admin.post("/api/v1/auth/refresh")
        assert r.status_code == 401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:5173") as c:
        r = await c.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 401
