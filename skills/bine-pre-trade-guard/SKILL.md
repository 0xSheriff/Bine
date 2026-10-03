---
name: bine-pre-trade-guard
description: "Pre-trade safety guard for tokenized stocks (Ondo Global Markets and Dinari bStocks) on BNB Smart Chain (chainId=56). Use BEFORE executing any swap or market order for a tokenized stock (such as NVDAon, NVDAb, AAPLon, SPYon, TSLAon, TSLAb) to verify market hours, issuer minimum order size ($5 Ondo floor), true share-ratio adjusted cost per share, PMM/AMM depth, and execution spread against the live stock reference price."
metadata:
  author: bine
  version: "1.0.0"
  openclaw:
    requires:
      bins:
        - bine
---

# Bine Pre-Trade Guard Skill

Bine is a deterministic pre-trade safety guard for tokenized stocks on BNB Smart Chain (`binanceChainId="56"`). Before a person or an agent buys a tokenized stock via `baw market-order swap` or a DEX router, Bine checks both **Ondo Global Markets** (`*on`) and **Dinari bStocks** (`*b`) and returns a single `BUY` or `REFUSE` verdict.

## Mandatory Rule

> **Before any `baw market-order swap` on a tokenized stock, call `bine check <TICKER> <AMOUNT_USD>`. If verdict is `REFUSE`, abort and report the refusal message.**

Never bypass a `REFUSE` verdict. Bine refuses trades when:
- `amount_over_cap` — Order exceeds the configured safety cap (`BINE_MAX_TRADE_USD`).
- `below_issuer_minimum` — Order is below Ondo's `$5.00` minimum (`[40375] Minimum order amount is 5 USD`) and no eligible alternative exists.
- `market_closed` — Both issuers have paused primary creation/redemption for the current session.
- `reference_stale` — Stock reference price data is older than 120 seconds.
- `depth_thin` — Neither DEX aggregator nor issuer PMM returned an executable quote (`< $1,000` pool liquidity or empty route).
- `slippage_too_high` — All-in execution price per share exceeds `+1.00%` above reference price or single-trade price impact exceeds `0.50%` (e.g., `SPYon` at `$250` where `LiquidMesh -> Pancakeswap V3` executes `+40.7%` above reference).
- `quality_unreliable` — Token is quarantined due to low 24h volume (`< $1,000`), missing reference price, or `> 10%` raw gap.
- `unknown_ticker` — Ticker is not listed on BSC by Ondo or bStocks.

## Command Routing

| Intent | Command |
|---|---|
| Plain-English pre-trade check | `bine check <TICKER> <AMOUNT_USD>` |
| Structured JSON pre-trade check (`schema_version: "1"`) | `bine check <TICKER> <AMOUNT_USD> --json` |
| Pre-trade check + Transaction API dry-run + guarded buy | `bine buy <TICKER> <AMOUNT_USD>` |
| HTTP API endpoint | `GET /api/quote?ticker=<TICKER>&amount_usd=<AMOUNT_USD>` |
| MCP tool (check only) | `bine_check(ticker="<TICKER>", amount_usd=<AMOUNT_USD>)` |
| MCP tool (dry-run or live buy) | `bine_buy(ticker="<TICKER>", amount_usd=<AMOUNT_USD>, confirm=False)` |

## Workflow for Agentic Wallet (`baw`) Swaps

1. **Run the pre-trade guard first** (works with zero Binance keys via hosted `BINE_API_URL`, or direct mode when keys are present):
   ```bash
   bine check NVDA 5.50 --json
   ```
2. **Inspect `verdict`**:
   - If `"verdict": "REFUSE"`, **STOP IMMEDIATELY**. Report `refusal.code` and `refusal.message` to the user. Do not call `baw market-order swap`.
   - If `"verdict": "BUY"`, read the winning `token.address`, `token.symbol`, `token.issuer`, `shares`, and `all_in_price_per_share`.
3. **Execute or dry-run**:
   - Prefer `bine buy <TICKER> 5.50`, which runs `/api/v1/dex/pre-transaction/simulate` first and only invokes `npx --yes @binance/agentic-wallet@1.10.0 market-order swap --fromTokenQty <AMOUNT_USD> --fromToken 0x55d398326f99059fF775485246999027B3197955 --toToken <token.address> --binanceChainId 56 --slippage 0.5 --mev true --gasLevel MEDIUM --json` after simulation passes and live mode is enabled.
