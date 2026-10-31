from conftest import drain, make_user
from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_items_crud_and_batch_conflict(client, canvas):
    cid = canvas["id"]
    r = await client.post(f"/api/v1/canvases/{cid}/items",
                          json={"kind": "note", "x": 10, "y": 20, "content": {"markdown": "Ship **v1** on Friday"}})
    assert r.status_code == 201, r.text
    note = r.json()["data"]
    assert note["version"] == 1 and note["safety_state"] == "unchecked"

    r = await client.patch(f"/api/v1/canvases/{cid}/items", json={"items": [{"id": note["id"], "version": 1, "x": 99}]})
    body = r.json()["data"]
    assert body["updated"][0]["x"] == 99 and not body["conflicts"]

    # A second tab still holds version 1: its write is refused and it gets the current card back.
    r = await client.patch(f"/api/v1/canvases/{cid}/items", json={"items": [{"id": note["id"], "version": 1, "x": 5}]})
    body = r.json()["data"]
    assert not body["updated"] and body["conflicts"][0]["x"] == 99

    assert (await client.delete(f"/api/v1/items/{note['id']}")).status_code == 204
    r = await client.get(f"/api/v1/canvases/{cid}/items")
    assert r.json()["data"] == []


async def test_index_job_marks_card_safe_and_searchable(client, canvas):
    cid = canvas["id"]
    await client.post(f"/api/v1/canvases/{cid}/items",
                      json={"kind": "text", "x": 0, "y": 0, "content": {"text": "Quarterly roadmap review"}})
    await drain()
    item = (await client.get(f"/api/v1/canvases/{cid}/items")).json()["data"][0]
    assert item["safety_state"] == "ok" and item["index_state"] == "ready"
    hits = (await client.get("/api/v1/search", params={"q": "roadmap"})).json()["data"]
    assert [h["item_id"] for h in hits] == [item["id"]]


async def test_abusive_card_is_flagged(client, canvas):
    cid = canvas["id"]
    await client.post(f"/api/v1/canvases/{cid}/items",
                      json={"kind": "note", "x": 0, "y": 0, "content": {"markdown": "honestly you are stupid"}})
    await drain()
    item = (await client.get(f"/api/v1/canvases/{cid}/items")).json()["data"][0]
    assert item["safety_state"] == "flagged"


async def test_adult_domain_link_is_never_fetched(client, canvas):
    cid = canvas["id"]
    r = await client.post(f"/api/v1/canvases/{cid}/items",
                          json={"kind": "link", "x": 0, "y": 0, "content": {"url": "https://pornhub.com/x"}})
    assert r.json()["data"]["content"]["fetch_state"] == "blocked"
    await drain()
    item = (await client.get(f"/api/v1/canvases/{cid}/items")).json()["data"][0]
    assert item["safety_state"] == "flagged"


async def test_duplicate_link_is_reported(client, canvas):
    cid = canvas["id"]
    body = {"kind": "link", "x": 0, "y": 0, "content": {"url": "https://example.com/post?utm_source=x"}}
    first = await client.post(f"/api/v1/canvases/{cid}/items", json=body)
    assert first.json()["meta"]["duplicate_of"] is None
    body["content"]["url"] = "https://www.example.com/post/"
    second = await client.post(f"/api/v1/canvases/{cid}/items", json=body)
    assert second.json()["meta"]["duplicate_of"]["item_id"] == first.json()["data"]["id"]


async def test_other_users_get_404(client, canvas):
    cid = canvas["id"]
    item = (await client.post(f"/api/v1/canvases/{cid}/items",
                              json={"kind": "text", "x": 0, "y": 0, "content": {"text": "private"}})).json()["data"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:5173") as other:
        await make_user(other, "eve@example.com")
        assert (await other.get(f"/api/v1/canvases/{cid}")).status_code == 404
        assert (await other.get(f"/api/v1/canvases/{cid}/items")).status_code == 404
        assert (await other.delete(f"/api/v1/items/{item['id']}")).status_code == 404
        r = await other.patch(f"/api/v1/canvases/{cid}/items", json={"items": [{"id": item["id"], "version": 1}]})
        assert r.status_code == 404
        assert (await other.get("/api/v1/search", params={"q": "private"})).json()["data"] == []


async def test_canvas_list_has_previews(client, canvas):
    cid = canvas["id"]
    await client.post(f"/api/v1/canvases/{cid}/items", json={"kind": "text", "x": 1, "y": 2, "content": {"text": "a"}})
    rows = (await client.get("/api/v1/canvases")).json()["data"]
    assert rows[0]["item_count"] == 1 and len(rows[0]["preview"]) == 1


async def test_partial_content_patch_keeps_other_fields(client, canvas):
    cid = canvas["id"]
    code = {"language": "python", "source": "x = 1", "filename": "a.py"}
    item = (await client.post(f"/api/v1/canvases/{cid}/items",
                              json={"kind": "code", "x": 0, "y": 0, "content": code})).json()["data"]
    r = await client.patch(f"/api/v1/canvases/{cid}/items",
                           json={"items": [{"id": item["id"], "version": 1, "content": {"source": "x = 2"}}]})
    assert r.json()["data"]["updated"][0]["content"] == {"language": "python", "source": "x = 2", "filename": "a.py"}

    note = (await client.post(f"/api/v1/canvases/{cid}/items", json={
        "kind": "note", "x": 0, "y": 0, "content": {"markdown": "keep me", "color": "yellow"}})).json()["data"]
    r = await client.patch(f"/api/v1/canvases/{cid}/items",
                           json={"items": [{"id": note["id"], "version": 1, "content": {"color": "blue"}}]})
    assert r.json()["data"]["updated"][0]["content"] == {"markdown": "keep me", "color": "blue"}
