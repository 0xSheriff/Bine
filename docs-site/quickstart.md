# Quickstart

Get BINE running locally in under two minutes and run your first pre-trade check and Transaction API dry-run.

## 1. Prerequisites & Binance Web3 API Keys

- **Python**: `3.11+` (`3.13` tested)
- **Node.js**: `20+` (for the web UI and optional `@binance/agentic-wallet` CLI)
- **Binance Web3 Open API credentials**:
  - `BINANCE_API_KEY`: Your Binance Web3 Open API key (`X-OC-APIKEY`)
  - `BINANCE_SECRET_KEY`: Your HMAC-SHA256 signing secret (`X-OC-SIGN`)

> [!IMPORTANT]
> Without valid keys in `.env`, the Open API path `GET /build/api/v1/dex/market/rwa/tokens` returns HTTP `401` (`code: 40101`, `"API Key is required"`), `/api/quote` returns HTTP `503` (`"Binance API keys missing or rejected"`), and the `bine` CLI prints that single line with exit code `1`.

## 2. Install & Start the Backend (3 Commands)

From the repository root:

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -e backend
printf "BINANCE_API_KEY=<your-key>\nBINANCE_SECRET_KEY=<your-secret>\n" > .env
set -a; source .env; set +a; backend/.venv/bin/uvicorn bine.app:app --app-dir backend --host 0.0.0.0 --port 8000
```

*(If your local network resolver times out on `web3.binance.com`, add `DEV_DNS_FALLBACK=true` before `uvicorn`.)*

## 3. Run Your First Pre-Trade Check

Open a second terminal and run `bine check`:

```bash
# 1. Eligible dual-issuer check ($5.50 NVDA)
backend/.venv/bin/bine check NVDA 5.50
# -> BUY: Buy 0.0232 NVDA (NVDAon on Ondo) for $5.50. All-in $237.99 per share, +0.13% vs $237.69 reference.

# 2. Below issuer minimum refusal ($2.00 AAPL on Ondo)
backend/.venv/bin/bine check AAPL 2
# -> REFUSE [below_issuer_minimum]: Ondo's minimum order is $5 (you entered $2.00). Try $5.50.

# 3. Raw frozen schema_version="1" JSON output
backend/.venv/bin/bine check NVDA 5.50 --json | jq .
```

Exit codes for shell scripts and agents:
- `0`: Verdict is `BUY`
- `2`: Verdict is `REFUSE`
- `1`: Backend unreachable or API keys missing/rejected (`HTTP 503`)

## 4. Run Your First Transaction API Dry-Run

Run `bine buy` (or `POST /api/execute` with `execute_live: false`). By default, `BINE_LIVE_MODE=false`, so `bine buy` runs the pre-trade guard and then simulates the unsigned swap calldata (`GET /api/v1/dex/aggregator/swap`) through `POST /api/v1/dex/pre-transaction/simulate` without broadcasting any transaction:

```bash
backend/.venv/bin/bine buy NVDA 5.50
```

What happens during the dry-run:
1. BINE evaluates all 8 safety rules on `NVDA` at `$5.50`.
2. If the verdict is `REFUSE`, simulation is skipped immediately (`status: "SKIPPED"`).
3. If the verdict is `BUY`, BINE fetches the EVM transaction from `/api/v1/dex/aggregator/swap` and posts it to `/api/v1/dex/pre-transaction/simulate`.
4. When the simulation router (`0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`) has zero USDT allowance, `/simulate` returns `"execution reverted: BEP20: transfer amount exceeds allowance"`. BINE automatically fetches ERC-20 `approve()` calldata from `/api/v1/dex/aggregator/approve-transaction` and simulates the approval (`approval_simulation_status: "SUCCESS"`), returning `status: "DRY_RUN_OK"` (`simulation.status: "REQUIRES_APPROVAL"`, `passed: true`).

## 5. Start the Web UI (Optional)

```bash
npm --prefix frontend install
npm --prefix frontend run dev -- --host 0.0.0.0 --port 5174
```

Then open `http://localhost:5174/guard` to test presets (`NVDA $5.50`, `AAPL $2`, `SPYon $250`, `KLAC $5.50`) and inspect the glass detail panels.
