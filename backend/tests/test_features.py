"""Templates, sharing, card history, trash and purge, export, account deletion, save by email, chat actions."""

from datetime import UTC, datetime, timedelta

from conftest import drain, make_user
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.config import settings
from app.data.models import ChatMessage, Item, User
from app.db import SessionLocal, engine
from app.main import app
from app.services.mail import sender


async def _note(client, cid: str, markdown: str = "first draft", **extra) -> dict:
    r = await client.post(f"/api/v1/canvases/{cid}/items",
                          json={"kind": "note", "x": 0, "y": 0, "content": {"markdown": markdown}, **extra})
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _edit(client, cid: str, item: dict, markdown: str) -> dict:
    r = await client.patch(f"/api/v1/canvases/{cid}/items",
                           json={"items": [{"id": item["id"], "version": item["version"],
                                            "content": {"markdown": markdown}}]})
    return r.json()["data"]["updated"][0]


# ---------- templates ----------

async def test_templates_create_starter_cards(client, user):
    keys = [t["key"] for t in (await client.get("/api/v1/canvases/templates")).json()["data"]]
    assert "trip" in keys and "reading-list" in keys
    r = await client.post("/api/v1/canvases", json={"title": "Untitled", "template": "trip"})
    assert r.status_code == 201, r.text
    canvas = r.json()["data"]
    assert canvas["title"] == "Trip planner"
    cards = (await client.get(f"/api/v1/canvases/{canvas['id']}/items")).json()["data"]
    assert len(cards) == 6 and {c["kind"] for c in cards} == {"note", "text"}
    r = await client.post("/api/v1/canvases", json={"title": "x", "template": "nope"})
    assert r.status_code == 400


# ---------- sharing ----------

