# How BINE Decides (The 8 Safety Rules)

Every call to `GET /api/quote`, `POST /api/execute`, `bine check`, or `bine_check` evaluates **8 deterministic refusal rules** defined in `backend/bine/quote_engine.py` and `backend/bine/quality.py`.

If **any** rule fails on a single-issuer stock, or if **both** issuers fail on a dual-issuer stock (`Ondo` and `bStocks`), BINE returns `verdict: "REFUSE"` with the first failing rule's `code` and a plain-English `message`.

## Summary Truth Table

This table matches the output of `scripts/verify_rules_truth_table.py`, `GUARD_RULE_DEFINITIONS` in `frontend/src/lib/humanize.ts`, and the backend constants in `backend/bine/quote_engine.py` and `backend/bine/quality.py`:

| # | Refusal Code | Plain-English Label | Backend Constant & Trigger |
| --- | --- | --- | --- |
| 1 | `amount_over_cap` | Order size cap | `amount_usd <= 0` or `amount_usd > MAX_QUOTE_USD` (`$2,500.00`) |
| 2 | `below_issuer_minimum` | Issuer minimum order (`Below issuer minimum`) | Upstream code `40375` (`Minimum order amount is 5 USD.` on Ondo; `$0.01` tiebreak floor on bStocks, tested live at `$2.00`) |
| 3 | `market_closed` | Trading session open (`Trading session closed`) | `open_state is not True`, `reason_code != "TRADING"`, `market_status in ("paused", "closed")`, or quote returns `40367` / `40369` |
| 4 | `reference_stale` | Reference price freshness (`Reference price stale`) | `reference_price is None`, `reference_price <= 0`, or sample age `> MAX_SAMPLE_AGE_SECONDS` (`120` seconds) |
| 5 | `quality_unreliable` | Token price & ratio sanity (`Share ratio or price outlier`) | `token_price < $1.00`, `reference_price < $1.00`, `token_to_share_ratio` outside `0.25x..5.00x` (`MIN_SANE_SHARE_RATIO = 0.25`, `MAX_SANE_SHARE_RATIO = 5.0`), implied ratio divergence `> 1.0%`, or 24h catalog volume `< $1,000,000` |
| 6 | `depth_thin` | On-chain pool depth (`Order-book depth too thin`) | Quote returns `40374` (`Insufficient liquidity for a quote`), `tokens_out <= 0`, `shares_out <= 0`, AMM pool depth `< $10,000` (`MIN_LIQUIDITY_USD`), AMM depth `< 10x` order (`MIN_DEPTH_TO_ORDER_MULTIPLIER`), or 24h RFQ volume `< $1,000,000` (`MIN_CATALOG_24H_VOLUME_USD`) |
| 7 | `slippage_too_high` | All-in slippage vs stock (`Slippage too high`) | `effective_slippage_pct = max(abs(execution_vs_reference_pct), abs(price_impact_pct)) > MAX_SLIPPAGE_PCT` (`1.00%` / `100 bps`) |
| 8 | `unknown_ticker` | Verified BSC token contract (`Ticker not in catalog`) | Ticker or token symbol is not present in the live BNB Smart Chain (`chainId=56`) `ondo` or `bstock` `/rwa/tokens` catalog |

---

## Detailed Rule Breakdown & Recorded Examples

### 1. `amount_over_cap` (Order size cap)
- **Trigger**: `amount_usd <= 0` or `amount_usd > 2500.0` (`MAX_QUOTE_USD = 2500.0` in `backend/bine/quote_engine.py:42`).
- **Why it exists**: Prevents malformed zero/negative amounts and caps single pre-trade checks at `$2,500.00` (while live swaps via `POST /api/execute` are further capped at `BINE_MAX_TRADE_USD = $6.00` per trade and `BINE_DAILY_CAP_USD = $10.00` per UTC day).
- **Example (`NVDA` at `$5,000.00`, `backend/tests/test_quote_engine.py:216`)**:
  > `"Order amount $5,000.00 is over the $2,500 per-check limit."`

### 2. `below_issuer_minimum` (Issuer minimum order)
- **Trigger**: `/api/v1/dex/aggregator/quote` returns business code `40375` (`[40375] Minimum order amount is 5 USD.`) or message containing `"minimum order amount"` (`ONDO_MIN_ORDER_USD = 5.0`, `BSTOCK_MIN_ORDER_USD = 0.01` in `backend/bine/quote_engine.py:45-46`).
- **Why it exists**: Ondo Global Markets enforces a `$5.00` minimum order on its RFQ/PMM routes (`40375`). On a dual-issuer ticker like `NVDA` at `$2.00`, Ondo fails with `below_issuer_minimum` while `NVDAB` (bStocks) succeeds and wins the route (`Decision #16` and `Decision #18`). On an Ondo-only ticker like `AAPL` (`AAPLon`) at `$2.00`, BINE refuses the trade and suggests `$5.50`.
- **Recorded example (`AAPL` at `$2.00`, `bine.db:decision_log#id=15-18`)**:
  > `"Ondo's minimum order is $5 (you entered $2.00). Try $5.50."`

