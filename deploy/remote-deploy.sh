#!/usr/bin/env bash
# Runs ON the server, as root, for every CI deploy. The CI SSH key is locked to this script in
# ~ubuntu/.ssh/authorized_keys (see deploy/README.md, "CI/CD"), so CI can do nothing else on the box.
# The commit to deploy arrives as the SSH command (SSH_ORIGINAL_COMMAND) or as $1; it must be on origin/main.
set -euo pipefail

APP=/srv/stash
SHA="${1:-${SSH_ORIGINAL_COMMAND:-}}"
SHA="${SHA##* }"  # tolerate "deploy <sha>"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "usage: remote-deploy.sh <40-char commit sha>"; exit 2; }

as_stash() { sudo -iu stash bash -c "$1"; }

exec 9>/var/lock/stash-deploy.lock
flock -w 600 9 || { echo "another deploy is still running"; exit 1; }

echo "==> fetch $SHA"
as_stash "cd $APP && git fetch -q origin main"
as_stash "cd $APP && git merge-base --is-ancestor $SHA origin/main" || { echo "$SHA is not on origin/main"; exit 1; }
PREV="$(as_stash "cd $APP && git rev-parse HEAD")"
as_stash "cd $APP && git checkout -q main && git reset -q --hard $SHA"

echo "==> backend: dependencies and migrations"
as_stash "cd $APP/backend && uv sync --frozen --no-dev --python 3.13 -q && .venv/bin/alembic upgrade head"

echo "==> frontend: build"
as_stash "cd $APP/frontend && npm ci --no-audit --no-fund --silent && npm run build --silent"

echo "==> services"
if ! cmp -s "$APP/deploy/systemd/stash-api.service" /etc/systemd/system/stash-api.service \
   || ! cmp -s "$APP/deploy/systemd/stash-worker.service" /etc/systemd/system/stash-worker.service; then
  install -m 644 "$APP/deploy/systemd/stash-api.service" "$APP/deploy/systemd/stash-worker.service" /etc/systemd/system/
  systemctl daemon-reload
fi
systemctl restart stash-api stash-worker

echo "==> health"
for _ in $(seq 1 30); do
  body="$(curl -s localhost:4000/api/v1/health/ready || true)"
  if [[ "$body" == *'"database":"ok"'* ]]; then
    echo "$body"
    systemctl is-active --quiet stash-worker || { echo "worker is not running"; journalctl -u stash-worker -n 30 --no-pager; exit 1; }
    echo "==> deployed $SHA (was $PREV)"
    exit 0
  fi
  sleep 1
done
echo "API did not become healthy. Last response: ${body:-none}"
journalctl -u stash-api -n 40 --no-pager
exit 1
