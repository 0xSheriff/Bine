# Developer Experience Findings (Binance Web3 Open API & Agentic Wallet)

This page summarizes only the **`VERIFIED`** findings from the full evidence ledger in [`docs/devex-evidence.md`](https://github.com/kyrian-dev/Bine/blob/master/docs/devex-evidence.md) (106 verified entries backed by raw captures in `docs/raw/*`, SQLite rows in `bine.db` / `backend/bine.db`, and rendered DOM snapshots from `https://web3.binance.com/en/dev-docs/`).

*(Note: Two earlier observations from development notes that lacked standalone raw capture files are explicitly separated as `AGENT-REPORTED` in Section 8 of `docs/devex-evidence.md` and are omitted from the verified claims below.)*

---

## 1. Documentation & `llms-full.txt` Gaps (`VERIFIED`)

1. **`llms.txt` and `llms-full.txt` are blocked by AWS WAF (`HTTP 202 Challenge`) for standard HTTP clients**:
   - `curl -sI https://web3.binance.com/en/dev-docs/llms.txt` and `llms-full.txt` return `HTTP/2 202` with `x-amzn-waf-action: challenge` and `content-length: 0` (`docs/devex-evidence.md:27-28`). A real browser (or headless Chromium executing the WAF challenge script) is required to read them.
2. **Entire RWA Data API (`GET /api/v1/dex/market/rwa/platforms` and `GET /api/v1/dex/market/rwa/tokens`) is absent from `llms-full.txt`**:
   - Neither endpoint path nor any of the RWA catalog fields (`tokenToShareRatio`, `referencePrice`, `marketStatus`, `openState`, `underlyingTicker`, `reasonCode`, `sharesMultiplier`) appear in `llms-full.txt` (`3,735` lines). They exist only on the rendered SPA page `https://web3.binance.com/en/dev-docs/products/rwa-data/api-reference` (`docs/devex-evidence.md:45-61`).
3. **Undocumented business error codes (`40367`, `40369`, `40374`, `40375`)**:
   - None of the four RWA/Trading business error codes returned in production (`40367` non-trading session / phase shift, `40369` market closed, `40374` insufficient liquidity, `40375` minimum order amount is 5 USD) appear in `llms.txt`, `llms-full.txt`, or the rendered `rwa-data` / `trading-api` pages (`docs/devex-evidence.md:29-35`).
4. **Ondo `type=1` routing & `executionMode=RFQ` in Trading API Introduction**:
   - Under `https://web3.binance.com/en/dev-docs/products/trading-api/introduction#tokenized-stocks-ondo`, the docs state: *"Any quote whose route list contains a protocol with `type=1` must be executed through the Ondo Place Order endpoint (`/api/v1/dex/aggregator/ondo/place-order`), not the standard `/swap` endpoint. The Quote API automatically sets `executionMode=RFQ` when an Ondo route is selected."* (`docs/devex-evidence.md:49`).

---

## 2. API Payload & Schema Findings (`VERIFIED`)

1. **Catalog Key Names (`rwa_tokens_ondo.json` / `/api/v1/dex/market/rwa/tokens`)**:
   - Each item in `data[]` uses flat camelCase keys (`tokenSymbol`, `underlyingTicker`, `tokenContractAddress`, `tokenPrice`, `referencePrice`, `tokenToShareRatio`, `openState`, `marketStatus`, `reasonCode`, `volume24h`, `marketCap`). The string `sharesMultiplier` does not exist in the API response or on the rendered doc pages (`docs/devex-evidence.md:47-55`).
2. **Missing `X-OC-APIKEY` Behavior (`40101` vs `302`)**:
   - Calling `GET https://web3.binance.com/build/api/v1/dex/market/rwa/tokens` without `X-OC-APIKEY` returns `HTTP 401` with `{"code": 40101, "msg": "API Key is required"}` (`docs/raw/rwa_tokens_no_key_2026-10-05.txt:1-19`), whereas calling the non-`/build/api` web path redirects with `HTTP 302` (`docs/devex-evidence.md:63`).
3. **`POST` vs `GET` on `/api/v1/dex/market/token/basic-info`**:
   - Calling `/build/api/v1/dex/market/token/basic-info` with `GET` returns `HTTP 401` (`40101` without key) or fails, while `POST` with a JSON body `{"binanceChainId": "56", "contractAddresses": [...]}` is the required method (`docs/devex-evidence.md:18`).
4. **`priceImpactPercent` is a `0..1` fraction, not a `0..100` percentage**:
   - On `SPYon` at `$250` off-hours, where output drops by ~29.7% (`+40.76%` execution spread above reference), `/aggregator/quote` returns `"priceImpactPercent": "0.2974289557"` (`docs/devex-facts.md:58`). BINE multiplies `priceImpactPercent` by `100.0` so `0.2974` is evaluated as `29.74%`.

---

## 3. Agentic Wallet (`baw`) & On-Chain Execution Findings (`VERIFIED`)

1. **Separate Router Contracts (`0xB444...` vs `0xb300...`)**:
   - `/api/v1/dex/aggregator/swap` builds calldata for router `0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`, whereas `baw market-order swap` executes on-chain through `0xb300000b72DEAEb607a12d5f54773D1C19c7028d` (`docs/raw/tx_history_2026-10-05.json`, `docs/raw/usdt_allowance_2026-10-05.txt`).
2. **Parent vs. Child `orderId` when Approval Runs First**:
   - When `baw market-order swap` submits a one-time `approve` transaction first (`Decision #16`), `baw` returns a parent `orderId` (`26100300001937918699`) that returns `{"list": []}` when queried with `--orderId`. Polling `baw market-order list --json` without `--orderId` is required to read the child swap order (`26100300001937918737`, `status: "FINISHED"`, `txHash: "0x00c0fabd...c228e506"`).
3. **`baw wallet balance` Reports Share-Adjusted Units, Not Raw ERC-20 `balanceOf`**:
   - After Swap #1, on-chain `eth_call` `balanceOf` returned `8505393792444895` wei (`0.0085053938` raw `NVDAB` tokens), while `baw wallet balance --binanceChainId 56 --json` reported `0.00851201289192116` (`= raw_tokens * tokenToShareRatio` `1.0007782237528078`). After Swap #2, `balanceOf` returned `16926469875736378` wei (`0.01692647` raw tokens) and `baw wallet balance` reported `0.016939642456644862` (`docs/raw/wallet_balance_post_swap.json`, `docs/raw/wallet_balance_second_swap_2026-10-05.json`).

---

## 4. Measured Endpoint Latency & Rate-Limit Behavior (`VERIFIED`)

Across `75` sequential live calls (`15` runs per endpoint, `3` seconds apart, `docs/raw/endpoint_latency_15_runs_2026-10-07.jsonl`) and `53,643` historical `token_sample` rows (`docs/devex-evidence.md:77-101`):

| Endpoint | Calls (`n`) | Min (`ms`) | Median (`ms`) | Max (`ms`) | HTTP `429`s |
| --- | --- | --- | --- | --- | --- |
| `GET /rwa/tokens?binanceChainId=56&platformId=ondo` | `15` | `506.19` | `871.57` | `1813.84` | `0` |
| `GET /rwa/tokens?binanceChainId=56&platformId=bstock` | `15` | `456.43` | `495.56` | `833.97` | `0` |
| `GET /token/top-liquidity` (`NVDAon`) | `15` | `449.70` | `552.78` | `3030.38` | `0` |
| `GET /aggregator/quote` (`NVDAon` `$2.00` -> `40375`) | `15` | `439.89` | `464.41` | `2028.72` | `0` |
| `GET /aggregator/quote` (`NVDAon` `$5.50` -> `code: 0`) | `15` | `659.05` | `901.61` | `3196.65` | `0` |
