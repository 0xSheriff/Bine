# BINE — Friction Log

All entries are factual. Timestamps are UTC.

---

## 2026-09-30T16:38Z — First doc read: llms.txt

- **What I tried**: Fetched `https://web3.binance.com/en/dev-docs/llms.txt`
- **What happened**: Returned a concise index of all doc pages with URLs. 45 lines. Useful as a map.
- **Latency**: ~9s (includes DNS + TLS)
- **Notes**: No issues.

## 2026-09-30T16:38Z — Doc read: Authentication page (HTML)

- **What I tried**: Fetched `https://web3.binance.com/en/dev-docs/authentication`
- **What happened**: Page is a React SPA. The fetch returned raw HTML/JS, not readable content. No server-side rendering for the doc content.
- **Page**: https://web3.binance.com/en/dev-docs/authentication
- **How I fixed it**: Used `llms-full.txt` instead, which contains the full authentication docs in markdown.
- **Friction**: Doc pages at `/en/dev-docs/*` are SPAs that return no useful content to non-browser clients. The `llms-full.txt` file is the only machine-readable path. This is not documented anywhere on the llms.txt page.

## 2026-09-30T16:38Z — Doc read: RWA Data API reference (HTML)

- **What I tried**: Fetched `https://web3.binance.com/en/dev-docs/catalog/web3-wallet/api/rest-api/rwa-data`
- **What happened**: Same SPA problem. Got HTML with sidebar navigation showing 6 RWA endpoints (Get RWA Token Issuance Platforms, Get RWA Token Price, Search RWA Token, Get RWA Underlying Info, Get RWA Token List, Get RWA Underlying Market Data) but no request parameters, response schemas, or example responses.
- **Page**: https://web3.binance.com/en/dev-docs/catalog/web3-wallet/api/rest-api/rwa-data
- **How I fixed it**: Not yet fixed. `llms-full.txt` does NOT include the RWA Data API reference at all. The endpoint names are visible from the sidebar HTML but paths, parameters, and response shapes are unknown.
- **Friction**: **Critical gap.** The RWA Data API reference is missing from `llms-full.txt`. The only way to get it is to render the SPA in a browser. For a hackathon centered on tokenized stocks / RWA, the RWA Data API docs being unreachable by LLMs or `curl` is a significant developer experience problem.

## 2026-09-30T16:38Z — Doc read: Agentic Wallet docs

- **What I tried**: Fetched `https://developers.binance.com/en/docs/products/agentic-wallet/welcome` and `https://developers.binance.com/en/docs/products/agentic-wallet/use-cases/trading/stock-trading`
- **What happened**: DNS resolution failed: `lookup developers.binance.com: no such host`
- **Error text**: `dial tcp: lookup developers.binance.com: no such host`
- **How I fixed it**: Not yet fixed. Need to retry with browser-level fetch or network access. The `llms-full.txt` includes a summary of Agentic Wallet capabilities under the "Supported Skills" and "Binance Wallet Skills" sections.
- **Friction**: `developers.binance.com` did not resolve. Could be a temporary DNS issue or the domain may have changed. The agentic wallet docs are critical for the execution layer.

## 2026-09-30T16:39Z — Doc read: llms-full.txt

- **What I tried**: Fetched `https://web3.binance.com/en/dev-docs/llms-full.txt`
- **What happened**: 3036 lines, 144KB. Contains full docs for Authentication, Trading API, Transaction API, Wallet API, Wallet Skills, error codes. Does NOT contain the RWA Data API reference (the `/catalog/web3-wallet/api/rest-api/rwa-data` endpoints).
- **Latency**: ~3s
- **Notes**: This is the authoritative machine-readable doc source. Confirmed API base URL is `https://web3.binance.com/build`, all paths start with `/build/api/v1/...`.

## 2026-09-30T17:09Z — RWA Data API reference obtained from user

- **What I tried**: User opened the SPA page in a browser and pasted the full API reference.
- **What happened**: Got all 6 endpoints with paths, params, and response schemas. Key endpoints: `/api/v1/dex/market/rwa/platforms`, `/price`, `/search`, `/underlying-profile`, `/tokens`, `/underlying-market`.
- **Friction findings**:
  1. **xStocks missing from RWA Data API.** The `platformId` enum only has `ondo` and `bstock`. No `xstock` value. The brief says to compare all three issuers, but xStocks may need a different API path or may only be discoverable through the Trading API search. Needs investigation.
  2. **`referencePrice` is NOT the stock market price.** Both `/price` and `/tokens` describe `referencePrice` as "A per-share converted price derived from the on-chain token price, not an official quote from the traditional stock market." This means `referencePrice` ≈ `tokenPrice / tokenToShareRatio`. If true, comparing `tokenPrice` vs `referencePrice` does NOT measure the gap between on-chain price and the real stock price. We need to verify this with real data — if they're always nearly identical, the "gap" feature needs a different data source.
  3. **`/tokens` is the goldmine endpoint.** Returns tokenPrice, referencePrice, statusInfo (with openState, marketStatus, reasonCode, nextOpenTime), volume24H, marketCap all in one call. This is the sampler's primary endpoint.

## 2026-09-30T17:09Z — OpenAPI schema URL discovered

- **What I tried**: User's paste included a schema download link: `https://web3.binance.com/en/dev-docs/catalog/web3-wallet/api/rest-api/1.0.0/schema.json`
- **What happened**: Not yet fetched. Will try during Phase 0 first-call script.
- **Notes**: If this JSON schema is reachable, it would have been a much faster path than the SPA workaround.

## 2026-10-01T00:39Z — First API call attempt: DNS timeout

