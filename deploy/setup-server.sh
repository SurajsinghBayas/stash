#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 EC2 instance. deploy.sh runs it as root: `./deploy/deploy.sh setup`.
# Safe to run again: every step checks before it changes anything.
set -euo pipefail

DOMAIN="${1:?usage: setup-server.sh <domain>}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> packages"
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -yq nginx rsync curl postgresql-client certbot python3-certbot-nginx

echo "==> swap (2 GB; the reader agent and dependency installs need headroom on a small instance)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q /swapfile /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

echo "==> uv"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh

echo "==> stash user and directories (home is /srv/stash so uv's Python lives outside /home)"
id stash >/dev/null 2>&1 || useradd --system --home-dir /srv/stash --shell /bin/bash stash
mkdir -p /srv/stash/backend /srv/stash/frontend/dist
chown -R stash:stash /srv/stash

echo "==> systemd services"
install -m 644 "$HERE/systemd/stash-api.service" "$HERE/systemd/stash-worker.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable stash-api stash-worker

echo "==> nginx"
sed "s/DOMAIN/$DOMAIN/g" "$HERE/nginx/stash.conf" > /etc/nginx/sites-available/stash
ln -sf /etc/nginx/sites-available/stash /etc/nginx/sites-enabled/stash
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
# The production TLS config (deploy/nginx/stash-tls.conf, headers, rate limits) is installed by remote-deploy.sh
# on the first deploy after certbot has issued the certificate.

echo "==> done. Next: put backend/.env in place, run ./deploy/deploy.sh, then certbot (see deploy/README.md)."
