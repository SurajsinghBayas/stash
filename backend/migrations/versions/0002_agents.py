"""AI pipeline v2: card understanding, chunks, caches, memory.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCHEMA = """
alter table users add column memory_enabled boolean not null default true;

-- What the reader / vision agents understood about a card, for the content hash in `ai_hash`.
alter table items add column ai jsonb not null default '{}'::jsonb;
alter table items add column ai_hash text;

-- Fetched pages, shared by every user who saves the same public URL (no cookies are ever sent).
create table link_cache (
  url_norm    text primary key,
  final_url   text not null,
  meta        jsonb not null default '{}'::jsonb,
  body        text,
  word_count  integer not null default 0,
  fetched_at  timestamptz not null default now()
);
create index on link_cache (fetched_at);

-- Retrieval unit. Rows exist only for text that passed the safety check for the card's current content_hash.
create table chunks (
  id            bigserial primary key,
  item_id       uuid not null references items(id) on delete cascade,
  owner_id      uuid not null references users(id) on delete cascade,
  content_hash  text not null,
  ord           smallint not null,
  source        text not null,
  heading       text,
  body          text not null,
  tsv           tsvector generated always as (to_tsvector('simple', coalesce(heading, '') || ' ' || body)) stored
);
create index on chunks (item_id);
create index on chunks (owner_id);
create index on chunks using gin (tsv);

-- Voyage vectors by sha256(model, input type, text): deterministic, so cached forever (pruned when unused).
create table embedding_cache (
  key      text primary key,
  vector   real[] not null,
  used_at  timestamptz not null default now()
);
create index on embedding_cache (used_at);

-- Long-term facts about a user, extracted from chat. Only text that passed the safety check is stored.
create table memories (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references users(id) on delete cascade,
  fact               text not null,
  kind               text not null default 'other',
  source_message_id  bigint references chat_messages(id) on delete set null,
  vector             real[],
  created_at         timestamptz not null default now(),
  last_used_at       timestamptz
);
create index on memories (user_id, created_at desc);

-- Exact-match answers. The key includes the corpus version, so any card change misses the cache.
create table answer_cache (
  key         text primary key,
  user_id     uuid not null references users(id) on delete cascade,
  answer      text not null,
  sources     jsonb not null,
  cited       uuid[] not null default '{}',
  created_at  timestamptz not null default now()
);
create index on answer_cache (created_at);
create index on answer_cache (user_id);
"""

VECTOR = """
alter table chunks add column embedding vector(1024);
create index chunks_embedding_hnsw on chunks using hnsw (embedding vector_cosine_ops);
"""


def upgrade() -> None:
    bind = op.get_bind()
    for statement in filter(str.strip, SCHEMA.split(";")):
        bind.exec_driver_sql(statement)
    has_vector = bind.execute(text("select 1 from pg_extension where extname = 'vector'")).scalar()
    if has_vector:
        for statement in filter(str.strip, VECTOR.split(";")):
            bind.exec_driver_sql(statement)


def downgrade() -> None:
    for table in ("answer_cache", "memories", "embedding_cache", "chunks", "link_cache"):
        op.execute(f"drop table if exists {table} cascade")
    op.execute("alter table items drop column if exists ai, drop column if exists ai_hash")
    op.execute("alter table users drop column if exists memory_enabled")