- **What I tried**: Ran `python -m scripts.first_call` targeting `GET https://web3.binance.com/build/api/v1/dex/market/rwa/platforms`
- **What happened**: `httpx.ConnectTimeout` (15053 ms) followed by `httpx.ConnectError: [Errno 8] nodename nor servname provided, or not known` (14005 ms, 7 ms).
- **Exact error text**: `httpcore.ConnectError: [Errno 8] nodename nor servname provided, or not known`
- **How I fixed it**: Diagnosed that the local default DNS resolver timed out while `8.8.8.8` resolved `web3.binance.com` (`dnsu8oml1p86w.cloudfront.net` → `108.156.221.129`). Switched DNS / `/etc/hosts` and hardened `scripts/first_call.py` to catch `ConnectError`/`ConnectTimeout` cleanly.

## 2026-10-01T00:48Z — First successful authenticated RWA Data API calls

- **Time from first doc open to first successful API call**: ~8 hours 10 minutes elapsed wall-clock (including user credential setup and SPA doc workaround; ~15 minutes active engineering once RWA endpoint paths were pasted).
- **What I tried**: Executed 4 signed `GET` requests via `BinanceClient` (`X-OC-APIKEY`, `X-OC-TIMESTAMP`, `X-OC-SIGN` with `/build` prefix included in pre-hash):
  1. `GET /api/v1/dex/market/rwa/platforms` → HTTP 200, `code: 0` (**1508 ms**)
  2. `GET /api/v1/dex/market/rwa/tokens?binanceChainId=56&platformId=ondo` → HTTP 200, `code: 0`, 442 tokens (**1632 ms**)
  3. `GET /api/v1/dex/market/rwa/tokens?binanceChainId=56&platformId=bstock` → HTTP 200, `code: 0`, 46 tokens (**1560 ms**)
  4. `GET /api/v1/dex/market/rwa/search?keyword=NVDA` → HTTP 200, `code: 0`, 4 assets across chains/issuers (**636 ms**)
- **Tokenized-stock domain findings from real responses**:
  1. **`referencePrice` vs `tokenPrice` confirmed**: For every single token returned across both Ondo (442 tokens) and bStocks (46 tokens), `referencePrice == tokenPrice / tokenToShareRatio` (e.g. `NOWon`: `tokenPrice=3352.740075`, `tokenToShareRatio=5`, `referencePrice=670.548015`, caused by a 5-for-1 stock split multiplier; `ACNon`: `tokenToShareRatio=1.0308528...` from reinvested dividends). Thus, within a single token record, `tokenPrice / tokenToShareRatio` equals `referencePrice` to floating-point precision—it is **not** an independent traditional stock exchange quote.
  2. **Real price gaps exist across issuers and vs DEX execution**: Comparing the same underlying ticker across Ondo (`referencePrice`) and bStocks (`referencePrice`) on BSC (`chainId=56`, 40 overlapping tickers) reveals genuine cross-issuer price gaps even during `overnight` trading: e.g. `BABA` (`Ondo ref=$108.77` vs `bStock ref=$107.92`, **+0.79% gap**; raw token price gap **+1.69%**), `AVGO` (`Ondo ref=$354.86` vs `bStock ref=$352.83`, **+0.58% gap**), `CRCL` (**-0.15% gap**), `EWY` (**-0.14% gap**).
  3. **Issuer metadata differences (`ondo` vs `bstock`)**:
     - `ondo` returns `statusInfo.marketStatus: "overnight"`, `openState: true`, `reasonCode: "TRADING"`, and populated `nextOpenTime` / `nextCloseTime` timestamps, plus `marketCap` and `peRatioTTM`.
     - `bstock` returns `statusInfo.openState: true` and `reasonCode: "TRADING"`, but `marketStatus: null`, `nextOpenTime: null`, `nextCloseTime: null`, `marketCap: null`, and `peRatioTTM: null`. Our sampler and Agent rules must handle `marketStatus: null` on bStocks without crashing or falsely assuming the market is closed when `openState` is `true`.
  4. **`xStocks` absence**: `/api/v1/dex/market/rwa/platforms` only lists `ondo` (458 tokens on BSC) and `bstock` (87 tickers, 46 returned on BSC `/tokens`). `xStocks` is not returned by `/rwa/platforms` or `/rwa/tokens`—it only appears in the Trading API documentation (`type=2` AMM SWAP mode).

## 2026-10-01T14:03Z — Sampler startup DNS timeout & automatic `8.8.8.8` fallback

- **What I tried**: Started FastAPI + APScheduler (`uvicorn bine.app:app --reload --port 8000`).
- **What happened**: First sampler tick failed with `ConnectTimeout (15023 ms)` and `ConnectError: [Errno 8] nodename nor servname provided, or not known`. Sampler wrote explicit failure rows (`ok=False`) to `bine.db` as designed without crashing the server.
- **How I fixed it**: Added an `anyio.connect_tcp` wrapper in `bine/sampler.py` that resolves `web3.binance.com` via `8.8.8.8` (`nslookup web3.binance.com 8.8.8.8`) with a 5-minute TTL cache while preserving the TLS SNI hostname. Uvicorn auto-reloaded and immediately began recording 488 tokens per tick (~1927 ms latency). Verified `/api/health` (`3,912` samples recorded) and `/api/compare/NVDA` (`cross_token_price_gap_pct: 0.2094%`).

## 2026-10-01T14:50Z — `[40103] Timestamp outside recv_window` after 15s `ConnectTimeout` retry

- **What I tried**: Sampler polled `GET /api/v1/dex/market/rwa/tokens` when attempt 1 experienced a 15,002 ms `ConnectTimeout`.
- **What happened**: Attempt 2 reached the server and returned `TimestampError: [40103] Timestamp outside recv_window. serverTime=2026-10-01T14:50:36.762084309Z`.
- **Why**: Default `X-OC-RECV-WINDOW` on Binance Web3 API is 5,000 ms (5 seconds). When an HTTP client computes `X-OC-TIMESTAMP` and `X-OC-SIGN` once before entering the retry loop and attempt 1 times out after 15 seconds, attempt 2 sends a 15-second-old timestamp, triggering `40103`. Re-signing headers per retry attempt (or setting `X-OC-RECV-WINDOW: 30000`) prevents `40103` on retry.

