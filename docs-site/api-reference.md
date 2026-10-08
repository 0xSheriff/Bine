# API Reference

All BINE HTTP endpoints live under `/api/*`. On Vercel Services (`vercel.json`), `/api/(.*)` routes to the FastAPI backend (`services.backend`) with the `/api` prefix preserved. Locally, `uvicorn bine.app:app --app-dir backend --port 8000` serves the exact same paths.

## Endpoints Overview

| Method & Path | Rate Limit | Description |
| --- | --- | --- |
| `GET /api/quote` | `20 req/min` per IP (15s cache per `(ticker, amount_usd)`) | Frozen `schema_version: "1"` pre-trade guard check |
| `POST /api/execute` | `20 req/min` per IP | Pre-trade guard + Transaction API `/simulate` dry-run + gated `baw` execution |
| `GET /api/decisions` | Uncapped read | Recent decisions, refusals, dry-runs, and live swaps from `decision_log` |
| `GET /api/decisions/{decision_id}` | Uncapped read | Full stored `ExecuteTradeResponse` receipt for a single decision |
| `GET /api/tickers` | Uncapped read (60s catalog cache) | Autocomplete catalog of all 448 BSC tokenized stock tickers (`ondo` + `bstock`) |
| `GET /api/health` | Uncapped read | Service liveness, `schema_version`, `live_mode` status, USD caps, and sample count |

---

## 1. `GET /api/quote` (Frozen Schema v1)

Evaluates whether buying `amount_usd` of `ticker` on BNB Smart Chain (`chainId = "56"`) is safe right now.

### Query Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `ticker` | `string` (required) | - | Underlying stock ticker (for example `NVDA`, `AAPL`, `SPY`) or token symbol (`NVDAB`, `SPYon`). Case-insensitive. |
| `amount_usd` | `number` | `5.5` | USD order size to evaluate (`USDT` on BSC). |
| `details` | `boolean` | `false` | Hidden UI parameter (`include_in_schema=False`). When `true`, attaches `details.issuers` for the UI comparison drawer. Omit in agent calls to receive the strict 13-key contract. |

### Frozen 13-Key Response Contract (`QuoteResponseModel`)

