#!/usr/bin/env bash
# One-time hardening of the EC2 host. Safe to run again. Run on the server as root:
#   sudo bash /srv/stash/deploy/harden-server.sh
#
# - SSH: keys only, no root login, no password or keyboard-interactive auth, fewer auth tries
# - fail2ban: bans IPs that keep failing SSH logins or keep hitting nginx rate limits
# - unattended-upgrades: security patches install automatically
# - ufw: only SSH, HTTP and HTTPS are open (the AWS security group stays the first line of defence)
# - kernel: SYN-flood protection, no ICMP redirects or source routing, reverse-path filtering
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run as root: sudo bash $0"; exit 1; }

echo "==> packages"
DEBIAN_FRONTEND=noninteractive apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -yq fail2ban unattended-upgrades ufw

echo "==> ssh"
cat > /etc/ssh/sshd_config.d/10-stash-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
EOF
sshd -t
systemctl reload ssh 2>/dev/null || systemctl reload sshd

echo "==> automatic security updates"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

echo "==> fail2ban"
cat > /etc/fail2ban/jail.d/stash.local <<'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true

# Clients that keep tripping nginx's limit_req (deploy/nginx/stash-limits.conf) are banned at the firewall.
[nginx-limit-req]
enabled = true
logpath = /var/log/nginx/error.log
maxretry = 20
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

echo "==> firewall"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo "==> kernel network settings"
cat > /etc/sysctl.d/90-stash-hardening.conf <<'EOF'
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
EOF
sysctl --system -q

echo "==> done"
ufw status verbose | head -12
fail2ban-client status