## 2026-10-01T21:00Z — Step 1 Verification: `referencePrice`, `marketStatus`, `ENLVon`, and SQLite UTC timestamps

- **Verified across 488 recorded fixture tokens (`442` Ondo + `46` bStocks) and `33,598` live `bine.db` rows**:
  1. **Exact meaning of `referencePrice`**: Across **488 / 488 tokens** (`0` exceptions), `referencePrice == tokenPrice / tokenToShareRatio`. It is the per-share equivalent price derived from the token's own on-chain price (adjusting for stock splits like `NFLXon` `10x`, reverse splits like `ENLVon` `0.066667x` (`1/15`), and dividend reinvestment like `ACNon` `1.03085x`). Thus `(tokenPrice - referencePrice) / referencePrice` is mathematically equal to `tokenToShareRatio - 1` and is **never** an oracle price gap.
  2. **Why `ENLVon` looked like a `-93.33%` gap outlier**: `ENLVon` has `tokenPrice = $0.0022938`, `referencePrice = $0.034407`, and `tokenToShareRatio = 0.066667` (a 1-for-15 reverse split on a sub-$0.04 penny stock, paused with `reasonCode: "MARKET_PAUSED"`). Ranking by `(tokenPrice - referencePrice) / referencePrice` surfaced `ENLVon` at `-93.33%` purely because `0.066667 - 1 = -0.9333`.
  3. **Why Ondo showed `"postmarket"` + UI timezone bug**:
     - From `14:10 UTC` (`10:10 EDT`) through `19:52 UTC` (`15:52 EDT`), all 442 Ondo tokens in `bine.db` returned `marketStatus = "regular"`, `openState = true`, `reasonCode = "TRADING"`.
     - At `20:00 UTC` (`16:00 EDT`, NYSE/Nasdaq closing bell), US regular market hours ended. At the `20:02:51 UTC` (`16:02 EDT`) sample tick, Ondo transitioned: `318` tokens to `marketStatus = "postmarket"`, `openState = true`, `reasonCode = "TRADING"`; `124` tokens to `marketStatus = "postmarket"`, `openState = false`, `reasonCode = "UNSUPPORTED"`; and `50` tokens briefly to `marketStatus = "paused"`, `openState = false`, `reasonCode = "MARKET_PAUSED"` (`"Paused for session transition"`).
     - Meanwhile, SQLite returns naive `datetime` objects (`tzinfo=None`), so `row.sampled_at.isoformat()` omitted the `"Z"` UTC suffix (`"2026-10-01T20:02:51.760990"`). Browser `new Date(...)` parsed that naive UTC string as local time (`UTC+1`), shifting every displayed timestamp **1 hour earlier** (`19:02 UTC` / `15:02 EDT`, when US markets *were* still open!) and making `DataMeta` report fresh samples as `60 min old`. Fixed via `_iso_utc()` in `bine/app.py` and `parseUtcDate()` / `formatUtcAndEt()` in `frontend/src/components/shared.tsx`.

## 2026-10-01T21:35Z — Step 4 Quote Engine: Live `/api/v1/dex/aggregator/quote` & `/api/v1/dex/market/token/top-liquidity` Domain Surprises

