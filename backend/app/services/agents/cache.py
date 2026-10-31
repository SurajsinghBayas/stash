"""Caches for the AI pipeline.

- embeddings: Postgres `embedding_cache` keyed by sha256(model, input type, text), with an in-process LRU in front
  for query vectors. Embeddings are deterministic, so a hit is always correct.
- answers: Postgres `answer_cache`, exact match only. The key holds the corpus version (any card, chunk or memory
  change misses), the prompt version and the models, and it is never shared between users.
- `TTLCache` for short-lived in-process results (plans, reranks).
"""

import hashlib
import json
import time
import uuid
from array import array
from collections import OrderedDict
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.ai import client as ai
from app.services.safety.service import SafeText

EMBED_BATCH = 64


def digest(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, default=str, separators=(",", ":")).encode()).hexdigest()


class TTLCache:
    def __init__(self, size: int, ttl_s: float):
        self.size, self.ttl = size, ttl_s
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any:
        found = self._data.get(key)
        if not found:
            return None
        expires, value = found
        if expires < time.monotonic():
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def put(self, key: str, value: Any) -> None:
        self._data[key] = (time.monotonic() + self.ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self.size:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


_query_vectors = TTLCache(1024, 24 * 3600)  # array('f'): 4 KB per vector


async def embed(session: AsyncSession, texts: list[SafeText],
                input_type: Literal["document", "query"]) -> list[list[float]]:
    """Voyage embeddings through the cache. New vectors are written with the caller's session (caller commits)."""
    keys = [digest(settings.embed_model, input_type, t.value) for t in texts]
    found: dict[str, list[float]] = {}
    for key in keys:
        if (hit := _query_vectors.get(key)) is not None:
            found[key] = hit.tolist()
    lookup = [k for k in dict.fromkeys(keys) if k not in found]
    if lookup:
        rows = await session.execute(text("select key, vector from embedding_cache where key = any(:keys)"),
                                     {"keys": lookup})
        for key, vector in rows:
            found[key] = list(vector)
        if found:
            await session.execute(text("update embedding_cache set used_at = now() where key = any(:keys) "
                                       "and used_at < now() - interval '1 day'"), {"keys": list(found)})

    missing: list[int] = []
    for i, key in enumerate(keys):
        if key not in found and all(keys[j] != key for j in missing):
            missing.append(i)
    for start in range(0, len(missing), EMBED_BATCH):
        batch = missing[start:start + EMBED_BATCH]
        vectors = await ai.embed([texts[i] for i in batch], input_type)
        rows = []
        for i, vector in zip(batch, vectors, strict=True):
            found[keys[i]] = vector
            rows.append({"key": keys[i], "vector": vector})
        await session.execute(text("insert into embedding_cache (key, vector) values (:key, :vector) "
                                   "on conflict (key) do update set used_at = now()"), rows)

    if input_type == "query":
        for key in keys:
            _query_vectors.put(key, array("f", found[key]))
    return [found[key] for key in keys]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


# ---------- answers ----------

async def corpus_version(session: AsyncSession, user_id: uuid.UUID) -> str:
    row = (await session.execute(text("""
        select (select count(*) || ':' || coalesce(max(updated_at)::text, '') || ':'
                       || coalesce(max(deleted_at)::text, '') from items where owner_id = :u),
               (select count(*) || ':' || coalesce(max(id), 0) from chunks where owner_id = :u),
               (select count(*) || ':' || coalesce(max(created_at)::text, '') from memories where user_id = :u),
               (select memory_enabled from users where id = :u)
    """), {"u": user_id})).one()
    return digest(*row)


async def get_answer(session: AsyncSession, key: str) -> dict | None:
    row = (await session.execute(
        text("select answer, sources, cited from answer_cache where key = :k "
             "and created_at > now() - make_interval(hours => :h)"),
        {"k": key, "h": settings.answer_cache_hours},
    )).first()
    return {"answer": row.answer, "sources": row.sources, "cited": list(row.cited)} if row else None


async def put_answer(session: AsyncSession, key: str, user_id: uuid.UUID, answer: str, sources: list[dict],
                     cited: list[uuid.UUID]) -> None:
    await session.execute(
        text("insert into answer_cache (key, user_id, answer, sources, cited) "
             "values (:k, :u, :a, cast(:s as jsonb), :c) on conflict (key) do nothing"),
        {"k": key, "u": user_id, "a": answer, "s": json.dumps(sources), "c": cited},
    )


async def prune(session: AsyncSession) -> None:
    await session.execute(text("delete from answer_cache where created_at < now() - make_interval(hours => :h)"),
                          {"h": settings.answer_cache_hours})
    await session.execute(text("delete from embedding_cache where used_at < now() - interval '90 days'"))
    await session.execute(text("delete from link_cache where fetched_at < now() - interval '30 days'"))
    await session.commit()
