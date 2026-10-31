async def test_profile_counts_and_sign_in(client, canvas):
    cid = canvas["id"]
    for kind, content in (("note", {"markdown": "a"}), ("note", {"markdown": "b"}), ("code", {"source": "x = 1"})):
        r = await client.post(f"/api/v1/canvases/{cid}/items", json={"kind": kind, "x": 0, "y": 0, "content": content})
        assert r.status_code == 201, r.text
    gone = (await client.post(f"/api/v1/canvases/{cid}/items",
                              json={"kind": "note", "x": 0, "y": 0, "content": {"markdown": "deleted"}})).json()["data"]
    assert (await client.delete(f"/api/v1/items/{gone['id']}")).status_code == 204

    r = await client.get("/api/v1/users/me/profile")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["sign_in"] == {"password": True, "providers": []}
    assert body["counts"]["canvases"] == 1
    assert body["counts"]["cards"] == 3
    assert body["counts"]["by_kind"] == {"note": 2, "code": 1}
    assert body["counts"]["upcoming_reminders"] == 0
    assert body["member_since"]


async def test_profile_requires_sign_in(client):
    assert (await client.get("/api/v1/users/me/profile")).status_code == 401