- **What I tried**: Called `GET /api/v1/dex/aggregator/quote` (`binanceChainId=56`, `fromTokenAddress=0x55d398326f99059fF775485246999027B3197955` USDT 18 decimals, `toTokenAddress=NVDAon / NVDAB`, `amount=25000000000000000000` wei, `userWalletAddress=0xd8dA...`) and `GET /api/v1/dex/market/token/top-liquidity` across 5 dual-issuer tickers (`NVDA`, `TSLA`, `BABA`, `SPY`, `META`) at `$25` and `$250`.
- **What happened & 5 undocumented behaviors discovered**:
  1. **Ondo & bStocks return `executionMode: "SWAP"` via `vendorName: "LiquidMesh"` on BSC (`chainId=56`)**:
     - **Doc page**: `https://web3.binance.com/en/dev-docs/products/trading-api/introduction` states *"Ondo tokens (type=1): Always routed via 3-vendor RFQ (InchFusion + CowSwap + PcsXRfq). All routes return `executionMode=RFQ`."*
     - **Live reality**: All 20 live `/quote` calls on BSC (`NVDAon`, `NVDAB`, `TSLAon`, `TSLAB`, `BABAon`, `BABAB`, `SPYon`, `SPYB`, `METAon`, `METAB` at `$25` and `$250`) returned `vendorName: "LiquidMesh"`, `executionMode: "SWAP"`, and `approveTarget: "0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5"` (routing via `Metric`, `Elfomofi`, `Uniswap V4`, or `PancakeSwap V3`). Latency was `~620–980 ms`.
  2. **`/api/v1/dex/market/token/top-liquidity` returns `liquidityUsd: null` on 100% of Ondo pools**:
     - **Live reality**: For `NVDAon` (8 pools), `TSLAon` (6 pools), `BABAon` (1 pool), `SPYon` (5 pools), and `METAon` (4 pools), every pool is a `Bebop` or `Native` PMM pool where `liquidityUsd` is `null` and `liquidityAmount[].tokenAmount` is `null`.
     - By contrast, `bStocks` (`NVDAB`, `TSLAB`, `BABAB`, `SPYB`, `METAB`) have standard `PancakeSwap V3` and `Uniswap V3` AMM pools alongside `Bebop`/`Native` pools, reporting `$6.21M` AMM TVL for `NVDAB`, `$2.64M` for `BABAB`, `$2.35M` for `TSLAB`, `$1.80M` for `SPYB`, and `$205.6K` for `METAB`.
     - **How I fixed it**: `summarize_liquidity_pools()` in `bine/quote_engine.py` sums non-null AMM `liquidityUsd` when present (`depth_source="amm_pools"`), and falls back to the RWA 24h volume (`depth_source="pmm_rfq_24h_volume"`, minimum `$1M`) when all pools are PMM/RFQ pools with `liquidityUsd: null`.
  3. **`priceImpactPercent` is a `0–1` fractional ratio (`0.2974` = `29.74%`) mislabeled as `Percent` (it does NOT understate)**:
     - **Live reality**: On the 5 `$250` runs for `SPYon` (`Ondo`), `toTokenAmount` (`0.22774` tokens = `0.22970` shares) delivered ~29.1% fewer shares than the `$100` rate (`2.5 * 0.12965 = 0.32413` shares), which corresponds to a `+40.75%` higher execution price per share (`1 / (1 - 0.291) - 1 ≈ +41.0%`). In those responses, `priceImpactPercent` returned `"0.2974289557"`. Thus the field is a `0–1` fraction (`29.74%` share reduction) mislabeled as `Percent` in the field name — it accurately reflects the ~29.7% output drop and does **not** understate when scaled by `100.0`.
     - **How I fixed it**: `_parse_price_impact_pct()` in `bine/quote_engine.py` multiplies `priceImpactPercent` by `100.0` (`"0.2974289557"` → `29.7429%`), and `evaluate_issuer_quote()` computes both `price_impact_pct` (`29.7429%`) and `execution_vs_reference_pct` (`+40.75%`) and sets `effective_slippage_pct = max(abs(execution_vs_reference_pct), abs(price_impact_pct))`. Our deterministic `slippage_too_high` rule (`> 1.00%`) immediately refuses `SPYon` at `$250` while recommending `SPYB` (`bStocks`, `-0.02%` vs ref).
  4. **Why raw `toTokenAmount` comparison is wrong without `tokenToShareRatio`**:
     - In our recorded `$25` `NVDA` fixture (`quote_nvda_ondo_25usd.json` vs `quote_nvda_bstock_25usd.json`), `NVDAB` returned slightly more raw tokens (`0.10806278` tokens) than `NVDAon` (`0.10800374` tokens). However, `NVDAon` has `tokenToShareRatio = 1.00171525` (reinvested dividends) vs `NVDAB` `1.00008368`, so `NVDAon` actually delivered more underlying `NVDA` shares (`0.10818899` shares vs `0.10807182` shares). Multiplying `tokens_received * token_to_share_ratio` before computing `all_in_price_per_share_usd` ensures an apples-to-apples share comparison.
  5. **`/api/v1/dex/market/token/basic-info` is `POST` with query parameters (not `GET`)**:
     - Calling `GET /api/v1/dex/market/token/basic-info` returns HTTP 200 with business error `[000002] unknown error` because the OpenAPI spec (`schema.json` line 1538) defines `/token/basic-info` as `POST` while taking `binanceChainId` and `tokenContractAddress` `in: "query"`.

## 2026-10-01T23:00Z — Step 5 Execution: Transaction API `/simulate`, ERC-20 Allowance Reverts, and Ondo `$5` Minimum Order

- **What I tried**: Implemented `POST /api/execute` in `bine/execution.py` + `bine/app.py` to run the Quote Engine, build unsigned swap calldata via `GET /api/v1/dex/aggregator/swap`, dry-run via `POST /api/v1/dex/pre-transaction/simulate`, enforce per-trade (`$3.00`) and daily (`$10.00`) caps + `BINE_LIVE_MODE=true`, and persist every decision in `decision_log`. Tested live on BSC (`chainId=56`) for `$2.00` `NVDA`.
- **What happened & 3 key findings**:
  1. **Ondo enforces a `$5.00` minimum order (`[40375] Minimum order amount is 5 USD.`) while bStocks executes at `$2.00`**:
     - When quoting `$2.00` of `NVDA`, `NVDAon` (`Ondo`) returned HTTP 200 with business error `code: "40375"`, `msg: "Minimum order amount is 5 USD."`.
     - By contrast, `NVDAB` (`bStocks`) returned a valid `LiquidMesh` `SWAP` quote at `$2.00` (`$233.18/share` all-in, `+0.85%` vs `$231.21` reference price, yielding `0.008652` shares).
     - Our Quote Engine deterministically refused `NVDAon` (`[depth_thin]: No executable DEX route: [40375] Minimum order amount is 5 USD.`) and selected `NVDAB` (`BUY_BSTOCK`) as the only eligible issuer for micro-sized (`<$5`) trades.
  2. **Simulating an ERC-20/BEP-20 swap via `POST /api/v1/dex/pre-transaction/simulate` before router approval**:
     - `GET /api/v1/dex/aggregator/swap` returned a `5,188`-byte calldata payload targeting the `LiquidMesh` router `0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5` (`gas: "450000"`, `gasPrice: "50343340"`).
     - Passing `data.tx` directly to `POST /api/v1/dex/pre-transaction/simulate` (`{"binanceChainId": "56", "evmTx": ...}`) returned `code: 0`, `data.status: "FAILED"`, `data.failReason: "execution reverted: BEP20: transfer amount exceeds allowance"` whenever the wallet has `0` USDT allowance for `0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`.
     - **How I fixed it**: When `/simulate` reverts with `"allowance"`, `run_transaction_dry_run()` automatically calls `GET /api/v1/dex/aggregator/approve-transaction` (`binanceChainId=56`, `tokenContractAddress=0x55d398326f99059fF775485246999027B3197955`, `approveAmount=2000000000000000000`) and simulates that ERC-20 `approve()` calldata via `POST /api/v1/dex/pre-transaction/simulate`. That second simulation returns `data.status: "SUCCESS"` with `allowanceChanges: [{"tokenAddress": "0x55d3...", "spender": "0xb444...", "preAmount": "0", "postAmount": "2000000000000000000"}]`. We report `simulation.status = "REQUIRES_APPROVAL"` and `simulation.passed = True`, giving the user both the exact router calldata verification and proof that the ERC-20 approval succeeds.
  3. **Binance Agentic Wallet CLI (`baw`) integration**:
     - The official `@binance/agentic-wallet` skill executes swaps via `baw market-order swap --fromTokenQty <qty> --fromToken 0x55d398326f99059fF775485246999027B3197955 --toToken <addr> --binanceChainId 56 --slippage 0.5 --mev true --gasLevel MEDIUM --json`.
     - `run_agentic_wallet_swap()` in `bine/execution.py` generates this exact command, checks all 5 safety gates (`verdict != REFUSE` → `simulation.passed` → `execute_live=True` → `amount_usd <= $3.00` & `daily_spend <= $10.00` → `BINE_LIVE_MODE=true`), and logs every decision, refusal, dry-run simulation, and `tx_hash` (`https://bsctrace.com/tx/...`) in the `decision_log` SQLite/Postgres table.

