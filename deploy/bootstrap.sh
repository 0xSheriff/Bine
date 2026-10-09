#!/usr/bin/env bash
# ==============================================================================
# BINE Production VPS Bootstrap Script
# Target OS: Ubuntu 22.04 LTS / Ubuntu 24.04 LTS
# Run as root (sudo ./deploy/bootstrap.sh)
#
# HARD SECURITY RULES:
# - Never print, copy, or log secrets or .env contents.
# - Never expose internal ports (8000) through firewall.
# ==============================================================================

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Error: This bootstrap script must be run as root (use sudo)." >&2
  exit 1
fi

echo "=== Step 1: System packages update ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gnupg \
  git \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  build-essential \
  ufw \
  fail2ban \
  unattended-upgrades \
  jq \
  dnsutils

echo "=== Step 2: Install Node.js (v20 LTS if not present) ==="
if ! command -v node >/dev/null 2>&1 || [[ $(node -v | cut -d'.' -f1 | tr -d 'v') -lt 20 ]]; then
  echo "Installing Node.js 20.x from NodeSource..."
  mkdir -p /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg --yes
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list
  apt-get update -y
  apt-get install -y nodejs
fi
echo "Node version: $(node -v)"
echo "NPM version: $(npm -v)"

echo "=== Step 3: Install Caddy web server ==="
if ! command -v caddy >/dev/null 2>&1; then
  echo "Installing Caddy from official repository..."
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg --yes
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi
echo "Caddy version: $(caddy version)"

echo "=== Step 4: Create deploy system user and directories ==="
if ! id -u deploy >/dev/null 2>&1; then
  useradd -m -s /bin/bash -d /srv/bine deploy
  echo "Created user 'deploy'."
else
  echo "User 'deploy' already exists."
fi

# Application base directory
mkdir -p /srv/bine
chown -R deploy:deploy /srv/bine
chmod 755 /srv/bine

# Runtime database directory
mkdir -p /var/lib/bine
chown -R deploy:deploy /var/lib/bine
chmod 750 /var/lib/bine

# Environment configuration directory (protected)
mkdir -p /etc/bine
chown -R deploy:deploy /etc/bine
chmod 750 /etc/bine

# Caddy log directory
mkdir -p /var/log/caddy
if id -u caddy >/dev/null 2>&1; then
  chown -R caddy:caddy /var/log/caddy
fi
chmod 755 /var/log/caddy

echo "=== Step 5: Configure firewall (UFW) ==="
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
ufw status verbose

echo "=== Step 6: Configure fail2ban & unattended upgrades ==="
systemctl enable fail2ban
systemctl restart fail2ban
systemctl enable unattended-upgrades
systemctl restart unattended-upgrades

echo "=== Step 7: Configure systemd service ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/bine-api.service" ]]; then
  cp "${SCRIPT_DIR}/bine-api.service" /etc/systemd/system/bine-api.service
  systemctl daemon-reload
  systemctl enable bine-api
  echo "Installed /etc/systemd/system/bine-api.service."
fi

echo "=== Step 8: Configure environment template ==="
if [[ ! -f /etc/bine/bine.env ]]; then
  if [[ -f "${SCRIPT_DIR}/bine.env.example" ]]; then
    cp "${SCRIPT_DIR}/bine.env.example" /etc/bine/bine.env
    chown deploy:deploy /etc/bine/bine.env
    chmod 600 /etc/bine/bine.env
    echo "Created /etc/bine/bine.env from template (mode 0600). Please edit and set API credentials."
  fi
else
  echo "/etc/bine/bine.env already exists; leaving untouched."
fi

echo "=== Step 9: Configure Caddy ==="
if [[ -f "${SCRIPT_DIR}/Caddyfile.bine" ]]; then
  echo "Copying Caddyfile.bine to /etc/caddy/Caddyfile..."
  cp "${SCRIPT_DIR}/Caddyfile.bine" /etc/caddy/Caddyfile
  systemctl enable caddy
fi

echo "=== Bootstrap Complete ==="
echo "Next steps:"
echo "1. Run ${SCRIPT_DIR}/check_egress.sh to verify Binance API reachability."
echo "2. Edit /etc/bine/bine.env to set your BINANCE_API_KEY and BINANCE_SECRET_KEY."
echo "3. Run ${SCRIPT_DIR}/deploy.sh as user 'deploy' to build and launch BINE."
