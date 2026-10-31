#!/usr/bin/env bash
# Run from your Mac at the repo root.
#   ./deploy/deploy.sh setup   one-time server setup (packages, user, services, nginx)
#   ./deploy/deploy.sh         build the frontend, ship code, install deps, migrate, restart
# Needs: STASH_HOST=ubuntu@<elastic-ip>  STASH_KEY=~/.ssh/stash.pem  STASH_DOMAIN=stash.example.com (setup only)
# The server's backend/.env is never touched: it is excluded from every sync.
set -euo pipefail

HOST="${STASH_HOST:?set STASH_HOST=ubuntu@<elastic-ip>}"
KEY="${STASH_KEY:?set STASH_KEY=<path to .pem>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST")
RSYNC=(rsync -az --delete -e "ssh -i $KEY" --rsync-path="sudo rsync")

if [[ "${1:-}" == "setup" ]]; then
  DOMAIN="${STASH_DOMAIN:?set STASH_DOMAIN=<your domain>}"
  rsync -az -e "ssh -i $KEY" "$ROOT/deploy/" "$HOST:/tmp/stash-deploy/"
  "${SSH[@]}" "sudo bash /tmp/stash-deploy/setup-server.sh '$DOMAIN'"
  exit 0
fi

echo "==> build frontend"
(cd "$ROOT/frontend" && npm ci --silent && npm run build)

echo "==> ship backend"
"${RSYNC[@]}" \
  --exclude '.env' --exclude '.env.*' --exclude '.venv/' --exclude '__pycache__/' --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' --exclude '.uploads/' --exclude 'tests/.uploads/' \
  "$ROOT/backend/" "$HOST:/srv/stash/backend/"

echo "==> ship frontend"
"${RSYNC[@]}" "$ROOT/frontend/dist/" "$HOST:/srv/stash/frontend/dist/"

echo "==> install, migrate, restart"
"${SSH[@]}" 'set -e
  sudo chown -R stash:stash /srv/stash
  test -f /srv/stash/backend/.env || { echo "missing /srv/stash/backend/.env (see deploy/README.md)"; exit 1; }
  sudo -iu stash bash -c "cd /srv/stash/backend && uv sync --frozen --no-dev --python 3.13 -q && .venv/bin/alembic upgrade head"
  sudo systemctl restart stash-api stash-worker
  for i in $(seq 1 20); do curl -fs http://127.0.0.1:4000/api/v1/health >/dev/null && break; sleep 1; done
  curl -s http://127.0.0.1:4000/api/v1/health/ready; echo
  systemctl is-active stash-api stash-worker'

echo "==> deployed"
