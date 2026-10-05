# Bine

**Bine is a pre-trade safety guard for tokenized stocks on BNB Smart Chain (`chainId="56"`) that tells humans and AI agents whether a tokenized stock is safe to buy right now, what they will actually receive per share, and if not, why not.**

---

## Run it in 3 commands

```bash
git clone <repo-url> bine && cd bine && python3 -m venv .venv && .venv/bin/pip install -e backend
cp .env.example .env && (.venv/bin/uvicorn bine.app:app --app-dir backend --port 8000 &)
.venv/bin/bine check NVDA 5.50
```

Set `BINANCE_API_KEY` and `BINANCE_SECRET_KEY` in `.env` before starting `uvicorn`. `bine` and `bine-mcp` connect to `BINE_API_URL` (default `http://localhost:8000`). If `http://localhost:8000` is not running, `bine` prints a single line showing how to start it (`uvicorn bine.app:app --app-dir backend --port 8000`). Optional single-service hosting notes are in [`docs/optional-hosting.md`](docs/optional-hosting.md).

---

## Local URL & Web Routes

- **Local API & Web App**: `http://localhost:8000` (frontend dev server: `http://localhost:5173`)
- **Routes**:
  - `/` — Pre-trade guard (`NVDA` at `$5.50` default) + Transaction API `/simulate` dry-run
  - `/integrate` — Copy-paste snippets for `curl`, `bine`, MCP config JSON, Wallet Skill install, and frozen v1 schema
  - `/refusals` — Live refusal cards fetched from `GET /api/quote` and `/api/tickers` (`below_issuer_minimum`, `slippage_too_high`, `quality_unreliable`, share-ratio trap, `market_closed`)
  - `/receipts` — Read-only list of executed on-chain trades with `tx_hash` and BscTrace links (dry-runs excluded)

---

## Plug-and-Play Surfaces

### 1. HTTP API (`schema_version: "1"`)

```bash
curl -s "http://localhost:8000/api/quote?ticker=NVDA&amount_usd=5.50" | jq .
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
        "BINE_API_URL": "http://localhost:8000"
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

---

## Verified On-Chain Execution & Evidence Artifacts

- **Dry-run artifact (`docs/dry_run_nvda_2usd.json`)**: `"passed": true` with `"fail_reason": "execution reverted: BEP20: transfer amount exceeds allowance"` is the expected pre-approval state when simulating raw `/api/v1/dex/aggregator/swap` calldata before USDT is approved to the router (`0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`), and the approval simulation (`"approval_simulation_status": "SUCCESS"`) returned `SUCCESS`.
- **Live `$2` `NVDAB` swap artifact (`docs/live_swap_nvda_2usd.json`) & reconciliation note**: First-time swaps run an `approve` tx (`0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64`) before the `swap` tx (`0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506`, BSC Block `125555002`). `baw market-order swap` returns the parent `orderId` (`26100300001937918699`), `--orderId` on it returns an empty list, and only `baw market-order list --json` shows the child (`orderId` `26100300001937918737`). The first live `$2` `NVDAB` swap recorded the parent `orderId` (`26100300001937918699`) and no `txHash`; `docs/live_swap_nvda_2usd.json` and `DecisionLog #16` were reconciled afterwards from `baw market-order list` (child `orderId` `26100300001937918737`) and the BSC receipt for `0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506`. Untouched `baw` outputs and the commands that produced them are kept in `docs/raw/`.
- **Share-ratio balance reconciliation**: `baw wallet balance` shows `0.00851201289192116` `NVDAB`, while `eth_call` `balanceOf(0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730)` returns `8505393792444895` wei (`0.0085053938` raw tokens). The gap equals `tokenToShareRatio` `1.0007782237528078` (`0.008505393792444894 * 1.0007782237528078 = 0.00851201289192116`).

