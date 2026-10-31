from datetime import UTC, datetime, timedelta

from conftest import drain, make_user
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.main import app
from app.services.digests import service as digests
from app.services.mail import sender
from app.services.reminders.service import queue_due


async def _set(sql: str, **params) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


async def test_reminder_sends_once(client, canvas):
    item = (await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                              json={"kind": "text", "x": 0, "y": 0, "content": {"text": "Renew passport"}})).json()
    soon = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    r = await client.post("/api/v1/reminders", json={"remind_at": soon, "item_id": item["data"]["id"],
                                                     "note": "Book the appointment"})
    assert r.status_code == 201, r.text
    rid = r.json()["data"]["id"]
    await drain()
    sender.outbox.clear()

    await _set("update reminders set remind_at = now() - interval '1 minute' where id = :id", id=rid)
    async with SessionLocal() as s:
        assert await queue_due(s) == 1
    await drain()
    assert len(sender.outbox) == 1
    mail = sender.outbox[0]
    assert mail["subject"] == "Reminder: Book the appointment" and "Renew passport" in mail["text"]

    async with SessionLocal() as s:
        assert await queue_due(s) == 0
    await drain()
    assert len(sender.outbox) == 1
    state = (await client.get("/api/v1/reminders", params={"state": "sent"})).json()["data"][0]["state"]
    assert state == "sent"


async def test_reminder_validation_and_cancel(client, canvas):
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    assert (await client.post("/api/v1/reminders", json={"remind_at": past, "note": "x"})).status_code == 400
    naive = (datetime.now() + timedelta(days=1)).replace(tzinfo=None).isoformat()
    assert (await client.post("/api/v1/reminders", json={"remind_at": naive, "note": "x"})).status_code == 400
    soon = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert (await client.post("/api/v1/reminders", json={"remind_at": soon})).status_code == 400

    rid = (await client.post("/api/v1/reminders", json={"remind_at": soon, "note": "call"})).json()["data"]["id"]
    assert (await client.delete(f"/api/v1/reminders/{rid}")).status_code == 204
    await _set("update reminders set remind_at = now() - interval '1 minute' where id = :id", id=rid)
    async with SessionLocal() as s:
        assert await queue_due(s) == 0


async def test_flagged_card_text_never_goes_into_a_reminder(client, canvas):
    item = (await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                              json={"kind": "text", "x": 0, "y": 0, "content": {"text": "you are stupid"}})).json()
    soon = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    rid = (await client.post("/api/v1/reminders", json={"remind_at": soon, "item_id": item["data"]["id"]})
           ).json()["data"]["id"]
    await drain()
    sender.outbox.clear()
    await _set("update reminders set remind_at = now() - interval '1 minute' where id = :id", id=rid)
    async with SessionLocal() as s:
        await queue_due(s)
    await drain()
    assert "stupid" not in sender.outbox[0]["text"]


MONDAY_8AM = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)


async def test_daily_and_weekly_digest_once_per_period(client, canvas, user):
    await client.patch("/api/v1/users/me", json={"timezone": "UTC", "digest_hour": 8})
    await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                      json={"kind": "note", "x": 0, "y": 0, "content": {"markdown": "Pricing ideas for launch"}})
    await drain()
    await _set("update items set updated_at = :t", t=datetime(2026, 11, 1, 12, 0, tzinfo=UTC))
    sender.outbox.clear()

    async with SessionLocal() as s:
        assert await digests.schedule(s, MONDAY_8AM) == 2  # Monday: daily (Sunday) + weekly
        assert await digests.schedule(s, MONDAY_8AM + timedelta(minutes=5)) == 0
    await drain()
    subjects = sorted(m["subject"] for m in sender.outbox)
    assert subjects == ["Your day in Stash: 1 card noted", "Your week in Stash: 1 card noted"]
    digest = sender.outbox[0]
    assert "Pricing ideas for launch" in digest["text"] or "Pricing ideas for launch" in digest["html"]
    assert digest["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


async def test_no_email_for_an_empty_period_or_wrong_hour(client, user):
    await client.patch("/api/v1/users/me", json={"timezone": "UTC", "digest_hour": 8})
    async with SessionLocal() as s:
        assert await digests.schedule(s, MONDAY_8AM.replace(hour=9)) == 0
        assert await digests.schedule(s, MONDAY_8AM) == 2
    sender.outbox.clear()
    await drain()
    assert sender.outbox == []


async def test_digest_respects_user_timezone(client, user):
    await client.patch("/api/v1/users/me", json={"timezone": "Asia/Kolkata", "digest_hour": 8})
    async with SessionLocal() as s:
        # 08:00 in Kolkata is 02:30 UTC.
        assert await digests.schedule(s, datetime(2026, 11, 3, 2, 30, tzinfo=UTC)) == 1
        assert await digests.schedule(s, datetime(2026, 11, 3, 8, 0, tzinfo=UTC)) == 0


async def test_unsubscribe_link_turns_off_one_digest(client, user):
    from app.routes.users import unsubscribe_token

    token = unsubscribe_token(user["id"], "daily")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:5173") as anon:
        assert (await anon.get("/api/v1/email/unsubscribe", params={"token": token})).status_code == 200
        r = await anon.post("/api/v1/email/unsubscribe", params={"token": token},
                            headers={"Origin": "https://mail.example"})
        assert r.status_code == 204
    me = (await client.get("/api/v1/users/me")).json()["data"]
    assert me["digest_daily"] is False and me["digest_weekly"] is True


async def test_other_users_reminders_are_hidden(client, canvas):
    soon = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    rid = (await client.post("/api/v1/reminders", json={"remind_at": soon, "note": "mine"})).json()["data"]["id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:5173") as other:
        await make_user(other, "eve@example.com")
        assert (await other.delete(f"/api/v1/reminders/{rid}")).status_code == 404
        assert (await other.get("/api/v1/reminders")).json()["data"] == []


async def test_deleting_a_canvas_cancels_its_reminders_and_cards(client, canvas):
    item = (await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                              json={"kind": "text", "x": 0, "y": 0, "content": {"text": "on the canvas"}})).json()
    soon = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    await client.post("/api/v1/reminders", json={"remind_at": soon, "item_id": item["data"]["id"]})
    assert (await client.delete(f"/api/v1/canvases/{canvas['id']}")).status_code == 204
    assert (await client.get("/api/v1/reminders")).json()["data"] == []
    assert (await client.get("/api/v1/search", params={"q": "canvas"})).json()["data"] == []
    async with engine.connect() as conn:
        assert await conn.scalar(text("select count(*) from items where deleted_at is null")) == 0
