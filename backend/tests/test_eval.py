"""Retrieval score for the golden questions. Refusals and chitchat are not retrieval and are skipped here."""

import uuid

from conftest import drain
from sqlalchemy import text

from app.db import SessionLocal, engine
from evals.score import load, score


async def test_golden_retrieval_recall(client, canvas):
    corpus, questions = load()
    ids: dict[str, uuid.UUID] = {}
    for card in corpus:
        r = await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                              json={"kind": card["kind"], "x": 0, "y": 0, "content": card["content"]})
        assert r.status_code == 201, r.text
        ids[card["key"]] = uuid.UUID(r.json()["data"]["id"])
    assert await drain() >= len(corpus)

    me = (await client.get("/api/v1/users/me")).json()["data"]
    async with SessionLocal() as session:
        report = await score(session, uuid.UUID(me["id"]), uuid.UUID(canvas["id"]), ids, questions)
    print(f"recall@5={report['recall_at_5']} hit={report['hit_rate']} mrr={report['mrr']} "
          f"no_match={report['no_match_ok']} scored={report['scored']} skipped={report['skipped']}")
    misses = ", ".join(f"{m['id']} recall {m['recall']}" for m in report["misses"]) or "none"
    assert report["recall_at_5"] >= 0.9 and report["no_match_ok"] == 1, (
        f"recall@5 {report['recall_at_5']} hit {report['hit_rate']} mrr {report['mrr']} "
        f"no_match {report['no_match_ok']} misses: {misses}")
    async with engine.connect() as conn:
        chunks = await conn.scalar(text("select count(*) from chunks"))
    assert chunks >= len(corpus)
