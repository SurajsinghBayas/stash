"""Security properties that must never regress: tenant isolation, CSRF, headers, body caps, SSRF, limiter memory."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import drain, make_user
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.rate_limit import SlidingWindow
from app.services.links.fetch import BlockedURL, _check_host


async def _other_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:5173")


# ---------- tenant isolation ----------

async def test_another_user_cannot_touch_my_data(client, user):
    """Ada owns a canvas, a note (with two versions), a reminder and a share link. Eve tries every route with Ada's
    ids and must get 403/404 every time, and Ada's data must be exactly as before."""
    canvas = (await client.post("/api/v1/canvases", json={"title": "Private plans"})).json()["data"]
    cid = canvas["id"]
    note = (await client.post(f"/api/v1/canvases/{cid}/items",
                              json={"kind": "note", "x": 0, "y": 0, "content": {"markdown": "secret v1"}})).json()
    note = note["data"]
    r = await client.patch(f"/api/v1/canvases/{cid}/items",
                           json={"items": [{"id": note["id"], "version": note["version"],
                                            "content": {"markdown": "secret v2"}}]})
    note = r.json()["data"]["updated"][0]
    iid = note["id"]
    versions = (await client.get(f"/api/v1/items/{iid}/versions")).json()["data"]
    vid = versions[-1]["id"]
    reminder = (await client.post("/api/v1/reminders", json={
        "remind_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(), "item_id": iid, "note": "mine"})).json()
    rid = reminder["data"]["id"]
    await client.post(f"/api/v1/canvases/{cid}/share")
    await drain()

    async with await _other_client() as eve:
        await make_user(eve, "eve@example.com")
        later = (datetime.now(UTC) + timedelta(days=2)).isoformat()
        attempts = [
            ("GET", f"/api/v1/canvases/{cid}", None),
            ("PATCH", f"/api/v1/canvases/{cid}", {"title": "pwned"}),
            ("DELETE", f"/api/v1/canvases/{cid}", None),
            ("GET", f"/api/v1/canvases/{cid}/items", None),
            ("POST", f"/api/v1/canvases/{cid}/items", {"kind": "note", "x": 0, "y": 0,
                                                        "content": {"markdown": "injected"}}),
            ("PATCH", f"/api/v1/canvases/{cid}/items", {"items": [{"id": iid, "version": note["version"],
                                                                    "content": {"markdown": "pwned"}}]}),
            ("GET", f"/api/v1/canvases/{cid}/trash", None),
            ("POST", f"/api/v1/canvases/{cid}/restore", None),
            ("POST", f"/api/v1/canvases/{cid}/share", None),
            ("DELETE", f"/api/v1/canvases/{cid}/share", None),
            ("POST", f"/api/v1/canvases/{cid}/uploads", {"filename": "a.png", "mime": "image/png", "bytes": 10,
                                                          "x": 0, "y": 0}),
            ("DELETE", f"/api/v1/items/{iid}", None),
            ("POST", f"/api/v1/items/{iid}/restore", None),
            ("GET", f"/api/v1/items/{iid}/versions", None),
            ("POST", f"/api/v1/items/{iid}/versions/{vid}/restore", {"version": note["version"]}),
            ("GET", f"/api/v1/items/{iid}/related", None),
            ("GET", f"/api/v1/items/{iid}/image", None),
            ("POST", f"/api/v1/items/{iid}/uploaded", None),
            ("PATCH", f"/api/v1/reminders/{rid}", {"note": "pwned", "remind_at": later}),
            ("DELETE", f"/api/v1/reminders/{rid}", None),
            ("POST", "/api/v1/reminders", {"remind_at": later, "item_id": iid}),
        ]
        for method, path, body in attempts:
            r = await eve.request(method, path, json=body)
            assert r.status_code in (403, 404), f"{method} {path} -> {r.status_code} {r.text}"

        # Search and lists only ever show Eve's own data.
        assert (await eve.get("/api/v1/canvases")).json()["data"] == []
        found = (await eve.get("/api/v1/search", params={"q": "secret"})).json()["data"]
        assert not found

    after = (await client.get(f"/api/v1/canvases/{cid}")).json()["data"]
    assert after["title"] == "Private plans"
    items = (await client.get(f"/api/v1/canvases/{cid}/items")).json()["data"]
    assert [i["content"]["markdown"] for i in items] == ["secret v2"]
    reminders = (await client.get("/api/v1/reminders")).json()["data"]
    assert [x["note"] for x in reminders] == ["mine"]


async def test_signed_out_requests_are_refused(client):
    for method, path in [("GET", "/api/v1/canvases"), ("GET", "/api/v1/users/me"), ("GET", "/api/v1/reminders"),
                         ("GET", "/api/v1/users/me/export"), ("POST", "/api/v1/canvases")]:
        r = await client.request(method, path, json={} if method == "POST" else None)
        assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


# ---------- CSRF and headers ----------

async def test_writes_from_another_origin_are_rejected(client, user):
    r = await client.post("/api/v1/canvases", json={"title": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "bad_origin"
    r = await client.post("/api/v1/canvases", json={"title": "x"}, headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 201


async def test_api_responses_carry_security_headers(client, user):
    r = await client.get("/api/v1/users/me")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"  # personal data is never cached
    r = await client.get("/api/v1/email/unsubscribe", params={"token": "nope"})
    assert "style-src 'unsafe-inline'" in r.headers["content-security-policy"]  # its own, narrower policy


async def test_session_cookies_are_http_only(client):
    await make_user(client, "cookie@example.com")
    r = await client.post("/api/v1/auth/login", json={"email": "cookie@example.com", "password": "correct horse 1"})
    cookies = r.headers.get_list("set-cookie")
    assert cookies and all("httponly" in c.lower() and "samesite=lax" in c.lower() for c in cookies)


# ---------- body size ----------

async def test_oversized_body_is_rejected_even_without_content_length(client):
    big = b'{"email": "a@example.com", "password": "' + b"x" * (1024 * 1024 + 10) + b'"}'

    async def chunks():
        for i in range(0, len(big), 64 * 1024):
            yield big[i:i + 64 * 1024]

    r = await client.post("/api/v1/auth/login", content=chunks(), headers={"content-type": "application/json"})
    assert r.status_code == 413
    r = await client.post("/api/v1/auth/login", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413


# ---------- SSRF ----------

@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/", "http://127.0.0.1/", "http://localhost/", "http://[::1]/",
    "http://10.0.0.5/", "http://192.168.1.1/", "http://0.0.0.0/", "file:///etc/passwd", "gopher://example.com/",
    "http://example.com:5432/", "http://[::ffff:127.0.0.1]/",
])
async def test_link_fetcher_refuses_internal_targets(url):
    with pytest.raises(BlockedURL):
        await _check_host(url)


async def test_link_fetcher_connects_to_the_address_it_checked():
    target = await _check_host("https://1.1.1.1/dns-query?x=1")
    assert target.url == "https://1.1.1.1/dns-query?x=1" and target.host == "1.1.1.1"


# ---------- limiter ----------

def test_rate_limiter_forgets_idle_keys():
    w = SlidingWindow()
    for i in range(5000):
        w.hit(f"ip:{i}", 10, 60)
    w._prune(w._hits[next(iter(w._hits))][-1] + 86_401)
    assert not w._hits
