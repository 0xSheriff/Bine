# Bine Deployment Guide

Bine runs as a **single stateless FastAPI web service** (`uvicorn bine.app:app`) with an optional SQLite or Postgres database used only for the `decision_log` audit table. No background sampler or worker process is required — `/api/quote` fetches RWA token metadata live on demand with a 60-second in-memory cache.

---

## 1. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BINANCE_API_KEY` | Yes | — | Binance Web3 Open API key (`X-MBX-APIKEY`) |
| `BINANCE_SECRET_KEY` | Yes | — | Binance Web3 Open API HMAC-SHA256 secret |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./bine.db` | SQLite file or `postgresql://...` for `decision_log` |
| `BINE_LIVE_MODE` | No | `false` | Keep `false` on public deployments; set `true` only for verified live Agentic Wallet swaps |
| `BINE_MAX_TRADE_USD` | No | `6.0` | Hard USD cap per quote and execution |
| `BINE_ADMIN_TOKEN` | Conditional | `""` | Required via `X-Bine-Admin-Token` header whenever `execute_live=true` |
| `BINE_CORS_ORIGINS` | No | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed browser origins |

---

## 2. Deploy on Railway / Render / Fly.io (Single Service)

1. Point a single **Web Service** at `/backend`:
   - **Build Command**: `pip install -e .` (add `pip install asyncpg` if using Postgres)
   - **Start Command**: `uvicorn bine.app:app --host 0.0.0.0 --port ${PORT:-8000}`
2. Set `BINANCE_API_KEY`, `BINANCE_SECRET_KEY`, and `BINE_LIVE_MODE=false` in the service environment.
3. Optional: attach a small SQLite volume or managed Postgres (`DATABASE_URL`) to persist `decision_log` across restarts.

---

## 3. Deploy on a Linux VM (`systemd`)

```bash
cd /opt/bine/backend
python3 -m venv .venv
.venv/bin/pip install -e .
BINE_LIVE_MODE=false .venv/bin/uvicorn bine.app:app --host 0.0.0.0 --port 8000
```
