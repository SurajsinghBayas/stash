"""Initial schema: users, auth, canvases, items, jobs, chat, safety, reminders, digests.

Revision ID: 0001
Revises:
"""

from alembic import op
from sqlalchemy import text

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = """
create extension if not exists citext;

create table users (
  id                 uuid primary key default gen_random_uuid(),
  email              citext unique,
  email_verified     boolean not null default false,
  password_hash      text,
  display_name       text,
  avatar_url         text,
  timezone           text not null default 'Asia/Kolkata',
  digest_daily       boolean not null default true,
  digest_weekly      boolean not null default true,
  digest_hour        smallint not null default 8 check (digest_hour between 0 and 23),
  chat_blocked_until timestamptz,
  suspended_at       timestamptz,
  created_at         timestamptz not null default now()
);

create table oauth_accounts (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references users(id) on delete cascade,
  provider         text not null check (provider in ('google','x')),
  provider_user_id text not null,
  created_at       timestamptz not null default now(),
  unique (provider, provider_user_id)
);
create index on oauth_accounts (user_id);

create table refresh_tokens (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users(id) on delete cascade,
  token_hash text not null unique,
  family_id  uuid not null,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create index on refresh_tokens (family_id);
create index on refresh_tokens (user_id);

create table email_tokens (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users(id) on delete cascade,
  purpose    text not null check (purpose in ('verify','reset')),
  token_hash text not null unique,
  expires_at timestamptz not null,
  used_at    timestamptz
);
create index on email_tokens (user_id, purpose);

create table canvases (
  id         uuid primary key default gen_random_uuid(),
  owner_id   uuid not null references users(id) on delete cascade,
  title      text not null default 'Untitled',
  viewport   jsonb not null default '{"x":0,"y":0,"zoom":1}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);
create index on canvases (owner_id, updated_at desc, id) where deleted_at is null;

create table items (
  id                uuid primary key default gen_random_uuid(),
  canvas_id         uuid not null references canvases(id) on delete cascade,
  owner_id          uuid not null references users(id) on delete cascade,
  kind              text not null check (kind in ('link','note','text','code','image')),
  x                 double precision not null,
  y                 double precision not null,
  w                 double precision,
  h                 double precision,
  z                 integer not null default 0,
  content           jsonb not null,
  version           integer not null default 1,
  search_text       text,
  content_hash      text,
  embed_model       text,
  tsv               tsvector generated always as (to_tsvector('simple', coalesce(search_text, ''))) stored,
  index_state       text not null default 'pending' check (index_state in ('pending','ready','failed')),
  safety_state      text not null default 'unchecked' check (safety_state in ('unchecked','ok','flagged')),
  safety_categories text[] not null default '{}',
  safety_hash       text,
  bytes             bigint not null default 0,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz
);
create index on items (canvas_id) where deleted_at is null;
create index on items (owner_id, updated_at desc) where deleted_at is null;
create index on items using gin (tsv);
create index on items (owner_id, ((content->>'url_norm'))) where kind = 'link' and deleted_at is null;

create table jobs (
  id         bigint generated always as identity primary key,
  kind       text not null,
  payload    jsonb not null,
  dedupe_key text unique,
  state      text not null default 'queued' check (state in ('queued','running','done','dead')),
  attempts   integer not null default 0,
  run_after  timestamptz not null default now(),
  locked_at  timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on jobs (state, run_after);

create table chat_messages (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references users(id) on delete cascade,
  canvas_id   uuid references canvases(id) on delete set null,
  role        text not null check (role in ('user','assistant')),
  content     text not null,
  cited_items uuid[] not null default '{}',
  created_at  timestamptz not null default now()
);
create index on chat_messages (user_id, canvas_id, created_at desc);

create table moderation_events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references users(id) on delete cascade,
  source     text not null check (source in ('chat_input','chat_output','item','image','link_domain','digest')),
  item_id    uuid,
  action     text not null check (action in ('blocked','flagged','refused_save','deleted')),
  categories text[] not null default '{}',
  request_id text,
  created_at timestamptz not null default now()
);
create index on moderation_events (user_id, created_at desc);

create table ai_requests (
  id             bigint generated always as identity primary key,
  request_id     text,
  user_id        uuid not null references users(id) on delete cascade,
  task           text not null,
  model          text not null,
  prompt_version text not null,
  item_ids       uuid[] not null default '{}',
  input_tokens   integer,
  output_tokens  integer,
  latency_ms     integer,
  outcome        text not null,
  created_at     timestamptz not null default now()
);
create index on ai_requests (user_id, created_at desc);

create table reminders (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users(id) on delete cascade,
  item_id    uuid references items(id) on delete cascade,
  canvas_id  uuid references canvases(id) on delete cascade,
  note       text not null default '',
  remind_at  timestamptz not null,
  state      text not null default 'pending' check (state in ('pending','sent','cancelled','failed')),
  sent_at    timestamptz,
  created_at timestamptz not null default now()
);
create index on reminders (remind_at) where state = 'pending';
create index on reminders (user_id, remind_at);
create index on reminders (item_id) where state = 'pending';

create table digest_runs (
  user_id      uuid not null references users(id) on delete cascade,
  kind         text not null check (kind in ('daily','weekly')),
  period_start date not null,
  item_count   integer not null,
  sent_at      timestamptz,
  primary key (user_id, kind, period_start)
);
"""

VECTOR = """
create extension if not exists vector;
alter table items add column embedding vector(1024);
create index items_embedding_hnsw on items using hnsw (embedding vector_cosine_ops);
"""


def upgrade() -> None:
    bind = op.get_bind()
    # exec_driver_sql: the schema has literal colons (jsonb defaults) that text() would read as bind parameters.
    for statement in filter(str.strip, SCHEMA.split(";")):
        bind.exec_driver_sql(statement)
    # pgvector is on Neon. A local Postgres without it still works; search falls back to keywords.
    has_vector = bind.execute(text("select 1 from pg_available_extensions where name = 'vector'")).scalar()
    if has_vector:
        for statement in filter(str.strip, VECTOR.split(";")):
            bind.exec_driver_sql(statement)


def downgrade() -> None:
    for table in ("digest_runs", "reminders", "ai_requests", "moderation_events", "chat_messages", "jobs",
                  "items", "canvases", "email_tokens", "refresh_tokens", "oauth_accounts", "users"):
        op.execute(f"drop table if exists {table} cascade")
