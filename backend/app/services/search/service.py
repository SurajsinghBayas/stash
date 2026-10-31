"""Keyword search (always), vector search (when pgvector + Voyage are available), fused with RRF."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import capabilities
from app.errors import NotFound
from app.services.ai import client as ai
from app.services.items.text import KIND_LABEL, looks_like_code, snippet_of, title_of
from app.services.safety.service import SafeText, from_checked_item

TOKEN = re.compile(r"[\w]+", re.UNICODE)


STOPWORDS = frozenset(
    "a an and are as at be but by can could did do does for from had has have how i if in is it its me my of on or "
    "our so than that the their them then there these they this to was we were what when where which who why will "
    "with would you your about any anything did find show tell saved save".split()
)

# A question that is only a card type ("code", "my notes") should list that kind. The word itself is
# often missing from the card: a Python file's text is the language and the source, not the word "code".
KIND_ALIASES = {
    "code": "code", "codes": "code", "snippet": "code", "snippets": "code",
    "script": "code", "scripts": "code",
    "link": "link", "links": "link", "url": "link", "urls": "link", "website": "link", "websites": "link",
    "note": "note", "notes": "note",
    "image": "image", "images": "image", "photo": "image", "photos": "image",
    "picture": "image", "pictures": "image", "screenshot": "image", "screenshots": "image",
    "text": "text", "texts": "text",
}
BROWSE_FILLER = STOPWORDS | {"card", "cards", "stuff", "thing", "things", "give", "get", "want", "need",
                             "looking", "look", "see", "please", "just", "some", "all", "got"}
# A language name next to "code" is still a request for code, not a separate topic.
LANGUAGES = frozenset(
    "python py javascript js typescript ts java go golang rust ruby sql bash sh html css cpp php kotlin swift".split()
)


def browse_kinds(question: str) -> list[str] | None:
    """Kinds to list when the question names a card type and nothing more specific."""
    kinds: list[str] = []
    specific = False
    for token in TOKEN.findall(question.lower()):
        if len(token) <= 1 or token in BROWSE_FILLER:
            continue
        if token in LANGUAGES:
            continue
        kind = KIND_ALIASES.get(token)
        if kind:
            if kind not in kinds:
                kinds.append(kind)
        else:
            specific = True
    return kinds if kinds and not specific else None


def _tsquery(q: str, *, any_word: bool = False) -> str | None:
    """Quick find needs every word (prefix match). Chat questions match any meaningful word, ranked by ts_rank."""
    tokens = [t.lower() for t in TOKEN.findall(q) if len(t) > 1]
    if any_word:
        tokens = [t for t in tokens if t not in STOPWORDS]
    tokens = list(dict.fromkeys(tokens))[:12]
    return (" | " if any_word else " & ").join(f"{t}:*" for t in tokens) or None


def _like(q: str) -> str:
    return "%" + q.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")[:100] + "%"


@dataclass
class Hit:
    id: uuid.UUID
    canvas_id: uuid.UUID
    canvas_title: str
    kind: str
    content: dict
    search_text: str
    safety_state: str
    safety_hash: str | None
    content_hash: str | None
    score: float = 0.0
    created_at: datetime | None = None

    def out(self) -> dict:
        return {"item_id": str(self.id), "canvas_id": str(self.canvas_id), "canvas_title": self.canvas_title,
                "kind": self.kind, "kind_label": KIND_LABEL.get(self.kind, "Card"),
                "title": title_of(self.kind, self.content), "snippet": snippet_of(self.kind, self.content, 120)}


BASE = """
  select i.id, i.canvas_id, c.title as canvas_title, i.kind, i.content, coalesce(i.search_text, '') as search_text,
         i.safety_state, i.safety_hash, i.content_hash {score}
  from items i join canvases c on c.id = i.canvas_id
  where i.owner_id = :owner and i.deleted_at is null and c.deleted_at is null
    and (cast(:canvas as uuid) is null or i.canvas_id = cast(:canvas as uuid)) {extra}