async def test_share_link_is_read_only_and_hides_unchecked_cards(client, canvas):
    cid = canvas["id"]
    await _note(client, cid, "Ship v1 on Friday")
    await client.post(f"/api/v1/canvases/{cid}/items",
                      json={"kind": "note", "x": 0, "y": 0, "content": {"markdown": "honestly you are stupid"}})
    await drain()
    await _note(client, cid, "not checked yet")  # no drain: still "unchecked"

    share = (await client.post(f"/api/v1/canvases/{cid}/share")).json()["data"]
    assert share["url"].endswith(f"/s/{share['token']}")
    again = (await client.post(f"/api/v1/canvases/{cid}/share")).json()["data"]
    assert again["token"] == share["token"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:5173") as anon:
        r = await anon.get(f"/api/v1/public/canvases/{share['token']}")
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["title"] == "Research"
        assert [c["content"]["markdown"] for c in body["items"]] == ["Ship v1 on Friday"]
        assert "owner_id" not in body["items"][0] and "canvas_id" not in body["items"][0]
        # Nothing to write with: the owner API still needs a session.
        assert (await anon.get(f"/api/v1/canvases/{cid}/items")).status_code == 401

        assert (await client.delete(f"/api/v1/canvases/{cid}/share")).status_code == 204
        assert (await anon.get(f"/api/v1/public/canvases/{share['token']}")).status_code == 404
        assert (await anon.get("/api/v1/public/canvases/short")).status_code == 404


async def test_deleted_canvas_is_no_longer_shared(client, canvas):
    token = (await client.post(f"/api/v1/canvases/{canvas['id']}/share")).json()["data"]["token"]
    await client.delete(f"/api/v1/canvases/{canvas['id']}")
    assert (await client.get(f"/api/v1/public/canvases/{token}")).status_code == 404
    await client.post(f"/api/v1/canvases/{canvas['id']}/restore")
    assert (await client.get(f"/api/v1/public/canvases/{token}")).status_code == 404


# ---------- history ----------

async def test_versions_record_edits_and_restore(client, canvas):
    cid = canvas["id"]
    note = await _note(client, cid, "first draft")
    note = await _edit(client, cid, note, "second draft")
    # Moving a card is not history.
    r = await client.patch(f"/api/v1/canvases/{cid}/items",
                           json={"items": [{"id": note["id"], "version": note["version"], "x": 50}]})
    note = r.json()["data"]["updated"][0]
    versions = (await client.get(f"/api/v1/items/{note['id']}/versions")).json()["data"]
    assert [v["content"]["markdown"] for v in versions] == ["first draft"]

    # Edits within a couple of minutes are one entry (autosave sends many patches).
    note = await _edit(client, cid, note, "third draft")
    versions = (await client.get(f"/api/v1/items/{note['id']}/versions")).json()["data"]
    assert len(versions) == 1

    # A stale tab cannot restore over newer edits.
    r = await client.post(f"/api/v1/items/{note['id']}/versions/{versions[0]['id']}/restore",
                          json={"version": note["version"] - 1})
    assert r.status_code == 409
    r = await client.post(f"/api/v1/items/{note['id']}/versions/{versions[0]['id']}/restore",
                          json={"version": note["version"]})
    assert r.status_code == 200, r.text
    restored = r.json()["data"]
    assert restored["content"]["markdown"] == "first draft" and restored["version"] == note["version"] + 1
    # Restoring is itself undoable: the text it replaced is now in history.
    versions = (await client.get(f"/api/v1/items/{note['id']}/versions")).json()["data"]
    assert versions[0]["content"]["markdown"] == "third draft"


async def test_versions_are_private(client, canvas):
    note = await _note(client, canvas["id"])
    client.cookies.clear()
    await make_user(client, "eve@example.com")
    assert (await client.get(f"/api/v1/items/{note['id']}/versions")).status_code == 404


# ---------- trash ----------

async def test_card_trash_and_restore(client, canvas):
    cid = canvas["id"]
    note = await _note(client, cid, "keep me")
    await client.delete(f"/api/v1/items/{note['id']}")
    trash = (await client.get(f"/api/v1/canvases/{cid}/trash")).json()["data"]
    assert [t["id"] for t in trash] == [note["id"]]
    r = await client.post(f"/api/v1/items/{note['id']}/restore")
    assert r.status_code == 200, r.text
    assert [i["id"] for i in (await client.get(f"/api/v1/canvases/{cid}/items")).json()["data"]] == [note["id"]]
    assert (await client.get(f"/api/v1/canvases/{cid}/trash")).json()["data"] == []
    assert (await client.post(f"/api/v1/items/{note['id']}/restore")).status_code == 404


async def test_canvas_trash_restores_its_cards_only(client, canvas):
    cid = canvas["id"]
    gone_before = await _note(client, cid, "deleted earlier")
    await client.delete(f"/api/v1/items/{gone_before['id']}")
    kept = await _note(client, cid, "on the canvas")
    await client.delete(f"/api/v1/canvases/{cid}")
    assert (await client.post(f"/api/v1/items/{kept['id']}/restore")).status_code == 404  # canvas first

    trash = (await client.get("/api/v1/canvases/trash")).json()["data"]
    assert trash[0]["id"] == cid and trash[0]["item_count"] == 1
    assert (await client.post(f"/api/v1/canvases/{cid}/restore")).status_code == 200
    ids = [i["id"] for i in (await client.get(f"/api/v1/canvases/{cid}/items")).json()["data"]]
    assert ids == [kept["id"]]
    assert [t["id"] for t in (await client.get(f"/api/v1/canvases/{cid}/trash")).json()["data"]] == [gone_before["id"]]


async def test_purge_removes_old_trash_and_queues_file_deletes(client, canvas):
    from app.worker import purge_deleted

    cid = canvas["id"]
    old = await _note(client, cid, "old")
    recent = await _note(client, cid, "recent")
    alive = await _note(client, cid, "alive")
    await client.delete(f"/api/v1/items/{old['id']}")
    await client.delete(f"/api/v1/items/{recent['id']}")
    other = (await client.post("/api/v1/canvases", json={"title": "Old canvas"})).json()["data"]
    await _note(client, other["id"], "in old canvas")
    await client.delete(f"/api/v1/canvases/{other['id']}")
    async with engine.begin() as conn:
        await conn.execute(text("update items set deleted_at = now() - interval '31 days' where id = :i"),
                           {"i": old["id"]})
        await conn.execute(text("update canvases set deleted_at = now() - interval '31 days' where id = :c"),
                           {"c": other["id"]})
        # An image in the purged canvas: its files must be queued for deletion.
        await conn.execute(text(
            "insert into items (canvas_id, owner_id, kind, x, y, content, deleted_at) "
            "select :c, owner_id, 'image', 0, 0, '{\"storage_key\": \"u/a.png\", \"thumb_key\": \"u/a.t.webp\"}', "
            "now() - interval '40 days' from canvases where id = :c"), {"c": other["id"]})

    async with SessionLocal() as session:
        assert await purge_deleted(session, datetime.now(UTC)) == 3
    async with engine.begin() as conn:
        left = {str(r[0]) for r in await conn.execute(text("select id from items"))}
        canvases = {str(r[0]) for r in await conn.execute(text("select id from canvases"))}
        jobs = [r[0] for r in await conn.execute(text("select payload from jobs where kind = 'delete_objects'"))]
    assert left == {recent["id"], alive["id"]}
    assert canvases == {cid}
    assert jobs == [{"keys": ["u/a.png", "u/a.t.webp"]}]
    await drain()  # the delete job runs against local storage and succeeds for missing files


# ---------- export and account deletion ----------

async def test_export_contains_everything(client, canvas):
    await _note(client, canvas["id"], "exported note")
    r = await client.get("/api/v1/users/me/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    body = r.json()
    assert body["account"]["email"] == "ada@example.com"
    assert body["canvases"][0]["title"] == "Research"
    assert body["cards"][0]["content"]["markdown"] == "exported note"
    assert "password_hash" not in str(body)


async def test_delete_account_requires_password_and_removes_everything(client, canvas):
    await _note(client, canvas["id"])
    r = await client.request("DELETE", "/api/v1/users/me", json={"confirm": "DELETE", "password": "wrong password"})
    assert r.status_code == 403
    r = await client.request("DELETE", "/api/v1/users/me", json={"confirm": "nope", "password": "correct horse 1"})
    assert r.status_code == 400
    r = await client.request("DELETE", "/api/v1/users/me", json={"confirm": "DELETE", "password": "correct horse 1"})
    assert r.status_code == 204, r.text
    async with engine.begin() as conn:
        assert (await conn.execute(text("select count(*) from users"))).scalar() == 0
        assert (await conn.execute(text("select count(*) from items"))).scalar() == 0
    assert (await client.get("/api/v1/users/me")).status_code == 401
    r = await client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "correct horse 1"})
    assert r.status_code == 401


