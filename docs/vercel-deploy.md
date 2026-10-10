# Deploying BINE on Vercel

BINE uses **Vercel Services** (`vercel.json` at the repository root) to serve the Vite React frontend (`frontend/`) and the FastAPI pre-trade guard backend (`backend/`) from a single project and domain.

## 1. Vercel Project Settings

When importing the GitHub repository (`Bine`) in the Vercel Dashboard:

- **Project Name**: `bine`
- **Root Directory**: `./` (repository root, where `vercel.json` lives)
- **Framework Preset**: `Services` (auto-detected from the `services` block in `vercel.json`; if prompted in older project creation wizards, select `Services` or `Other` and let `vercel.json` drive the build)
- **Service Topology (`vercel.json`)**:
  - `frontend`: `root: "frontend"`, `framework: "vite"`, SPA fallback `/(.*) -> /index.html`
  - `backend`: `root: "backend"`, `framework: "fastapi"`, `entrypoint: "main:app"` (also declared in `backend/pyproject.toml` under `[tool.vercel]` as `entrypoint = "bine.app:app"`), dependencies installed from `backend/requirements.txt`
  - Top-level rewrites route `/api/(.*)` to `backend` (preserving the full `/api/...` path) and `/(.*)` to `frontend`.

## 2. Environment Variables

Set the following environment variables in **Project Settings -> Environment Variables** (for Production and Preview):

| Variable | Value on Vercel | Purpose |
| --- | --- | --- |
| `BINANCE_API_KEY` | `<your-read-only-binance-web3-api-key>` | Authenticates signed requests to `https://web3.binance.com/build/api/v1/dex/...` |
| `BINANCE_SECRET_KEY` | `<your-read-only-binance-web3-secret-key>` | HMAC-SHA256 signing secret for the Binance Web3 DEX API |
| `BINE_LIVE_MODE` | `false` | Keeps live swap execution disabled (note: when `VERCEL` is set, the backend also hard-locks `live_mode = False` in code) |
| `BINE_MAX_TRADE_USD` | `6` | Per-trade USD cap (`$6.00` default) |
| `BINE_DAILY_CAP_USD` | `10` | Daily USD cap (`$10.00` default) |
| `BINE_PROBE_SECRET` | `<random-hex-or-uuid>` | Shared secret guarding `POST /api/probe` (required for background probes) |
| `UPSTASH_REDIS_REST_URL` / `TOKEN` *(or `KV_REST_API_URL` / `TOKEN`)* | `https://...` | Upstash Redis REST or Vercel KV REST URL and Token for the 24h probe feed |
| `BINE_DB_PATH` | `/tmp/bine.db` *(optional)* | Ephemeral SQLite path on serverless instances (defaults to `/tmp/bine.db` automatically when `VERCEL` is set) |

### Key Recommendation (Read-Only Binance API Key)

Use a **separate Binance API key** dedicated to the hosted Vercel deployment with **read-only permissions** and **no Trade or Wallet permission**.

- The hosted Vercel app only needs to read RWA token catalogs (`/rwa/tokens`), DEX quotes (`/aggregator/quote`), pool liquidity (`/token/top-liquidity`), unsigned swap/approve calldata (`/aggregator/swap`, `/aggregator/approve-transaction`), and Transaction API dry-run simulations (`/pre-transaction/simulate`).
- Live swaps (`baw market-order swap`) are permanently disabled whenever `VERCEL=1` is present in the runtime environment, even if `BINE_LIVE_MODE=true` is accidentally configured.
- Never set `BINE_ADMIN_TOKEN` or upload `~/.baw` wallet credentials to Vercel.

## 3. Function Region (`fra1`)

Set the serverless function region to **Frankfurt (`fra1`)**:

1. `vercel.json` already sets `"regions": ["fra1"]` both at the top level and under `services.backend.functions["main.py"]`.
2. In the Vercel Dashboard, verify under **Project Settings -> Functions -> Function Region** that **Frankfurt, Germany (`fra1`)** is selected so requests to `web3.binance.com` run from a non-restricted European region with low latency.

## 4. Background Probes (`POST /api/probe` via cron-job.org)

Vercel Hobby plan crons are limited to daily frequency only (`0 0 * * *`). To maintain a continuous 24-hour probe feed on the Refusals page every 30 minutes without a dedicated VPS:

1. **Set Up Remote Store**:
   - Create a free Upstash Redis database (or Vercel KV) and copy the REST URL and REST Token into Vercel environment variables as `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` (or `KV_REST_API_URL` and `KV_REST_API_TOKEN`).
2. **Set Probe Secret**:
   - Set `BINE_PROBE_SECRET` in Vercel environment variables to a random secret token.
3. **Configure cron-job.org**:
   - Create a free account at [cron-job.org](https://cron-job.org).
   - Create a new cron job:
     - **Title**: `BINE 30-Minute Background Probe`
     - **URL**: `https://<your-vercel-domain>/api/probe`
     - **Execution schedule**: Every 30 minutes (`*/30 * * * *`)
     - **Request Method**: `POST`
     - **HTTP Headers**: Add header `Authorization: Bearer <your-BINE_PROBE_SECRET>`
4. **How It Works**:
   - Each call probes at most 4 rotating tickers (from `NVDA`, `SPY`, `AAPL`, `KLAC`, `NFLX`, `PPLT`, `CVNA`, `NOW`), 1.0 second apart, with automatic retry on HTTP 429.
   - Merges probe results into the single 24-hour JSON document in the remote store under key `probe:recent_24h` with `EX 86400` TTL, pruning entries older than 24 hours.
   - If regional restrictions (`40304`) or key errors (`40104`) occur, the probe immediately aborts with HTTP 503 and records nothing to the store.
   - `GET /api/recent` reads from the store (cached for 60 seconds) and feeds the "Last 24 hours" live strip on the Refusals page.

## 5. Post-Deploy Verification Checklist

After deploying to Vercel, run these four checks against your deployment URL (`https://<your-vercel-domain>`):

1. **Health & Live Mode Lock (`/api/health`)**
   ```bash
   curl -s "https://<your-vercel-domain>/api/health" | jq .
   ```
   Confirm `status` is `"ok"` and `live_mode` is `false`.

2. **Live Pre-Trade Check on `/guard` (`NVDA`, `$5.50`)**
   - Open `https://<your-vercel-domain>/guard?ticker=NVDA&amount=5.5` in a browser (or click **NVDA** and **Check trade**).
   - Confirm a live `schema_version: "1"` quote card renders (`BUY` during regular/eligible sessions or `REFUSE` with a plain-English reason when closed or spread is wide) and the header chip reads `Live trading: OFF`.

3. **Hard Refresh on `/guard` (SPA Rewrite Check)**
   - Press `Cmd+Shift+R` (`Ctrl+Shift+R`) on `https://<your-vercel-domain>/guard` and `https://<your-vercel-domain>/receipts`.
   - Confirm the SPA loads with HTTP `200` (no Vercel `404: NOT_FOUND`).

4. **Refusals Catalog (`/refusals`)**
   - Open `https://<your-vercel-domain>/refusals`.
   - Confirm all 8 refusal rules and recorded refusal cards render with zero console errors, and clicking **Run this live** navigates to `/guard` and runs a fresh check.