"""


async def _keyword_rows(session: AsyncSession, owner: uuid.UUID, q: str, canvas_id: uuid.UUID | None,
                        limit: int, safe_only: bool) -> list[Hit]:
    tsq = _tsquery(q, any_word=safe_only)
    safe = "and i.safety_state = 'ok' and i.safety_hash = i.content_hash" if safe_only else ""
    tsq_sql = "to_tsquery('simple', cast(:tsq as text))"
    sql = BASE.format(
        score=f", (case when cast(:tsq as text) is null then 0 else ts_rank(i.tsv, {tsq_sql}) end)"
              " + (case when i.search_text ilike cast(:like as text) then 0.05 else 0 end) as score",
        extra=f"{safe} and ((cast(:tsq as text) is not null and i.tsv @@ {tsq_sql})"
              " or i.search_text ilike cast(:like as text))"
              " order by score desc, i.updated_at desc limit :limit",
    )
    rows = await session.execute(text(sql), {"owner": owner, "canvas": canvas_id, "tsq": tsq, "like": _like(q),
                                             "limit": limit})
    return [Hit(**r._mapping) for r in rows]


async def keyword(session: AsyncSession, owner: uuid.UUID, q: str, *, canvas_id: uuid.UUID | None = None,
                  limit: int = 20) -> list[dict]:
    return [h.out() for h in await _keyword_rows(session, owner, q, canvas_id, limit, safe_only=False)]


async def _vector_rows(session: AsyncSession, owner: uuid.UUID, vector: list[float], canvas_id: uuid.UUID | None,
                       limit: int, exclude: uuid.UUID | None = None) -> list[Hit]:
    sql = BASE.format(
        score=", 1 - (i.embedding <=> cast(:vec as vector)) as score",
        extra="and i.embedding is not null and i.safety_state = 'ok' and i.safety_hash = i.content_hash"
              " and (cast(:exclude as uuid) is null or i.id <> cast(:exclude as uuid))"
              " order by i.embedding <=> cast(:vec as vector) limit :limit",
    )
    rows = await session.execute(text(sql), {"owner": owner, "canvas": canvas_id, "limit": limit,
                                             "vec": "[" + ",".join(f"{v:.6f}" for v in vector) + "]",
                                             "exclude": exclude})
    return [Hit(**r._mapping) for r in rows]


def _rrf(*ranked: list[Hit], k: int = 60) -> list[Hit]:
    scores: dict[uuid.UUID, float] = {}
    by_id: dict[uuid.UUID, Hit] = {}
    for hits in ranked:
        for rank, hit in enumerate(hits):
            scores[hit.id] = scores.get(hit.id, 0.0) + 1.0 / (k + rank + 1)
            by_id.setdefault(hit.id, hit)
    fused = sorted(by_id.values(), key=lambda h: scores[h.id], reverse=True)
    for hit in fused:
        hit.score = scores[hit.id]
    return fused


async def retrieve(session: AsyncSession, owner: uuid.UUID, question: SafeText, *, canvas_id: uuid.UUID | None,
                   keep: int = 6, rerank_floor: float = 0.35, rerank_margin: float = 0.3) -> list[Hit]:
    """Chat retrieval. Only cards that passed the safety check for their current text are considered."""
    keyword_hits = await _keyword_rows(session, owner, question.value, canvas_id, 30, safe_only=True)
    vector_hits: list[Hit] = []
    if capabilities.vector and settings.embeddings_configured:
        try:
            [vec] = await ai.embed([question], "query")
            vector_hits = await _vector_rows(session, owner, vec, canvas_id, 30)
        except ai.AIUnavailable:
            pass  # keyword results still answer; a Voyage outage should not take chat down
    candidates = _rrf(keyword_hits, vector_hits)[:30]
    if not candidates:
        return []
    if settings.embeddings_configured:
        docs = [from_checked_item(h.search_text[:4000], h.safety_state, h.safety_hash, h.content_hash)
                for h in candidates]
        try:
            ranked = await ai.rerank(question, docs, top_k=min(keep, len(docs)))
        except ai.AIUnavailable:
            return candidates[:keep]
        # rerank-3-lite gives unrelated text ~0.29-0.34 and relevant text 0.35-0.7 (spot-checked 2026-10-31).
        # Keep a card only above the floor and within the margin of the best match.
        cutoff = max(rerank_floor, (ranked[0][1] if ranked else 0) - rerank_margin)
        result = []
        for index, score in ranked:
            if score >= cutoff:
                candidates[index].score = score
                result.append(candidates[index])
        return result
    return candidates[:keep]


async def related(session: AsyncSession, owner: uuid.UUID, item_id: uuid.UUID, limit: int = 5) -> list[dict]:
    row = (await session.execute(
        text("select search_text, kind, content, safety_state from items "
             "where id = :id and owner_id = :owner and deleted_at is null"),
        {"id": item_id, "owner": owner},
    )).first()
    if not row:
        raise NotFound("Card not found")
    if capabilities.vector:
        vec = await session.scalar(text("select embedding::text from items where id = :id"), {"id": item_id})
        if vec:
            values = [float(v) for v in vec.strip("[]").split(",")]
            return [h.out() for h in await _vector_rows(session, owner, values, None, limit, exclude=item_id)]
    words = " ".join(title_of(row.kind, row.content).split()[:6])
    hits = await _keyword_rows(session, owner, words, None, limit + 1, safe_only=False) if words else []
    return [h.out() for h in hits if h.id != item_id][:limit]


# ---------- chunk retrieval (chat v2) ----------

@dataclass
class Filters:
    canvas_id: uuid.UUID | None = None
    kinds: list[str] | None = None
    since: datetime | None = None


@dataclass
class Passage:
    hit: Hit
    key: str  # chunk id, or "item:<id>" when the card has no chunks yet
    heading: str | None
    body: str
    score: float = 0.0

    def sealed_text(self, limit: int = 4000) -> SafeText:
        """Chunks hold only text that passed the check for the card's current content hash."""
        text = f"{self.heading}\n{self.body}" if self.heading else self.body
        return from_checked_item(text[:limit], self.hit.safety_state, self.hit.safety_hash, self.hit.content_hash)