## 2026-10-02T00:18Z — Phase 0 Truth Pass & 5-Run `SPYon` Spread Verification

- **a) Reconciling earlier summary contradictions**:
  1. **Simulation endpoint & router**: Checked `backend/bine/execution.py` (lines 162, 238) and `frontend/src/pages/Home.tsx` (lines 931, 1003) and ran `grep -rn "onchain-gateway\|OKX" .`. Zero occurrences in the codebase. The code exclusively calls `POST /api/v1/dex/pre-transaction/simulate` against the `LiquidMesh` router (`0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`).
  2. **Quarantined token count (`10` vs `8`)**: Both numbers came from real snapshots at different times because `assess_token_quality()` filters on rolling `volume24H < $1,000,000`:
     - Static `2026-10-01T00:48Z` fixture (`tests/fixtures/rwa_tokens_ondo_bsc.json`): **10** Ondo tokens failed (`SOXSon`, `ENLVon`, `BRHYon`, `EXODon`, `HYGWon`, `BRLNon`, `ORBXon`, `INCEon`, `FGDLon`, `VFSon`).
     - Live `bine.db` at `2026-10-02T00:13Z`: **8** Ondo tokens failed (`ORBXon`, `SOXSon`, `ENLVon`, `BRHYon`, `HYGWon`, `EXODon`, `BRLNon`, `NIKLon`) after `INCEon`, `FGDLon`, and `VFSon` crossed `$1.0M` 24h volume during Thursday's US market session and `NIKLon` dipped to `$339,716`.
  3. **`AAPL` quick-button behavior**: `AAPL` is listed on BSC only by Ondo (`AAPLon`, `0x390a684ef9cade28a7ad0dfa61ab1eb3842618c4`) and is not in the 40 `DUAL_ISSUER_TICKERS` (not listed by `bStocks` on BSC). Clicking the `AAPL` quick-button in `Home.tsx` queried `GET /api/quote?ticker=AAPL&amount_usd=25` (returning a single-issuer `BUY_ONDO` response for `AAPLon` at `$331.04/share`), while the `<select>` dropdown (populated only with the 40 dual-issuer tickers + `ENLV`) fell back to `value=""`.
- **b) Binance Agentic Wallet CLI (`baw`) check**:
  - `which baw` returned `baw not found` (exit code 1) and `baw --help` returned `zsh:1: command not found: baw`.
  - Ran `npx --yes @binance/agentic-wallet@1.10.0 --help` and `npx --yes @binance/agentic-wallet@1.10.0 market-order swap --help`. Confirmed `@binance/agentic-wallet` v1.10.0 accepts:
    `--fromTokenQty <fromTokenQty>`, `--fromToken <fromToken>`, `--toToken <toToken>`, `--slippage <slippage>` (default `"auto"`), `--mev <mev>` (default `"true"`), `--gasLevel <gasLevel>` (default `"MEDIUM"`), `--binanceChainId <binanceChainId>`, `--json`.
  - Inspected `@binance/agentic-wallet/dist/index.js` and `references/market-order.md`: `baw market-order swap` submits to `/bapi/defi/v1/public/wallet-direct/web-dex/agent/place-order` (or `/ondo/place-order` for Ondo RWA tokens) and returns `{ "success": true, "data": { "orderId": "..." } }`. It must then be polled via `baw market-order list --orderId <orderId> --json` until `status` reaches `FINISHED` (which populates `txHash`) or `FAILED`.
- **c) 5-Run `SPYon` (`Ondo`, `0x6a708ead771238919d85930b5a0f10454e1c331a`) Spread Verification (`$25`, `$100`, `$250`, 30 seconds apart)**:
  - **Plain conclusion**: **The ~41% execution spread on `SPYon` at `$250` is 100% reproducible (`5/5` runs returned `+40.73%` to `+40.76%` execution spread above reference).** At `$25` and `$100`, `SPYon` executes slightly below reference (`-0.69%` and `-0.15%`), but between `$100` and `$250` the `Pancakeswap V3` pool routed by `LiquidMesh` runs out of liquidity, causing `toTokenAmount` to collapse to `0.22774238` tokens (`$1,087.43/share` vs `$772.62/share` reference).
  - **Raw results across all 5 runs (`tokenToShareRatio = 1.00947307`, `marketStatus = "overnight"`, `vendorName = "LiquidMesh"`, `dexName = "Pancakeswap V3"`)**:

