# Stash AI: what runs today, and the v2 plan

## 1. AI tools in use today

| Tool | Model / version | Used for | Called from |
| --- | --- | --- | --- |
| Bedrock Mantle (OpenAI-compatible) | `zai.glm-5`, temperature 0.2 | Chat answers (stream, 450 output tokens max). Digest "key points" (400 max). | `services/ai/client.py` → `routes/chat.py`, `services/digests/service.py` |
| Voyage embeddings | `voyage-4`, 1024 dims | One vector per card (`document`). One vector per chat question (`query`). "Related cards". | `worker.index_item`, `search.retrieve`, `search.related` |
| Voyage rerank | `rerank-3-lite` | Re-orders chat candidates. Keeps a hit when score ≥ max(0.35, top − 0.3). | `search.retrieve` |
| Bedrock Guardrails | not configured yet (`GUARDRAIL_ID`) | Abuse and adult checks on cards, questions, history and answers. | `services/safety/service.py` |
| Local safety list | word list + adult domains | First layer; the only layer in dev. Blocks adult links before fetch. | `services/safety/local.py` |
| Postgres full text | `tsvector` | Keyword half of hybrid search; all of ⌘K quick find. | `search._keyword_rows` |
| pgvector (Neon) | `vector(1024)`, cosine | Vector half of hybrid search. | `search._vector_rows` |

Non-AI ingestion: the link fetcher reads only `<title>` and `og:` tags (5 s, 1 MB, HTML only). Pillow resizes images and strips EXIF.

Keys you already hold but Stash does not use yet: Mem0 (`memo_api_key`), LlamaParse, Reducto, Unstructured, Browserbase, `voyage-context-4`, `moonshotai.kimi-k2.5` (Mantle, tool calling).

## 2. Workflows today

**Ingest (worker, per card change)**
```
card saved → content_hash changes → job index_item(hash)
  → search_text(kind, content)          # link: title+description+url only; image: caption+filename
  → safety check (local + guardrail)    → safety_state ok | flagged
  → embed whole text (≤20k chars, 1 vector)  → items.embedding, index_state ready
```

**Chat (request, SSE)**
```
question → rate limit, budget, strikes → safety check
  → hybrid retrieve: keyword (OR of words) + vector → RRF → rerank → cutoff (≤8 cards)
  → none? fixed refusal, no model call
  → prompt = system + last turns (re-checked) + numbered cards → glm-5 stream
  → output checked every ~240 chars → citations limited to retrieved ids → saved to chat_messages
```

**Digest (worker, daily/weekly)**: cards in period, grouped by canvas, plus reminders, plus one `complete()` for key points from safe cards only.

## 3. Gaps

1. **Thin ingestion.** A link is indexed by its title and meta description, not the article. Images have no text unless the user writes a caption. PDFs aren't supported. One vector per card means a long note is a single blurry vector.
2. **Not agentic.** Chat is one fixed path: retrieve → answer. It can't search twice, filter by canvas, date or kind, open a card, compare two cards, or act (make a card, set a reminder).
3. **No memory.** Each conversation is the last few turns only. Nothing is learned about the user: their projects, preferences, or what they've asked before.
4. **Almost no caching.** Every question re-embeds and re-reranks. The same link saved by two users is fetched twice. Digests re-summarise unchanged cards.
5. **No traces or evals.** No golden set, no per-request record of which cards, prompt version or model, so quality changes can't be measured.

## 4. v2 design

### 4.1 Better ingestion

| Card | v2 extraction |
| --- | --- |
| Link (article) | Fetch the body (2 MB cap), extract the main text with `trafilatura`. Store the text and a word count. |
| Link (JS-heavy page) | Fallback to Browserbase render when extraction returns < 200 words. |
| Link (YouTube) | Transcript when available, else title and description. |
| Link (PDF) / uploaded PDF | New `file` card kind. Docling for text PDFs, LlamaParse `cost_effective` for scans. |
| Image | Vision model writes a caption and reads visible text (OCR). The result goes through the safety gate before it is stored. |
| Note / code / text | As today, but chunked. |

New table `chunks(id, item_id, owner_id, ord, heading, text, tsv, embedding, model, content_hash)`:
- Split on headings, about 400 tokens with 15% overlap. Every chunk carries the card title and its heading.
- Embed long documents with `voyage-context-4` (each chunk knows its neighbours) or keep `voyage-4`. Decide with the golden set.
- Each card gets an AI **summary** (2–3 sentences) and **tags** in JSON, schema-validated. These feed the card, digests, quick find and the agent.
- Retrieval moves from items to chunks and still returns cards, grouped and deduped, for citations. The `owner_id` filter stays in the SQL.
- Safety: every chunk inherits the card's verdict. A flagged card produces no chunks for AI.

### 4.2 Agentic chat

The model gets a small allowlist of tools and loops (at most 4 steps, 20 s, 1 budget reservation):