# ---------- save by email ----------

def _mime(sender_: str, to: str, subject: str, body: str) -> bytes:
    return (f"From: Ada <{sender_}>\r\nTo: {to}\r\nSubject: {subject}\r\nMessage-ID: <1@x>\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n\r\n{body}\r\n").encode()


async def test_save_by_email(client, user, monkeypatch):
    assert (await client.get("/api/v1/users/me/inbound")).json()["data"] == {"enabled": False, "address": None}
    monkeypatch.setattr(settings, "inbound_email_domain", "in.stash.test")
    monkeypatch.setattr(settings, "inbound_secret", "s" * 32)
    address = (await client.post("/api/v1/users/me/inbound")).json()["data"]["address"]
    assert address.startswith("save+") and address.endswith("@in.stash.test")
    headers = {"X-Inbound-Secret": "s" * 32, "X-Inbound-To": address}

    body = "Read this later https://example.com/article. And this: https://example.org/b\n\nGood for the launch.\n" \
           "-- \nAda's signature https://ada.example"
    raw = _mime("ada@example.com", address, "Two links", body)
    assert (await client.post("/api/v1/inbound/email", content=raw,
                              headers={**headers, "X-Inbound-Secret": "wrong"})).status_code == 403
    # Right address, wrong sender: a leaked address alone cannot write into the account.
    stranger = _mime("eve@example.com", address, "spam", "https://evil.example")
    r = await client.post("/api/v1/inbound/email", content=stranger,
                          headers={**headers, "X-Inbound-From": "eve@example.com"})
    assert r.status_code == 404

    r = await client.post("/api/v1/inbound/email", content=raw,
                          headers={**headers, "X-Inbound-From": "ADA@example.com"})
    assert r.status_code == 202, r.text
    assert r.json()["data"]["saved"] == 3
    canvases = (await client.get("/api/v1/canvases")).json()["data"]
    inbox = next(c for c in canvases if c["title"] == "Inbox")
    cards = (await client.get(f"/api/v1/canvases/{inbox['id']}/items")).json()["data"]
    urls = sorted(c["content"]["url"] for c in cards if c["kind"] == "link")
    assert urls == ["https://example.com/article", "https://example.org/b"]
    note = next(c for c in cards if c["kind"] == "note")
    assert note["content"]["markdown"].startswith("**Two links**") and "launch" in note["content"]["markdown"]
    assert "signature" not in note["content"]["markdown"]

    # A second mail lands on the same Inbox, below the first.
    r = await client.post("/api/v1/inbound/email", content=_mime("ada@example.com", address, "", "just a thought"),
                          headers=headers)
    assert r.status_code == 202
    cards2 = (await client.get(f"/api/v1/canvases/{inbox['id']}/items")).json()["data"]
    assert len(cards2) == 4 and max(c["y"] for c in cards2) > max(c["y"] for c in cards)

    # Rotating the address retires the old one.
    new = (await client.post("/api/v1/users/me/inbound")).json()["data"]["address"]
    assert new != address
    r = await client.post("/api/v1/inbound/email", content=raw, headers=headers)
    assert r.status_code == 404


