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

## 4. Post-Deploy Verification Checklist

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