### 3. `market_closed` (Trading session open)
- **Trigger**: Catalog `openState is not True`, `reasonCode != "TRADING"` (such as `"UNSUPPORTED"` or `"MARKET_CLOSED"`), `marketStatus in ("paused", "closed")`, or `/aggregator/quote` returns `40367` (`Token is currently in a non-trading session` / `The stock market is shifting its trading phase`) or `40369`.
- **Why it exists**: Blocks orders when an issuer has paused trading or during session phase transitions where quotes cannot be filled.
- **Recorded example (`ENLVon` / `NVDAon` phase shift in `backend/bine.db:quote_probe#id=19,72` and `ICHRon` in catalog)**:
  > `"[40367] Token is currently in a non-trading session. Expected to open in 0d 14h 28m."` / `"Ondo has paused trading on ICHRon (status: paused, reason: UNSUPPORTED)."`

### 4. `reference_stale` (Reference price freshness)
- **Trigger**: `referencePrice` is missing, `<= 0`, or the catalog sample timestamp is older than `MAX_SAMPLE_AGE_SECONDS = 120` seconds (`backend/bine/quote_engine.py:43`).
- **Why it exists**: Prevents comparing a live DEX execution price against an outdated or missing stock reference price.
- **Example (`backend/tests/test_quote_engine.py:322`)**:
  > `"Reference price for NVDAon is 300s old (limit 120s) - not buying."`

### 5. `quality_unreliable` (Token price & ratio sanity)
- **Trigger**: Assessed by `assess_sample_row()` in `backend/bine/quality.py`:
  - `tokenPrice < $1.00` or `referencePrice < $1.00` (`MIN_RELIABLE_PRICE_USD = 1.00`)
  - `tokenToShareRatio < 0.25` or `tokenToShareRatio > 5.00` (`MIN_SANE_SHARE_RATIO = 0.25`, `MAX_SANE_SHARE_RATIO = 5.0`)
  - Implied ratio `(tokenPrice / referencePrice)` diverges from `tokenToShareRatio` by `> 1.0%` (`RATIO_MATCH_TOLERANCE_PCT = 1.0`)
  - 24h catalog volume `< $1,000,000` when required
- **Why it exists**: Several Ondo tokens use 10x or sub-0.1x share ratios (`KLACon` `10.0261x`, `NFLXon` `10.0000x`, `PPLTon` `10.0000x`, `ENLVon` `0.0667x`). Because `baw` and `/aggregator/quote` unit behavior on extreme share ratios has not been verified with a live fill, BINE refuses any token outside `0.25x..5.00x`.
- **Recorded example (`KLACon` at `$5.50`, `docs/raw/regular_hours_quotes_2026-10-05.jsonl:9` & `frontend/src/data/recorded-refusals.json`)**:
  > `"KLACon has a share ratio of 10.0261. Its token price $20,538.32 is 10.03x the $2,048.49 per-share reference, as the ratio predicts. Ratios outside 0.25-5.00x are not supported by this tool, because quoted amounts for them have not been checked against a live trade. Not buying."`

### 6. `depth_thin` (On-chain pool depth)
- **Trigger**: `/aggregator/quote` returns business code `40374` (`[40374] Insufficient liquidity for a quote.`), returns empty/zero `toTokenAmount`, or `/token/top-liquidity` shows AMM pool depth `< $10,000` (`MIN_LIQUIDITY_USD = 10_000.0`) or `< 10x` the requested `amount_usd` (`MIN_DEPTH_TO_ORDER_MULTIPLIER = 10.0`), unless the issuer routes via PMM/RFQ with `volume_24h >= $1,000,000` (`MIN_CATALOG_24H_VOLUME_USD = 1_000_000.0`).
- **Why it exists**: Stops agents from submitting swaps into illiquid or empty pools.
- **Recorded example (`CVNAon` and `NOWon` at `$5.50`, `docs/raw/regular_hours_quotes_2026-10-05.jsonl:15,17` & `frontend/src/data/recorded-refusals.json`)**:
  > `"No pool on BNB Chain can fill $5.50 of CVNAon right now. Not buying."`

### 7. `slippage_too_high` (All-in slippage vs stock)
- **Trigger**: `effective_slippage_pct = max(abs(execution_vs_reference_pct), abs(price_impact_pct)) > 1.00%` (`MAX_SLIPPAGE_PCT = 1.0` in `backend/bine/quote_engine.py:38`). Note that upstream `priceImpactPercent` is returned as a `0..1` fraction (`"0.2974289557"` = `29.74%`), which BINE multiplies by `100.0`.
- **Why it exists**: Protects buyers when an AMM pool runs out of depth at larger order sizes.
- **Recorded example (`SPYon` at `$250.00` off-hours, `frontend/src/data/recorded-refusals.json` & `backend/bine.db:quote_probe#id=4`)**:
  > `"SPYon (Ondo) quotes $1,087.43 per share vs $772.52 reference (40.76% above reference, limit 1.00%). Not buying."`

### 8. `unknown_ticker` (Verified BSC token contract)
- **Trigger**: Neither `underlyingTicker` nor `tokenSymbol` matches any token in the live BNB Smart Chain (`binanceChainId="56"`) `ondo` or `bstock` `/rwa/tokens` catalog.
- **Why it exists**: Prevents agents from guessing ticker symbols or buying unverified counterfeit token contracts on BSC.
- **Example (`FAKE` at `$25.00`, `backend/tests/test_quote_engine.py:424`)**:
  > `"FAKE is not in the Binance RWA catalog on BNB Chain (checked Ondo and bStocks)."`