# ---------- chat actions ----------

async def _answer(user_email: str, canvas_id: str | None, content: str) -> int:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == user_email))
        session.add(ChatMessage(user_id=user.id, canvas_id=canvas_id, role="user", content="How do I launch?",
                                cited_items=[]))
        msg = ChatMessage(user_id=user.id, canvas_id=canvas_id, role="assistant", content=content, cited_items=[])
        session.add(msg)
        await session.commit()
        return msg.id


async def test_save_answer_as_note(client, canvas):
    mid = await _answer("ada@example.com", canvas["id"], "Book the venue first [1], then email guests [2].")
    r = await client.post(f"/api/v1/chat/messages/{mid}/actions",
                          json={"action": "save_note", "canvas_id": canvas["id"], "x": 10, "y": 20})
    assert r.status_code == 201, r.text
    note = r.json()["data"]
    assert note["kind"] == "note" and note["x"] == 10
    assert note["content"]["markdown"] == "**How do I launch?**\n\nBook the venue first, then email guests."
    # Not someone else's answer.
    client.cookies.clear()
    await make_user(client, "eve@example.com")
    other = (await client.post("/api/v1/canvases", json={"title": "Mine"})).json()["data"]
    r = await client.post(f"/api/v1/chat/messages/{mid}/actions",
                          json={"action": "save_note", "canvas_id": other["id"]})
    assert r.status_code == 404


async def test_checklist_from_answer(client, canvas, monkeypatch):
    from app.routes import chat as chat_route
    from app.services.ai import client as ai

    mid = await _answer("ada@example.com", canvas["id"], "Book the venue [1] and email the guests [2].")
    r = await client.post(f"/api/v1/chat/messages/{mid}/actions",
                          json={"action": "checklist", "canvas_id": canvas["id"]})
    assert r.status_code == 503  # assistant off in tests

    monkeypatch.setattr(settings, "openai_api_key", "k")
    monkeypatch.setattr(settings, "openai_base_url", "http://ai.invalid")

    async def fake_json(system, prompt, schema, **kw):
        assert "[1]" not in prompt.value
        kw["usage"].input_tokens, kw["usage"].output_tokens = 40, 20
        return schema(title="Launch prep", items=["Book the venue", "☐ Email the guests"])

    monkeypatch.setattr(ai, "chat_json", fake_json)
    r = await client.post(f"/api/v1/chat/messages/{mid}/actions",
                          json={"action": "checklist", "canvas_id": canvas["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["data"]["content"]["markdown"] == "**Launch prep**\n\n- ☐ Book the venue\n- ☐ Email the guests"
    async with engine.begin() as conn:
        row = (await conn.execute(text("select task, input_tokens from ai_requests"))).first()
    assert row == ("chat_checklist", 40)

    async def abusive(system, prompt, schema, **kw):
        return schema(title="x", items=["you are stupid"])

    monkeypatch.setattr(ai, "chat_json", abusive)
    r = await client.post(f"/api/v1/chat/messages/{mid}/actions",
                          json={"action": "checklist", "canvas_id": canvas["id"]})
    assert r.status_code == 422 and r.json()["error"]["message"] == chat_route.OUTPUT_BLOCKED


# ---------- reminders reach the mailbox ----------

async def test_reminder_email_is_sent(client, canvas):
    note = await _note(client, canvas["id"], "Call the venue")
    at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    r = await client.post("/api/v1/reminders", json={"item_id": note["id"], "remind_at": at, "note": "today"})
    assert r.status_code == 201, r.text
    async with engine.begin() as conn:  # time passes
        await conn.execute(text("update reminders set remind_at = now() - interval '1 second'"))
    await drain()  # the index job, so the card is "ok" and its text may go out by email
    from app.worker import tick

    await tick()
    await drain()
    mails = [m for m in sender.outbox if "Call the venue" in m["subject"] + m["text"]]
    assert mails and mails[-1]["to"] == "ada@example.com"
    async with SessionLocal() as session:
        assert (await session.scalar(select(Item).where(Item.id == note["id"]))) is not None
