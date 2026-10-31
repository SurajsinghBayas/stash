"""Score retrieval on the golden questions. No model calls: the same result every run.

Answer quality (citations, the verifier note, refusals) is covered by the chat tests. This score is the
retrieval half: recall@5, hit rate and MRR over the lookup questions, plus whether no-match questions stay empty.
"""

import json
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.search import service as search

HERE = Path(__file__).parent
K = 5


def load() -> tuple[list[dict], list[dict]]:
    corpus = json.loads((HERE / "corpus.json").read_text())
    questions = [json.loads(line) for line in (HERE / "questions.jsonl").read_text().splitlines() if line.strip()]
    return corpus, questions


async def top_cards(session: AsyncSession, owner: uuid.UUID, canvas_id: uuid.UUID, question: str) -> list[uuid.UUID]:
    filters = search.Filters(canvas_id)
    fused = search.fuse(
        await search.chunk_keyword(session, owner, [question], filters),
        await search.unchunked_keyword(session, owner, [question], filters),
    )
    seen: list[uuid.UUID] = []
    for passage in fused:
        if passage.hit.id not in seen:
            seen.append(passage.hit.id)
        if len(seen) == K:
            break
    return seen


def _row(question: dict, got: list[str], ids: dict[str, str]) -> dict:
    expected = question["expect"]
    if question["kind"] == "no_match":
        ok = not got
        return {"id": question["id"], "kind": "no_match", "hit": ok, "recall": 1.0 if ok else 0.0, "rr": 1.0 if ok else 0.0,
                "got": got}
    ranks = {card: i for i, card in enumerate(got, start=1)}
    found = [key for key in expected if ids.get(key) in got]
    first = min((ranks[ids[key]] for key in found), default=0)
    return {"id": question["id"], "kind": "lookup", "hit": bool(found),
            "recall": len(found) / len(expected) if expected else 1.0,
            "rr": (1.0 / first) if first else 0.0, "got": [key for key, cid in ids.items() if cid in got]}


async def score(session: AsyncSession, owner: uuid.UUID, canvas_id: uuid.UUID, ids: dict[str, uuid.UUID],
                questions: list[dict]) -> dict:
    """`ids` maps a corpus key to the card id that was saved."""
    str_ids = {key: str(value) for key, value in ids.items()}
    rows = []
    for question in questions:
        if question["kind"] in ("refuse", "chitchat"):
            continue
        got = [str(i) for i in await top_cards(session, owner, canvas_id, question["question"])]
        rows.append(_row(question, got, str_ids))
    lookup = [r for r in rows if r["kind"] == "lookup"]
    blank = [r for r in rows if r["kind"] == "no_match"]

    def avg(group: list[dict], key: str) -> float:
        return round(sum(r[key] for r in group) / len(group), 3) if group else 1.0

    return {"recall_at_5": avg(lookup, "recall"), "hit_rate": avg(lookup, "hit"), "mrr": avg(lookup, "rr"),
            "no_match_ok": avg(blank, "hit"), "misses": [r for r in rows if not r["hit"] or r["recall"] < 1],
            "scored": len(rows), "skipped": sum(1 for q in questions if q["kind"] in ("refuse", "chitchat"))}