| Run | UTC Timestamp | Ref Price | `$25` Exec / Share (Spread) | `$100` Exec / Share (Spread) | `$250` Exec / Share (Spread) | `$250` `toTokenAmount` (wei) | `$250` `priceImpactPercent` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `2026-10-02T00:16:52Z` | `$772.52` | `$767.30` (`-0.6759%`) | `$771.46` (`-0.1371%`) | `$1,087.43` (**`+40.7639%`**) | `227742382361888825` | `"0.2974289557"` |
| 2 | `2026-10-02T00:17:23Z` | `$772.61` | `$767.30` (`-0.6878%`) | `$771.46` (`-0.1490%`) | `$1,087.43` (**`+40.7470%`**) | `227742382361888825` | `"0.2974289557"` |
| 3 | `2026-10-02T00:17:53Z` | `$772.65` | `$767.30` (`-0.6922%`) | `$771.46` (`-0.1535%`) | `$1,087.43` (**`+40.7407%`**) | `227742382361888825` | `"0.2974289557"` |
| 4 | `2026-10-02T00:18:23Z` | `$772.59` | `$767.30` (`-0.6847%`) | `$771.46` (`-0.1459%`) | `$1,087.43` (**`+40.7515%`**) | `227742382361888825` | `"0.2974289557"` |
| 5 | `2026-10-02T00:18:53Z` | `$772.71` | `$767.30` (`-0.7003%`) | `$771.46` (`-0.1616%`) | `$1,087.43` (**`+40.7293%`**) | `227742382361888825` | `"0.2974289557"` |

- **d) Misclassification of `[40375] Minimum order amount is 5 USD`**:
  - Previously, when `/api/v1/dex/aggregator/quote` returned business error `[40375] Minimum order amount is 5 USD.`, `evaluate_issuer_quote()` classified it as `depth_thin` (`No executable DEX route: [40375] Minimum order amount is 5 USD.`). Separated into its own refusal code `below_issuer_minimum` in Phase 1.

## 2026-10-02T14:35Z — Phases 1–8 Verification: Stateless 60s Catalog, CLI/MCP/Skill Surfaces, and One-Screen Light/Dark UI

- **Frozen Contract (`schema_version: "1"`) & 5 bps Tie Band**:
  - Verified live on `GET /api/quote?ticker=NVDA&amount_usd=25`: `NVDAB` (`$237.38/share`) and `NVDAon` (`$237.33/share`) were `2.1 bps` apart (`<= 5.0 bps` tie band), triggering `"Either works (within 5 bps). Also checked NVDAon on Ondo: $0.05 per share less."` and deterministically selecting `NVDAB` on deeper AMM pool liquidity (`$6.06M` vs `$0` AMM TVL).
- **Stateless Request Path**:
  - Removed the background APScheduler worker from the web request path (`fetch_live_rwa_catalog()` caches `/api/v1/dex/market/rwa/tokens` in memory for 60s and checks `reference_stale` against `MAX_SAMPLE_AGE_SECONDS = 120s`). Moved the standalone research sampler to `tools/collect_evidence.py`.
- **Plug-in Surfaces (`bine` CLI, MCP Server, `SKILL.md`)**:
  - Verified `bine check NVDA 25`, `bine check NVDA 25 --json`, and stdio JSON-RPC `2.0` calls (`tools/list`, `tools/call` for `bine_check` and `bine_buy`) against the frozen `schema_version: "1"` contract (`48/48` pytest tests passing).

## 2026-10-03T21:18Z — Live `$2.00` `NVDAB` Swap Verification (`0x00c0fabd...e506`)

- **1. Dynamic `--toToken` Generator from Quote Response (`build_baw_swap_command_from_quote`)**:
  - Replaced hardcoded CLI command strings with `build_baw_swap_command_from_quote(quote, expected_address=...)` in `backend/bine/execution.py` and `backend/bine/cli.py`.
  - Verified character-by-character that `quote["token"]["address"]` for `NVDAB` is `0x02fca66c1d1afb4e2a7884261eb00f63598a7436`.
- **2. Pre-Swap Wallet Balance & Transaction API Dry-Run (`docs/dry_run_nvda_2usd.json`)**:
  - `baw wallet balance --binanceChainId 56 --json` on wallet `0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730` returned `5.00 USDT` (`$4.9996`) and `0.00025936 BNB` (`$0.2041`).
  - In `docs/dry_run_nvda_2usd.json`, `"passed": true` with `"fail_reason": "execution reverted: BEP20: transfer amount exceeds allowance"` is the expected pre-approval state when simulating raw `/api/v1/dex/aggregator/swap` calldata before USDT has been approved to the router (`0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`), and the `/api/v1/dex/aggregator/approve-transaction` simulation (`"approval_simulation_status": "SUCCESS"`) returned `SUCCESS` for `2000000000000000000` wei on `0x55d398326f99059fF775485246999027B3197955`.
- **3. Approve + Swap Parent/Child `orderId` Finding**:
  - First-time swaps run an `approve` transaction (`0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64`) before the `swap` transaction (`0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506`, BSC Block `125555002`).
  - `baw market-order swap` returns the parent `orderId` (`26100300001937918699`), `baw market-order list --orderId 26100300001937918699 --json` on that parent ID returns an empty list (`"list": []`), and only `baw market-order list --json` (without `--orderId`) shows the settled child order (`orderId` `26100300001937918737`, `"status": "FINISHED"`, `"txHash": "0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506"`).
  - Updated `run_agentic_wallet_swap()` in `backend/bine/execution.py` to fall back to `baw market-order list --json` when `--orderId` returns an empty list.
