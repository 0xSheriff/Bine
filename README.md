# Bine

**Bine is a pre-trade safety guard for tokenized stocks on BNB Smart Chain (`chainId="56"`) that tells humans and AI agents whether a tokenized stock is safe to buy right now, what they will actually receive per share, and if not, why not.**

---

## 3-Command Quickstart (No Binance API Keys Needed)

```bash
python3 -m venv .venv && .venv/bin/pip install -e backend
.venv/bin/bine check NVDA 5.50
.venv/bin/bine check SPYon 250 --json
```

When `BINANCE_API_KEY` and `BINANCE_SECRET_KEY` are not set locally, `bine` and `bine-mcp` automatically query the read-only hosted API (`BINE_API_URL`, default `https://bine-guard.fly.dev`). When keys are present in `.env`, Bine runs in direct signed mode against `https://web3.binance.com/build`.

---

## Hosted URL & Web Routes

- **Hosted API & Web App**: `https://bine-guard.fly.dev`
- **Routes**:
  - `/` — Pre-trade guard (`NVDA` at `$5.50` default) + Transaction API `/simulate` dry-run
  - `/integrate` — Copy-paste snippets for `curl`, `bine`, MCP config JSON, Wallet Skill install, and frozen v1 schema
  - `/refusals` — Live refusal cards fetched from `GET /api/quote` and `/api/tickers` (`below_issuer_minimum`, `slippage_too_high`, `quality_unreliable`, share-ratio trap, `market_closed`)
  - `/receipts` — Read-only list of executed on-chain trades with `tx_hash` and BscTrace links (dry-runs excluded)

---

## Plug-and-Play Surfaces

### 1. HTTP API (`schema_version: "1"`)

```bash
curl -s "https://bine-guard.fly.dev/api/quote?ticker=NVDA&amount_usd=5.50" | jq .
```

```json
{
  "schema_version": "1",
  "ticker": "NVDA",
  "amount_usd": 5.5,
  "quoted_at": "2026-10-03T00:15:00Z",
  "verdict": "BUY",
  "token": {
    "symbol": "NVDAB",
    "address": "0x02fca66c1d1afb4e2a7884261eb00f63598a7436",
    "issuer": "bstock"
  },
  "shares": 0.0235,
  "all_in_price_per_share": 234.94,
  "reference_price_per_share": 234.21,
  "spread_pct": 0.31,
  "refusal": null,
  "alternative": {
    "symbol": "NVDAon",
    "issuer": "ondo",
    "eligible": true,
    "note": "Either works (within 5 bps). Also checked NVDAon on Ondo: $0.06 per share less."
  },
  "market": {
    "status": "offhours",
    "open": true
  }
}
```

### 2. CLI (`bine`)

```bash
bine check NVDA 5.50          # One plain-English line (exit 0 on BUY, exit 2 on REFUSE)
bine check AAPL 2 --json      # Frozen schema_version="1" JSON
bine buy NVDA 5.50            # Pre-trade guard + /pre-transaction/simulate dry-run
```

### 3. MCP Server (`bine-mcp`, stdio JSON-RPC 2.0)

```json
{
  "mcpServers": {
    "bine-pre-trade-guard": {
      "command": "bine-mcp",
      "env": {
        "BINE_API_URL": "https://bine-guard.fly.dev"
      }
    }
  }
}
```

Tools exposed:
- `bine_check(ticker, amount_usd=5.50)`
- `bine_buy(ticker, amount_usd=5.50, confirm=False)`

### 4. Binance Agentic Wallet Skill

```bash
mkdir -p ~/.claude/skills/bine-pre-trade-guard
cp skills/bine-pre-trade-guard/SKILL.md ~/.claude/skills/bine-pre-trade-guard/SKILL.md
```

---

## Screenshots

| View | Light (`1440px`) | Dark (`1440px`) | Mobile (`390px`) |
|---|---|---|---|
| **BUY (`NVDA` `$5.50`)** | `ui_buy_light_1440.png` | `ui_buy_dark_1440.png` | `ui_buy_light_390.png` |
| **REFUSE (`AAPL` `$2.00`)** | `ui_refuse_light_1440.png` | `ui_refuse_dark_1440.png` | `ui_refuse_light_390.png` |
| **REFUSE (`SPYon` `$250.00`)** | `ui_refuse_spyon_light_1440.png` | `ui_refuse_spyon_dark_1440.png` | `ui_refuse_spyon_light_390.png` |
| **Dry-Run Confirm Panel** | `ui_confirm_light_1440.png` | `ui_confirm_dark_1440.png` | `ui_confirm_light_390.png` |

---

## Safety Defaults

- **`BINE_LIVE_MODE=false` by default**: `POST /api/execute` and `bine buy` run `POST /api/v1/dex/pre-transaction/simulate` dry-runs only unless explicitly enabled.
- **`BINE_ADMIN_TOKEN` constant-time gate**: Any request with `execute_live=true` requires a matching `X-Bine-Admin-Token` header (`hmac.compare_digest`), returning `HTTP 403` otherwise.
- **Hard trade caps**: `BINE_MAX_TRADE_USD=6.00` per trade and `BINE_DAILY_CAP_USD=10.00` per UTC day.
- **Rate limits & CORS**: Sliding-window per-IP rate limits (`60 req/min` on `/api/quote`, `20 req/min` on `/api/execute`) and explicit `GET, POST` origin allowlist.