| Tool | Kind | Notes |
| --- | --- | --- |
| `search_cards(query, canvas?, kind?, since?)` | read | Hybrid + rerank, returns ids and snippets |
| `open_card(id)` | read | Full chunked text of one safe card |
| `list_canvases()` / `recent_cards(days)` | read | For "what did I save this week" |
| `recall(query)` | read | Memory layer (4.3) |
| `create_note(canvas, markdown)` | **draft** | Shown as a card the user confirms |
| `set_reminder(item?, when, note)` | **draft** | User confirms in the UI |

Rules:
- Tool arguments are validated with the same Pydantic schemas as the REST API.
- Tool results are `SafeText` only: flagged cards never enter the loop.
- Card text is data. The system prompt says so, and the tool output is wrapped and labelled.
- Write actions are drafts that the user confirms in the UI. The model never writes on its own.
- Simple questions skip the loop. A cheap router (rules first, then glm-5 with one short call) decides between the "answer from retrieval" fast path and the agent path.
- Model: try `moonshotai.kimi-k2.5` for tool calling and keep `zai.glm-5` for the final answer. Pick from golden-set scores, not by feel.
- The SSE adds `step` events ("Searching 'pricing' in Launch…", "Reading 3 cards") so the mascot and drawer show progress.

Implementation choice: a plain async loop in `services/agent/` over the OpenAI tools API. LangGraph is optional. The flow is short, and adding a dependency is only worth it if we later need branching or checkpoints.

### 4.3 Memory layer

| Tier | Store | Lifetime | Content |
| --- | --- | --- | --- |
| Working | `chat_messages` (exists) | Conversation | Last N turns, plus a rolling summary once a conversation exceeds N |
| Episodic | `chat_sessions.summary` | Months | One summary per finished conversation, embedded, searchable by `recall` |
| Semantic (user facts) | `memories(id, owner_id, fact, source_msg_id, embedding, confidence, created_at, last_used_at)` | Until deleted | "Working on the Launch canvas", "prefers short answers", "uses Python" |

- After each answer, a background job extracts 0–3 facts as JSON. Each fact is checked for safety and deduped against existing facts by vector similarity. A newer contradicting fact replaces the old one.
- Before answering, the top 5 facts relevant to the question go in the system prompt.
- Users see and delete memories in Settings → Memory, with an off switch. Deleting a card or account removes facts sourced from it.
- Default store: Postgres (Neon), the same as cards: one database, one delete path, data stays with us. Mem0 is an option, but it sends facts outside our region and adds a second deletion path, so it stays optional behind the same interface.

### 4.4 Caching

| Cache | Key | Store | TTL / invalidation |
| --- | --- | --- | --- |
| Embedding cache | `sha256(model + input_type + text)` | `embedding_cache` table | Forever (deterministic). Saves Voyage cost on re-edits and duplicate links. |
| Query embedding | same key, `query` | in-process LRU (1k) + table | 1 day |
| Link fetch | normalized URL | `link_cache(url, metadata, text, fetched_at)` shared across users (public pages only, no cookies sent) | 7 days; refresh on demand |
| Rerank | `sha256(query + sorted chunk hashes)` | LRU | 10 min |
| Retrieval | `owner + scope + query + corpus_version` | LRU | Until any card in scope changes (`corpus_version` = max `updated_at`) |
| Answer (exact) | `owner + scope + normalized question + corpus_version + prompt_version + model` | `answer_cache` table | 24 h; never shared between users |
| Card summary / tags / caption | `content_hash + prompt_version` | columns on items | Until content changes |
| Digest key points | `owner + period + hash of card hashes` | `digest_runs` | Per period |
| Provider prompt cache | Stable system prompt prefix first, cards after | Mantle (if supported) | Provider-managed |

No semantic answer cache. Near-match questions can return a plausible but wrong answer.

Redis comes later, only when there's more than one API instance. The LRUs are per process until then.

### 4.5 Observability and evals (before tuning anything)

- An `ai_traces` row per request: request id, task, prompt version, model, tool steps, chunk ids, tokens, latency, cache hits, outcome. No raw prompts by default.
- `backend/evals/golden.jsonl`: about 30 questions over a seeded canvas, with expected card ids and must-refuse cases. Score recall@5 and citation faithfulness. `uv run python -m evals` runs it before any model, chunking or prompt change.

## 5. Build order

| Phase | Work | Why first |
| --- | --- | --- |
| 0 | Traces + golden set | Every later change is measured |
| 1 | Caches: embedding, link, query, answer | Cheap, immediate cost and latency win, no quality risk |
| 2 | Ingestion: article text, chunks table, summaries/tags, image captions/OCR | The biggest quality jump. Agents can't find what was never indexed. |
| 3 | Memory layer + Settings → Memory | Personal answers. Needs the trace table to debug. |
| 4 | Agent loop with read tools, then draft write tools | Builds on chunks and memory; measured by the golden set |
| 5 | PDFs / file cards, Browserbase fallback, `voyage-context-4` trial | Wider input once the core path is scored |

## 6. Decisions to confirm

1. Memory store: Postgres (recommended) or Mem0.
2. Vision model for image captions/OCR on Mantle (pick one that supports images; check availability in the region).
3. Agent model: `kimi-k2.5` vs `glm-5` with tools. Decide with phase 0's evals.
4. Shared link cache across users: OK for public pages? (It is recommended: no cookies are sent, and pages are public.)