CHUNKS = """
  select ch.id as chunk_id, ch.heading, ch.body, i.id, i.canvas_id, c.title as canvas_title, i.kind, i.content,
         coalesce(i.search_text, '') as search_text, i.safety_state, i.safety_hash, i.content_hash,
         i.created_at {score}
  from chunks ch join items i on i.id = ch.item_id join canvases c on c.id = i.canvas_id
  where ch.owner_id = :owner and i.deleted_at is null and c.deleted_at is null
    and ch.content_hash = i.content_hash and i.safety_state = 'ok' and i.safety_hash = i.content_hash
    and (cast(:canvas as uuid) is null or i.canvas_id = cast(:canvas as uuid))
    and (cast(:kinds as text[]) is null or i.kind = any(cast(:kinds as text[])))
    and (cast(:since as timestamptz) is null or i.created_at >= cast(:since as timestamptz)) {extra}
"""
HIT_FIELDS = ("id", "canvas_id", "canvas_title", "kind", "content", "search_text", "safety_state", "safety_hash",
              "content_hash", "created_at")


def _passage(row) -> Passage:
    m = row._mapping
    hit = Hit(**{k: m[k] for k in HIT_FIELDS})
    return Passage(hit, str(m["chunk_id"]), m["heading"], m["body"], float(m["score"] or 0))


def _params(owner: uuid.UUID, f: Filters, **extra) -> dict:
    return {"owner": owner, "canvas": f.canvas_id, "kinds": f.kinds, "since": f.since, **extra}


async def chunk_keyword(session: AsyncSession, owner: uuid.UUID, queries: list[str], f: Filters,
                        limit: int = 30) -> list[Passage]:
    """One query for all planner queries: any meaningful word, ranked by ts_rank."""
    tsq = _tsquery(" ".join(queries), any_word=True)
    if not tsq:
        return []
    sql = CHUNKS.format(score=", ts_rank(ch.tsv, to_tsquery('simple', cast(:tsq as text))) as score",
                        extra="and ch.tsv @@ to_tsquery('simple', cast(:tsq as text)) order by score desc limit :limit")
    return [_passage(r) for r in await session.execute(text(sql), _params(owner, f, tsq=tsq, limit=limit))]


async def chunk_vector(session: AsyncSession, owner: uuid.UUID, vector: list[float], f: Filters,
                       limit: int = 30) -> list[Passage]:
    if not capabilities.vector:
        return []
    sql = CHUNKS.format(score=", 1 - (ch.embedding <=> cast(:vec as vector)) as score",
                        extra="and ch.embedding is not null order by ch.embedding <=> cast(:vec as vector) "
                              "limit :limit")
    vec = "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
    return [_passage(r) for r in await session.execute(text(sql), _params(owner, f, vec=vec, limit=limit))]