```json
{
  "schema_version": "1",
  "ticker": "NVDA",
  "amount_usd": 5.5,
  "quoted_at": "2026-10-05T15:04:08Z",
  "verdict": "BUY",
  "token": {
    "symbol": "NVDAB",
    "address": "0x02fca66c1d1afb4e2a7884261eb00f63598a7436",
    "issuer": "bstock"
  },
  "shares": 0.023177,
  "all_in_price_per_share": 238.14,
  "reference_price_per_share": 237.3,
  "spread_pct": 0.35,
  "refusal": null,
  "alternative": {
    "symbol": "NVDAon",
    "issuer": "ondo",
    "eligible": true,
    "note": "Also checked NVDAon on Ondo: $0.15 per share less."
  },
  "market": {
    "status": "regular",
    "open": true
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | `"1"` | Frozen contract version string. Always `"1"`. |
| `ticker` | `string` | Normalized underlying equity ticker (`"NVDA"`, `"SPY"`). |
| `amount_usd` | `number` | Requested order size in USD (`USDT` equivalent on BSC). |
| `quoted_at` | `string` | ISO-8601 UTC timestamp when the quote was computed (preserved across the 15-second in-memory cache). |
| `verdict` | `"BUY" \| "REFUSE"` | Deterministic guard decision. Proceed only when `"BUY"`. |
| `token` | `{ symbol, address, issuer } \| null` | Winning BSC token contract (`issuer` is `"ondo"` or `"bstock"`), or `null` when `verdict` is `"REFUSE"`. |
| `shares` | `number \| null` | Expected share-adjusted equity units received (`tokens_received * tokenToShareRatio`), or `null` on `"REFUSE"`. |
| `all_in_price_per_share` | `number \| null` | All-in effective price per share in USD including DEX trade fee and estimated gas, or `null` on `"REFUSE"`. |
| `reference_price_per_share` | `number \| null` | Catalog per-share reference price in USD. |
| `spread_pct` | `number \| null` | Percentage spread of `all_in_price_per_share` versus `reference_price_per_share`, or `null` on `"REFUSE"`. |
| `refusal` | `{ code, message } \| null` | Refusal rule code (one of the 8 rules) and plain-English explanation when `verdict` is `"REFUSE"`, otherwise `null`. |
| `alternative` | `{ symbol, issuer, eligible, note } \| null` | Comparison summary for the second issuer on dual-issuer tickers, or `null` on single-issuer tickers (`AAPL`). |
| `market` | `{ status, open }` | Current RWA session state (`"regular"`, `"premarket"`, `"postmarket"`, `"overnight"`, `"offhours"`, `"paused"`, or `"closed"`). |

---

## 2. `POST /api/execute`

Runs the 4-stage execution pipeline:
1. Evaluates the 8 pre-trade guard rules.
2. Builds unsigned swap calldata (`GET /api/v1/dex/aggregator/swap`) and simulates it via `POST /api/v1/dex/pre-transaction/simulate` (plus `/approve-transaction` simulation if router allowance is zero).
3. If `execute_live: false` (default) or running on Vercel (`VERCEL=1`), stops after the dry-run simulation.
4. Only on a local server where `execute_live: true`, `BINE_LIVE_MODE=true`, `X-Bine-Admin-Token` matches `BINE_ADMIN_TOKEN`, `amount_usd <= BINE_MAX_TRADE_USD` (`$6.00`), and today's cumulative live spend `<= BINE_DAILY_CAP_USD` (`$10.00`), invokes `baw market-order swap` and polls `baw market-order list` until `FINISHED`.

### Request Body (`ExecuteRequest`)

```json
{
  "ticker": "NVDA",
  "amount_usd": 5.5,
  "execute_live": false,
  "admin_token": null
}
```

### Response Fields

Returns `decision_id`, `created_at`, `ticker`, `amount_usd`, `action` (`"dry_run"` or `"execute"`), `verdict`, `recommended_platform`, `recommended_symbol`, `recommended_contract_address`, `refusal_code`, `reason`, `why_others_lost`, `simulation` (`ran`, `passed`, `status`, `fail_reason`, `swap_tx_to`, `swap_tx_gas_limit`, `approval_required`, `approval_simulation_status`, `summary`), `execution` (`attempted`, `live_mode_enabled`, `status`, `order_id`, `tx_hash`, `bsctrace_url`, `baw_command`, `detail`), and `quote`.

Execution `status` values:
- `"DRY_RUN_OK"`: Pre-trade guard and `/pre-transaction/simulate` dry-run passed (`execute_live=false`).
- `"REFUSED"`: Pre-trade guard refused the trade; simulation was skipped.
- `"DRY_RUN_FAILED"`: Pre-trade guard passed, but `/pre-transaction/simulate` reverted for a non-allowance reason.
- `"LIVE_DISABLED"`: `execute_live=true` was requested, simulation passed, but `BINE_LIVE_MODE=false` (or `VERCEL=1` is set on the hosted deployment).
- `"LIVE_BLOCKED_CAP"`: `amount_usd` exceeds `BINE_MAX_TRADE_USD` (`$6.00`) or `BINE_DAILY_CAP_USD` (`$10.00`).
- `"LIVE_SUBMITTED"`: Live swap completed via `baw` with `tx_hash` recorded on BNB Smart Chain.

---

## 3. `GET /api/decisions` and `GET /api/decisions/{decision_id}`

- `GET /api/decisions?limit=5&live_only=false`: Returns `{ "count": N, "decisions": [...] }` ordered newest first. If SQLite is unavailable or empty on a fresh serverless cold start, returns `{ "count": 0, "decisions": [] }` with HTTP `200`.
- `GET /api/decisions/{decision_id}`: Returns the full stored receipt for `decision_id`, or HTTP `404` if not found.

---

## 4. `GET /api/tickers` and `GET /api/health`

- `GET /api/tickers`: Returns `{ "count": 448, "tickers": [{ "ticker": "AAPL", "issuers": ["ondo"], "dual": false }, ...], "catalog_examples": { "share_ratio": ..., "session_closed": ... } }`. Falls back to recorded fixtures in `backend/tests/fixtures/` if offline.
- `GET /api/health`: Returns `{ "status": "ok", "schema_version": "1", "live_mode": false, "max_trade_usd": 6.0, "daily_cap_usd": 10.0, "sample_count": 0, "oldest_sample": null, "newest_sample": null, "now": "2026-10-08T06:00:00Z" }`.

---

## 5. Error Codes (HTTP & Upstream Binance Open API)

| HTTP / Upstream Code | Where It Appears | Meaning & Action |
| --- | --- | --- |
| **HTTP `503`** (`{"detail": "Binance API keys missing or rejected"}`) | `GET /api/quote` | `BINANCE_API_KEY` or `BINANCE_SECRET_KEY` is missing, invalid, or rejected by `web3.binance.com`. Set valid keys in `.env` (or Vercel Environment Variables). |
| **Upstream `401` / `40101`** (`{"code": 40101, "msg": "API Key is required"}`) | `GET /build/api/v1/dex/...` | Returned by `web3.binance.com` when `X-OC-APIKEY` is missing or empty (`docs/raw/rwa_tokens_no_key_2026-10-05.txt`). Translated by BINE into `AuthError` -> HTTP `503`. |
| **Upstream `40102`** (`Invalid signature`) | `GET /build/api/v1/dex/...` | HMAC-SHA256 signature mismatch (for example if `/build` is omitted from the canonical path or query parameter order differs). `BinanceClient` signs the exact `/build/api/...` path. |
| **Upstream `40103`** (`Timestamp expired`) | `GET /build/api/v1/dex/...` | `X-OC-TIMESTAMP` is outside the 5,000 ms `recv_window`. `BinanceClient` generates a fresh timestamp and signature on every retry. |
| **HTTP `403`** | `POST /api/execute` | `execute_live=true` was sent on a non-Vercel server without a matching `X-Bine-Admin-Token` header. |
| **HTTP `429`** | `GET /api/quote`, `POST /api/execute` | Per-IP rate limit exceeded (`20 req/min` on `/api/quote`, `20 req/min` on `/api/execute`). Reuse quotes within the 15-second cache window. |
| **Upstream `40375`** (`Minimum order amount is 5 USD.`) | `/aggregator/quote` | Ondo minimum order rejection; mapped by BINE to `refusal.code = "below_issuer_minimum"`. |
| **Upstream `40374`** (`Insufficient liquidity for a quote.`) | `/aggregator/quote` | Pool cannot fill the requested amount; mapped by BINE to `refusal.code = "depth_thin"` (after `quality_unreliable`). |
| **Upstream `40367` / `40369`** | `/aggregator/quote` | Non-trading session or market phase transition; mapped by BINE to `refusal.code = "market_closed"`. |