- **4. Reconciliation Note (`docs/live_swap_nvda_2usd.json` & `DecisionLog #16`)**:
  - The first live `$2` `NVDAB` swap run recorded the parent `orderId` (`26100300001937918699`) and no `txHash` (`status: "LIVE_TIMEOUT"`). `docs/live_swap_nvda_2usd.json` and `DecisionLog #16` were reconciled afterwards from `baw market-order list --json` (child `orderId` `26100300001937918737`) and the BSC receipt for `0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506`.
  - Untouched copies of all `baw` outputs and the exact commands that produced them are stored in `docs/raw/`.
- **5. Share-Ratio Balance Finding (`baw wallet balance` vs. On-Chain `balanceOf`)**:
  - After the swap, `baw wallet balance --binanceChainId 56 --json` (and `toTokenActualQty` in `baw market-order list --json`) shows `0.00851201289192116` `NVDAB`, while on-chain `eth_call` `balanceOf(0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730)` on `0x02fca66c1d1afb4e2a7884261eb00f63598a7436` returns `8505393792444895` wei (`0.008505393792444894` raw tokens, or `0.0085053938` rounded to 10 decimal places).
  - The gap between the two numbers equals `tokenToShareRatio` `1.0007782237528078`:
    `0.008505393792444894 * 1.0007782237528078 = 0.00851201289192116`.
  - `baw` displays and reports the share-adjusted balance (`raw_tokens * tokenToShareRatio`), whereas the ERC-20 contract stores raw token units.
- **6. Quoted vs. Filled Shares & Gas Cost**:
  - Immediate pre-swap quote (`2026-10-03T21:18:06Z`, `offhours`): `0.008512` shares (`0.00851212` unrounded; `0.00850550` raw `NVDAB` tokens * `1.0007782237528078` `tokenToShareRatio`), all-in `$237.06/share` vs `$235.07` reference (`+0.85%` off-hours spread; earlier off-hours sample was `0.008516` shares at `+0.99%`).
  - Filled on-chain at `0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730`: `0.008505393792444894` raw `NVDAB` tokens (`-0.12 bps` vs quoted `0.00850550` tokens) and `0.00851201289192116` shares (`-0.13 bps` vs immediate quote `0.00851212`, `-4.7 bps` vs earlier `0.008516` quote).
  - Total BNB gas spent: `0.000002932518144096 BNB` (`approve`) + `0.000047976548789549 BNB` (`swap`) = `0.000050909066933645 BNB` (`$0.040`).

## 2026-10-05T15:04Z — US Regular-Hours (`marketStatus = "regular"`, 94 Minutes After Open / 11:04 New York) Quotes & Second `$2.00` `NVDAB` Swap (`0xa3693383...3e75`)

- **1. Regular-Hours Quote Matrix (`docs/raw/regular_hours_quotes_2026-10-05.jsonl`, `2026-10-05T15:04:08Z–15:04:25Z`, 94 minutes after the 09:30 New York open)**:
  - During US regular trading hours (`marketStatus = "regular"`, `11:04` New York):
    - `NVDAon` (`Ondo`) quoted via `Ondo RWA` (`SWAP`) at `$237.3188/share` (`+0.0037%` / `+0.37 bps` vs `$237.31` reference) at both `$5.50` and `$25.00`, while `NVDAB` (`bStocks`) quoted via `LiquidMesh` (`PancakeSwap V3`) at `$237.5515/share` (`+0.1059%` at `$5.50`) and `$237.5608/share` (`+0.1099%` at `$25.00`).
    - `SPYon` (`Ondo`) switched from off-hours `PancakeSwap V3` AMM routing (`+81.88%` at `$250`, `-1.19%` at `$25`) to `Ondo RWA` RFQ/mint routing during regular hours (`$777.0888/share` vs `$777.06` reference, **`+0.0037%` / `+0.37 bps`** at `$5.50` and `$25.00`).
    - `NFLXon` (`10.0000x` ratio), `CVNAon` (`4.9970x` ratio), and `NOWon` (`4.9964x` ratio) all executed via `Ondo RWA` during regular hours at **`+0.0036%` to `+0.0038%`** (`~0.37 bps`) vs reference, whereas `KLACon` (`10.0680x` ratio) and `PPLTon` (`10.0000x` ratio) continued to fail `/api/v1/dex/aggregator/quote` with `[40374] Insufficient liquidity for a quote. Please decrease the transaction amount or try again later.`
- **2. Second Live `$2.00` `NVDAB` Swap (`0xa3693383a9493600df08ae10a6a64faa6a7543e3bde9f6bbca3fd7acfc2a3e75`, Zero Hand Edits)**:
  - Executed `BINE_LIVE_MODE=true BINE_DIRECT_MODE=true backend/.venv/bin/bine buy NVDA 2 --yes` at `2026-10-05T15:05Z` (94 minutes after open, 11:04 New York).
  - `DecisionLog #17` recorded the pre-trade dry-run (`action="dry_run"`, `execution_status="DRY_RUN_OK"`, `order_id=null`) and `DecisionLog #18` recorded the live swap (`action="execute"`, `execution_status="LIVE_SUBMITTED"`, `order_id="26100500001942767719"`, `tx_hash="0xa3693383a9493600df08ae10a6a64faa6a7543e3bde9f6bbca3fd7acfc2a3e75"`).
  - Why `#17` and `#18` still showed `simulation_status = "REQUIRES_APPROVAL"` on `0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5` while the live swap needed no second `approve` tx:
    - On-chain `eth_call` `allowance(0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730, 0xb300000b72DEAEb607a12d5f54773D1C19c7028d)` on USDT returns `0xffffffffffffffffffffffffffffffffffffffffffffffffc87d2531626fffff` (`115792089237316195423570985008687907853269984665640564039453584007913129639935` wei = `uint256.max - 4e18` after two `$2` swaps) because the Oct 3 `approve` tx (`0x803cda03...eeb64`) approved `uint256.max` to `baw`'s router (`0xb300000b...028d`).
    - By contrast, `allowance(0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730, 0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5)` on the Open API `LiquidMesh` router is `0`, so `/api/v1/dex/pre-transaction/simulate` continues to report `REQUIRES_APPROVAL` on `0xB44446b0...`.
    - Because `0xb300000b...028d` already had `uint256.max` allowance, `baw market-order swap` submitted a single swap order (`26100500001942767719`) with no parent/child split, and `--orderId 26100500001942767719` returned `"status": "FINISHED"` with `txHash` on the first poll.

