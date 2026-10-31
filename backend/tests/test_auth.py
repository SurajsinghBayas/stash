from conftest import drain, link_from_outbox, make_user

from app.services.mail import sender


async def test_signup_requires_verification_before_login(client):
    r = await client.post("/api/v1/auth/signup", json={"email": "bo@example.com", "password": "long enough 1"})
    assert r.status_code == 201
    r = await client.post("/api/v1/auth/login", json={"email": "bo@example.com", "password": "long enough 1"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "email_not_verified"


async def test_verify_then_me_and_logout(client):
    me = await make_user(client)
    assert me["email"] == "ada@example.com"
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 200 and r.json()["data"]["has_password"] is True
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.get("/api/v1/users/me")).status_code == 401


async def test_duplicate_signup_and_short_password(client):
    await make_user(client)
    r = await client.post("/api/v1/auth/signup", json={"email": "ADA@example.com", "password": "correct horse 1"})
    assert r.status_code == 409
    r = await client.post("/api/v1/auth/signup", json={"email": "new@example.com", "password": "short"})
    assert r.status_code == 400


async def test_wrong_password(client):
    await make_user(client)
    r = await client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "wrong password"})
    assert r.status_code == 401


async def test_refresh_rotates_and_reuse_revokes_family(client):
    await make_user(client)
    old = client.cookies.get("stash_rt")
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    new = client.cookies.get("stash_rt")
    assert new and new != old

    # A stolen old token is replayed: the whole family is revoked, including the new token.
    client.cookies.set("stash_rt", old, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    client.cookies.set("stash_rt", new, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_forgot_password_does_not_reveal_accounts_and_resets(client):
    await make_user(client)
    sender.outbox.clear()
    r = await client.post("/api/v1/auth/password/forgot", json={"email": "nobody@example.com"})
    assert r.status_code == 202
    await drain()
    assert not sender.outbox

    r = await client.post("/api/v1/auth/password/forgot", json={"email": "ada@example.com"})
    assert r.status_code == 202
    await drain()
    token = link_from_outbox("/reset-password")
    r = await client.post("/api/v1/auth/password/reset", json={"token": token, "password": "a new password 2"})
    assert r.status_code == 200
    r = await client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "a new password 2"})
    assert r.status_code == 200
    # Reset links work once.
    r = await client.post("/api/v1/auth/password/reset", json={"token": token, "password": "another one 3"})
    assert r.status_code == 400


async def test_sent_links_are_scrubbed_from_jobs(client):
    from sqlalchemy import text

    from app.db import engine

    await make_user(client)
    async with engine.connect() as conn:
        payloads = (await conn.execute(text("select payload from jobs where kind = 'send_email'"))).scalars().all()
    assert payloads and all("link" not in p for p in payloads)


async def test_cross_site_post_is_refused(client):
    r = await client.post("/api/v1/auth/login", json={"email": "a@b.co", "password": "x" * 12},
                          headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
