import io
from urllib.parse import urlsplit

from conftest import drain
from PIL import Image


def png(size=(64, 48)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (200, 240, 49)).save(out, "PNG")
    return out.getvalue()


async def _upload(client, canvas, data: bytes, mime: str):
    r = await client.post(f"/api/v1/canvases/{canvas['id']}/uploads",
                          json={"filename": "shot.png", "mime": mime, "bytes": len(data), "x": 0, "y": 0})
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    put = await client.put(urlsplit(body["upload"]["url"]).path, content=data,
                           headers=body["upload"]["headers"])
    assert put.status_code == 200, put.text
    item_id = body["item"]["id"]
    r = await client.post(f"/api/v1/items/{item_id}/uploaded")
    assert r.json()["data"]["content"]["upload_state"] == "processing"
    await drain()
    items = (await client.get(f"/api/v1/canvases/{canvas['id']}/items")).json()["data"]
    return next(i for i in items if i["id"] == item_id)


async def test_image_is_processed_and_served(client, canvas):
    item = await _upload(client, canvas, png(), "image/png")
    assert item["content"]["upload_state"] == "ready"
    assert item["content"]["width"] == 64 and item["content"]["height"] == 48
    r = await client.get(f"/api/v1/items/{item['id']}/image", params={"size": "thumb"})
    assert r.status_code == 302
    img = await client.get(urlsplit(r.headers["location"]).path)
    assert img.status_code == 200 and img.content[:4] == b"RIFF"  # WebP


async def test_type_mismatch_is_rejected_and_never_served(client, canvas):
    item = await _upload(client, canvas, png(), "image/jpeg")
    assert item["content"]["upload_state"] == "rejected"
    assert (await client.get(f"/api/v1/items/{item['id']}/image")).status_code == 404


async def test_not_an_image_is_rejected(client, canvas):
    item = await _upload(client, canvas, b"<html>definitely not a png</html>", "image/png")
    assert item["content"]["reject_reason"] == "not_an_image"


async def test_oversized_upload_refused_up_front(client, canvas):
    r = await client.post(f"/api/v1/canvases/{canvas['id']}/uploads",
                          json={"filename": "big.png", "mime": "image/png", "bytes": 50 * 1024 * 1024, "x": 0,
                                "y": 0})
    assert r.status_code == 400 and r.json()["error"]["code"] == "file_too_large"


async def test_image_card_text_gets_a_safety_verdict(client, canvas):
    item = await _upload(client, canvas, png(), "image/png")
    assert item["safety_state"] == "ok"
