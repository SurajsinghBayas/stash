"""Shared canvases, card history, save-by-email addresses.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SCHEMA = """
-- A canvas is public read-only while share_token is set. Revoking clears it, so old links stop working.
alter table canvases add column share_token text unique;
alter table canvases add column shared_at timestamptz;

-- The secret part of the person's save-by-email address (save+<token>@<inbound domain>).
alter table users add column inbound_token text unique;

-- Earlier content of a card, one row per content edit (moves and resizes are not history).
create table item_versions (
  id          bigint generated always as identity primary key,
  item_id     uuid not null references items(id) on delete cascade,
  owner_id    uuid not null references users(id) on delete cascade,
  version     integer not null,
  content     jsonb not null,
  created_at  timestamptz not null default now()
);
create index item_versions_item on item_versions (item_id, id desc);

-- The purge job looks for cards and canvases deleted more than 30 days ago.
create index items_deleted on items (deleted_at) where deleted_at is not null;
create index canvases_deleted on canvases (deleted_at) where deleted_at is not null;
"""


def _run(sql: str) -> None:
    bind = op.get_bind()
    for statement in filter(str.strip, sql.split(";")):
        if any(line.strip() and not line.strip().startswith("--") for line in statement.splitlines()):
            bind.exec_driver_sql(statement)


def upgrade() -> None:
    _run(SCHEMA)


def downgrade() -> None:
    _run("""
      drop index if exists canvases_deleted;
      drop index if exists items_deleted;
      drop table if exists item_versions;
      alter table users drop column if exists inbound_token;
      alter table canvases drop column if exists shared_at;
      alter table canvases drop column if exists share_token;
    """)
