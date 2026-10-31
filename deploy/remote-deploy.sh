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

env_value() {  # env_value KEY: a value from the app's .env, without quotes or a trailing comment
  sed -n "s/^$1=//p" "$APP/backend/.env" | tail -n1 | sed -e 's/[[:space:]]#.*$//' -e 's/^["'\'']//' -e 's/["'\'']$//' \
    -e 's/[[:space:]]*$//'
}

# Render the managed nginx config from deploy/nginx and install it, but only if `nginx -t` accepts it; otherwise put
# the previous files back. Before the TLS certificate exists the plain-HTTP bootstrap config is kept.
install_nginx() {
  local domain bucket region s3 site tmp
  domain="$(env_value APP_URL | sed -E 's#^https?://##; s#/.*$##')"
  bucket="$(env_value S3_BUCKET)"
  region="$(env_value AWS_REGION)"
  s3=""
  [[ -n "$bucket" ]] && s3="https://$bucket.s3.${region:-ap-south-1}.amazonaws.com"
  [[ -n "$domain" ]] || { echo "APP_URL is not set; leaving nginx as it is"; return 0; }
  if [[ ! -f "/etc/letsencrypt/live/$domain/fullchain.pem" ]]; then
    echo "no TLS certificate for $domain yet; leaving the bootstrap config"
    return 0
  fi
  tmp="$(mktemp -d)"
  sed "s#DOMAIN#$domain#g" "$APP/deploy/nginx/stash-tls.conf" > "$tmp/stash"
  sed "s#S3_ORIGIN#$s3#g" "$APP/deploy/nginx/security-headers.conf" > "$tmp/stash-security-headers.conf"
  cp "$APP/deploy/nginx/stash-proxy.conf" "$tmp/stash-proxy.conf"
  cp "$APP/deploy/nginx/stash-limits.conf" "$tmp/stash-limits.conf"

  local -A dest=(
    [stash]=/etc/nginx/sites-available/stash
    [stash-security-headers.conf]=/etc/nginx/snippets/stash-security-headers.conf
    [stash-proxy.conf]=/etc/nginx/snippets/stash-proxy.conf
    [stash-limits.conf]=/etc/nginx/conf.d/stash-limits.conf
  )
  local changed=0 name
  for name in "${!dest[@]}"; do cmp -s "$tmp/$name" "${dest[$name]}" || changed=1; done
  if (( ! changed )); then echo "nginx config unchanged"; rm -rf "$tmp"; return 0; fi

  mkdir -p /etc/nginx/snippets /var/backups/stash-nginx
  for name in "${!dest[@]}"; do
    [[ -f "${dest[$name]}" ]] && cp -p "${dest[$name]}" "/var/backups/stash-nginx/$name"
    install -m 644 "$tmp/$name" "${dest[$name]}"
  done
  ln -sf /etc/nginx/sites-available/stash /etc/nginx/sites-enabled/stash
  if nginx -t 2>&1; then
    systemctl reload nginx
    echo "nginx config updated"
  else
    echo "nginx rejected the new config; restoring the previous one"
    for name in "${!dest[@]}"; do
      if [[ -f "/var/backups/stash-nginx/$name" ]]; then cp -p "/var/backups/stash-nginx/$name" "${dest[$name]}"
      else rm -f "${dest[$name]}"; fi
    done
    nginx -t && systemctl reload nginx
    rm -rf "$tmp"
    return 1
  fi
  rm -rf "$tmp"
}

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

echo "==> nginx"
install_nginx

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