async def unchunked_keyword(session: AsyncSession, owner: uuid.UUID, queries: list[str], f: Filters,
                            limit: int = 10) -> list[Passage]:
    """Cards whose ingest hasn't run yet (no chunks) are still found by their own text."""
    tsq = _tsquery(" ".join(queries), any_word=True)
    if not tsq:
        return []
    sql = BASE.format(
        score=", ts_rank(i.tsv, to_tsquery('simple', cast(:tsq as text))) as score, i.created_at",
        extra="and i.safety_state = 'ok' and i.safety_hash = i.content_hash"
              " and (cast(:kinds as text[]) is null or i.kind = any(cast(:kinds as text[])))"
              " and (cast(:since as timestamptz) is null or i.created_at >= cast(:since as timestamptz))"
              " and not exists (select 1 from chunks ch where ch.item_id = i.id and ch.content_hash = i.content_hash)"
              " and i.tsv @@ to_tsquery('simple', cast(:tsq as text)) order by score desc limit :limit",
    )
    rows = await session.execute(text(sql), _params(owner, f, tsq=tsq, limit=limit))
    out = []
    for r in rows:
        m = r._mapping
        hit = Hit(**{k: m[k] for k in HIT_FIELDS})
        out.append(Passage(hit, f"item:{hit.id}", None, hit.search_text[:1500], float(m["score"] or 0)))
    return out


async def recent(session: AsyncSession, owner: uuid.UUID, f: Filters, limit: int = 12) -> list[Passage]:
    """Newest safe cards, each with its first chunk (card text + understanding)."""
    sql = CHUNKS.format(score=", 0 as score",
                        extra="and ch.ord = 0 order by i.created_at desc limit :limit")
    passages = [_passage(r) for r in await session.execute(text(sql), _params(owner, f, limit=limit))]
    for n, p in enumerate(passages):
        p.score = 1.0 - n / max(len(passages), 1)
    return passages


async def of_kind(session: AsyncSession, owner: uuid.UUID, f: Filters, limit: int = 12) -> list[Passage]:
    """Cards of the given kinds, whether or not their text contains the type word."""
    passages = await recent(session, owner, f, limit)
    if not f.kinds:
        return passages
    seen = {p.hit.id for p in passages}
    sql = BASE.format(
        score=", 0 as score, i.created_at",
        extra="and i.safety_state = 'ok' and i.safety_hash = i.content_hash"
              " and i.kind = any(cast(:kinds as text[]))"
              " and (cast(:since as timestamptz) is null or i.created_at >= cast(:since as timestamptz))"
              " and not exists (select 1 from chunks ch where ch.item_id = i.id and ch.content_hash = i.content_hash)"
              " order by i.created_at desc limit :limit",
    )
    rows = await session.execute(text(sql), _params(owner, f, limit=limit))
    for r in rows:
        m = r._mapping
        hit = Hit(**{k: m[k] for k in HIT_FIELDS if k in m})
        if hit.id in seen:
            continue
        passages.append(Passage(hit, f"item:{hit.id}", None, hit.search_text[:1500], 0.5))
    if "code" in f.kinds:
        passages += await _code_written_as_text(session, owner, f, {p.hit.id for p in passages})
    return passages[:limit]


def _plain_source(hit: Hit) -> str:
    content = hit.content if isinstance(hit.content, dict) else {}
    if hit.kind == "text":
        return content.get("text") or ""
    if hit.kind == "note":
        return content.get("markdown") or ""
    return ""


async def _code_written_as_text(session: AsyncSession, owner: uuid.UUID, f: Filters,
                                seen: set[uuid.UUID], limit: int = 24) -> list[Passage]:
    """Text and notes that are source code typed straight onto the canvas."""
    prose = Filters(f.canvas_id, ["text", "note"], f.since)
    sql = BASE.format(
        score=", 0 as score, i.created_at",
        extra="and i.safety_state = 'ok' and i.safety_hash = i.content_hash"
              " and i.kind = any(cast(:kinds as text[]))"
              " and (cast(:since as timestamptz) is null or i.created_at >= cast(:since as timestamptz))"
              " order by i.created_at desc limit :limit",
    )
    rows = await session.execute(text(sql), _params(owner, prose, limit=limit))
    found = []
    for r in rows:
        m = r._mapping
        hit = Hit(**{k: m[k] for k in HIT_FIELDS if k in m})
        source = _plain_source(hit)
        if hit.id in seen or not looks_like_code(source):
            continue
        found.append(Passage(hit, f"item:{hit.id}", None, source[:4000], 0.5))
    return found


def fuse(*ranked: list[Passage], k: int = 60) -> list[Passage]:
    scores: dict[str, float] = {}
    by_key: dict[str, Passage] = {}
    for passages in ranked:
        for rank, p in enumerate(passages):
            scores[p.key] = scores.get(p.key, 0.0) + 1.0 / (k + rank + 1)
            by_key.setdefault(p.key, p)
    fused = sorted(by_key.values(), key=lambda p: scores[p.key], reverse=True)
    for p in fused:
        p.score = scores[p.key]
    return fused
