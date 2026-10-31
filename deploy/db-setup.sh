#!/usr/bin/env bash
# Create or repair the app's database and login so they match DATABASE_URL in backend/.env. Safe to run again.
# Run on the server: sudo bash /srv/stash/deploy/db-setup.sh [master-user]   (master user defaults to postgres)
set -euo pipefail

ENV_FILE="${ENV_FILE:-/srv/stash/backend/.env}"
MASTER="${1:-postgres}"

URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
[[ -n "$URL" ]] || { echo "DATABASE_URL not found in $ENV_FILE"; exit 1; }

# host, port, db, user, password from the URL (percent-decoded), one per line
{ read -r HOST; read -r PORT; read -r DB; read -r APP_USER; read -r APP_PW; } < <(python3 -c '
import sys
from urllib.parse import urlsplit, unquote
u = urlsplit(sys.argv[1])
print(u.hostname); print(u.port or 5432); print(u.path.lstrip("/")); print(unquote(u.username or "")); print(unquote(u.password or ""))
' "$URL")
[[ -n "$APP_USER" && -n "$APP_PW" ]] || { echo "DATABASE_URL has no user or password"; exit 1; }

read -rsp "Master password for $MASTER@$HOST: " MASTER_PW; echo
export PGPASSWORD="$MASTER_PW" PGSSLMODE=require PGCONNECT_TIMEOUT=10

echo "==> database $DB"
psql -h "$HOST" -p "$PORT" -U "$MASTER" -d postgres -v ON_ERROR_STOP=1 -q -v db="$DB" <<'SQL'
SELECT format('CREATE DATABASE %I', :'db') WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db') \gexec
SQL

echo "==> login $APP_USER, pgvector, ownership"
psql -h "$HOST" -p "$PORT" -U "$MASTER" -d "$DB" -v ON_ERROR_STOP=1 -q \
  -v app_user="$APP_USER" -v app_pw="$APP_PW" -v db="$DB" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'app_user') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user') \gexec
ALTER ROLE :"app_user" WITH LOGIN PASSWORD :'app_pw';
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL ON DATABASE :"db" TO :"app_user";
ALTER SCHEMA public OWNER TO :"app_user";
SQL

echo "==> check: connect as $APP_USER"
PGPASSWORD="$APP_PW" psql -h "$HOST" -p "$PORT" -U "$APP_USER" -d "$DB" -tAc \
  "select 'ok: ' || current_user || ' on ' || current_database() || ', pgvector ' || coalesce((select extversion from pg_extension where extname = 'vector'), 'missing')"
