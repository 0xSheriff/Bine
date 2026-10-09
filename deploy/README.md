# BINE Production VPS Deployment Guide

This guide provides step-by-step instructions for deploying BINE on a dedicated Ubuntu 22.04 LTS or 24.04 LTS server.

The deployment topology consists of:
- **Caddy Web Server**: Handles automatic TLS certificates, security headers, compression (gzip/zstd), static asset delivery (SPA and VitePress docs), and reverse-proxies `/api/*` to the local backend.
- **FastAPI API Daemon**: Runs as an isolated systemd service (`bine-api.service`) under an unprivileged `deploy` user on `127.0.0.1:8000`.
- **Protected Environment**: Configuration stored in `/etc/bine/bine.env` with restricted `0600` permissions.
- **Safety Lock**: `BINE_PUBLIC_DEMO=true` keeps public web instances locked to dry-run mode so real funds cannot be traded from the public web interface.

---

## Prerequisites

1. Fresh Ubuntu 22.04 or 24.04 LTS server with root/sudo access.
2. A DNS record (`A` or `AAAA`) pointing your domain (e.g. `bine.example.com`) to the server IP.
3. Outbound HTTPS (port 443) connectivity to Binance Web3 APIs.
4. Binance Web3 Wallet API Key and Secret Key (read-only keys recommended).

---

## Step-by-Step Setup

### Step 1: Clone Repository

Clone the project to `/srv/bine`:

```bash
sudo git clone https://github.com/kyrian-dev/Bine.git /srv/bine
cd /srv/bine
```

### Step 2: Run Bootstrap Script

The bootstrap script installs Python 3 venv, Node.js 20, Caddy, Fail2ban, UFW, creates the `deploy` user, and sets up system directories:

```bash
sudo ./deploy/bootstrap.sh
```

Firewall status after bootstrap:
- Port 22 (SSH): Open
- Port 80 (HTTP): Open
- Port 443 (HTTPS): Open
- Port 8000 (Internal FastAPI): Blocked from external traffic

### Step 3: Verify Network Egress

Before configuring credentials, confirm your server can reach the Binance Web3 Wallet API:

```bash
./deploy/check_egress.sh
```

- **HTTP 401 (Success)**: API endpoint reached. HTTP 401 is expected for unauthenticated probes.
- **HTTP 403 or 451 (Blocked)**: Upstream WAF or region restriction. Use a server located in an unrestricted region.
- **000 (Timeout)**: Check outbound port 443 firewall rules or server DNS.

### Step 4: Configure Environment Variables

Edit `/etc/bine/bine.env` (created by bootstrap with `chmod 600`):

```bash
sudo nano /etc/bine/bine.env
```

Set your values:

```bash
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_SECRET_KEY=your_binance_secret_key_here

# Keep BINE_PUBLIC_DEMO=true for public hosted servers
BINE_PUBLIC_DEMO=true
BINE_LIVE_MODE=false

# Caps in USD
BINE_MAX_TRADE_USD=6.00
BINE_DAILY_CAP_USD=10.00

# Storage path for SQLite decision log
BINE_DB_PATH=/var/lib/bine/bine.db

# Trusted reverse proxy for rate limiting (Caddy on localhost)
TRUSTED_PROXIES=127.0.0.1,::1

# DNS fallback (leave false unless outbound DNS to web3.binance.com fails)
DEV_DNS_FALLBACK=false
```

Ensure permissions remain restricted:

```bash
sudo chown deploy:deploy /etc/bine/bine.env
sudo chmod 600 /etc/bine/bine.env
```

### Step 5: Configure Domain in Caddy

Set your domain in `/etc/caddy/Caddyfile` or set the `BINE_HOST` environment variable:

```bash
# In /etc/caddy/Caddyfile:
# Replace {$BINE_HOST:localhost} with your domain, e.g. bine.example.com
```

Test Caddy configuration:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
```

### Step 6: Deploy Application

Run the deployment script to build the frontend, build the documentation site, install Python packages, and start services:

```bash
sudo -u deploy ./deploy/deploy.sh master
```

The script automatically polls `http://127.0.0.1:8000/api/health` and verifies that the service is running. If health check fails, it rolls back automatically to the previous commit.

### Step 7: Verify Running Service

Verify health via local loopback:

```bash
curl -s http://127.0.0.1:8000/api/health | jq .
```

Expected output:

```json
{
  "status": "ok",
  "schema_version": "1",
  "live_mode": false,
  "binance_credentials_present": true,
  "max_trade_usd": 6.0,
  "daily_cap_usd": 10.0,
  "sample_count": 0,
  "oldest_sample": null,
  "newest_sample": null
}
```

Verify public domain over HTTPS:

```bash
curl -s https://your-domain.example.com/api/health | jq .
```

---

## Day-2 Operations

### Deploying Updates

To deploy code updates from GitHub:

```bash
cd /srv/bine
sudo -u deploy ./deploy/deploy.sh master
```

### Service Logs

View real-time backend API logs:

```bash
sudo journalctl -u bine-api -f
```

View Caddy web server logs:

```bash
sudo tail -f /var/log/caddy/bine.access.log
```

### Restarting Services

```bash
sudo systemctl restart bine-api
sudo systemctl reload caddy
```

---

## Security Protocol

1. **Credentials Isolation**: API keys exist strictly in `/etc/bine/bine.env` (mode 0600, deploy user). They are never committed to git, logged to disk, or returned in API responses.
2. **Public Demo Lock**: `BINE_PUBLIC_DEMO=true` guarantees that the `/api/execute` endpoint executes simulations only (`status: "LIVE_DISABLED"`).
3. **Internal Port Protection**: Port 8000 is bound strictly to `127.0.0.1` and blocked by UFW from any public network interface.
4. **Rate Limiting**: Requests behind Caddy are tracked using client IPs extracted from trusted `X-Forwarded-For` headers (`60 req/min` for quote, `20 req/min` for execute).