## 2026-10-05T21:25Z — Developer-Experience Finding: Open API Simulation Spender (`0xB44446b0...`) vs. `baw` Execution Router (`0xb300000b...`) and `tx-history` Approve Amount

- **Endpoints & Doc Pages**:
  - `GET /build/api/v1/dex/aggregator/quote` (`data[].approveTarget`)
  - `GET /build/api/v1/dex/aggregator/swap` (`data.tx.to`)
  - `GET /build/api/v1/dex/aggregator/approve-transaction` (`data[].dexContractAddress`, documented at `https://web3.binance.com/en/dev-docs/llms-full.txt` under Trading API / Get Approve Transaction)
  - `POST /build/api/v1/dex/pre-transaction/simulate` (`data.status`, `data.failReason`, `data.allowanceChanges[].spender`, documented at `https://web3.binance.com/en/dev-docs/llms-full.txt` under Transaction API / Simulate Transaction)
  - `@binance/agentic-wallet@1.10.0` (`baw market-order swap` and `baw wallet tx-history --binanceChainId 56 --json`)
- **What `POST /api/v1/dex/pre-transaction/simulate` reported & which spender it used**:
  - Simulating the calldata from `GET /api/v1/dex/aggregator/swap` (`data.tx.to = "0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5"`) returned `status: "FAILED"`, `failReason: "execution reverted: BEP20: transfer amount exceeds allowance"`.
  - `GET /api/v1/dex/aggregator/approve-transaction` returned `dexContractAddress: "0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5"`, and simulating that approval calldata returned `status: "SUCCESS"` with `allowanceChanges[0].spender = "0xb44446b0c8e56988c34f7ff73ae904982b5fdda5"`.
- **What `baw` actually used**:
  - Live execution via `baw market-order swap` executed on-chain against spender/router `0xb300000b72DEAEb607a12d5f54773D1C19c7028d` (`txHash: 0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506` on `2026-10-03T21:18:17Z` and `txHash: 0xa3693383a9493600df08ae10a6a64faa6a7543e3bde9f6bbca3fd7acfc2a3e75` on `2026-10-05T15:05:34Z`).
  - The first swap's `approve` transaction (`0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64`) granted `uint256.max` (`0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff`) USDT allowance on-chain to `0xb300000b72DEAEb607a12d5f54773D1C19c7028d`, leaving `115792089237316195423570985008687907853269984665640564039453584007913129639935` wei (`uint256.max - 4 * 10^18`) after the two `$2` swaps, while `allowance(0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730, 0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5)` remained `0` (`docs/raw/usdt_allowance_2026-10-05.txt`).
  - Meanwhile, `baw wallet tx-history --binanceChainId 56 --json` reported `instructions.approve.amount = "2000000000000000000"` (`2 USDT`) for `0x803cda03...eeb64` instead of the on-chain `uint256.max` approval value.
- **What I expected**:
  - Expected `GET /api/v1/dex/aggregator/swap` + `POST /api/v1/dex/pre-transaction/simulate` and `baw market-order swap` to use the same router/spender address (or for `/aggregator/swap` and `/aggregator/approve-transaction` to return `0xb300000b72DEAEb607a12d5f54773D1C19c7028d`), so that after the first swap's approval, subsequent dry-runs would return `status: "SUCCESS"` rather than `BEP20: transfer amount exceeds allowance`. Also expected `baw wallet tx-history` `instructions.approve.amount` to report the actual on-chain `Approval` log value (`uint256.max`).
- **How long it took to understand (from log timestamps)**:
  - First live swap and dry-run logged at `2026-10-03T21:18:06Z–21:18:17Z`; second live swap (`DecisionLog #17` and `#18`) logged at `2026-10-05T15:05:27Z–15:05:40Z` (41 hours 47 minutes after the first swap); on-chain `eth_call` `allowance(owner, spender)` comparison across both spenders completed at `2026-10-05T21:25:35Z` (`6 hours 20 minutes` after `DecisionLog #17` at `15:05:27Z`, and `48 hours 07 minutes` elapsed since the first swap at `2026-10-03T21:18:17Z`).
- **What I would change in the API**:
  1. Align the router/spender returned by `GET /api/v1/dex/aggregator/quote` (`data[].approveTarget`), `GET /api/v1/dex/aggregator/swap` (`data.tx.to`), and `GET /api/v1/dex/aggregator/approve-transaction` (`data[].dexContractAddress`) with the router used by `baw market-order swap` (`0xb300000b72DEAEb607a12d5f54773D1C19c7028d`), or accept a router/channel parameter so `POST /api/v1/dex/pre-transaction/simulate` tests the exact router `baw` executes against.
  2. Expose a `baw market-order swap --dry-run` flag in `@binance/agentic-wallet` that simulates the exact `place-order` transaction against `0xb300000b72DEAEb607a12d5f54773D1C19c7028d`.
  3. Fix `baw wallet tx-history` so `instructions.approve.amount` reflects the actual on-chain ERC-20 `Approval` event amount (`uint256.max`) rather than the swap's `fromTokenQty` (`2000000000000000000`).

