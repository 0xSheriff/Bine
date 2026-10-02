# Binance Web3 Open API & Agentic Wallet — Verified DevEx Facts

Raw chronological list of verified technical observations, endpoints, timestamps, and exact response payloads recorded while building and testing Bine on BNB Smart Chain (`binanceChainId="56"`).

---

1. **Signing Prehash Path Prefix (`/build`)**
   - **Doc Page**: `docs/Open-API-Authentication.md` (`skills/binance-web3/signing/SKILL.md`)
   - **UTC Timestamp**: `2026-09-30T17:10:00Z`
   - **Observation**: Although the base URL is `https://web3.binance.com/build`, the HMAC-SHA256 prehash string `timestamp + METHOD + path + query + body` requires `path` to begin with `/build/api/v1/...`. Signing with `/api/v1/...` returns HTTP `401` / `{"code": 40102, "msg": "Invalid signature"}`.

2. **Per-Retry Timestamp Re-Signing (`[40103] Timestamp outside recv_window`)**
   - **Endpoint**: `GET /build/api/v1/dex/market/rwa/tokens`
   - **UTC Timestamp**: `2026-10-01T14:50:36.762084309Z`
   - **Observation**: When a first HTTP attempt experiences a `15002 ms` `ConnectTimeout` and the client retries with exponential backoff, reusing the original `X-MBX-TIMESTAMP` and `X-MBX-SIGNATURE` headers causes the retry to fail with `TimestampError: [40103] Timestamp outside recv_window. serverTime=2026-10-01T14:50:36.762084309Z`. `BinanceClient._request()` must regenerate `X-MBX-TIMESTAMP` and `X-MBX-SIGNATURE` inside the retry loop on every attempt.

3. **`GET /build/api/v1/dex/market/rwa/platforms` Platform Catalog**
   - **Endpoint**: `GET /build/api/v1/dex/market/rwa/platforms`
   - **UTC Timestamp**: `2026-10-01T00:48:34Z`
   - **Observation**: Returns `{"code": "000000", "data": [{"platformId": "ondo", "platformName": "Ondo Global Markets", "chains": [{"binanceChainId": "56", "chainName": "BSC"}, {"binanceChainId": "1", "chainName": "ETH"}, {"binanceChainId": "CT_501", "chainName": "SOL"}]}, {"platformId": "bstock", "platformName": "bStocks", "chains": [{"binanceChainId": "56", "chainName": "BSC"}]}]}`. No `xstock` or `xStocks` platform exists in the API response.

4. **`GET /build/api/v1/dex/market/rwa/tokens` Schema & Nullability Differences (`ondo` vs `bstock`)**
   - **Endpoint**: `GET /build/api/v1/dex/market/rwa/tokens?binanceChainId=56&platformId=ondo|bstock`
   - **UTC Timestamp**: `2026-10-01T00:48:35Z`
   - **Observation**:
     - `ondo` returns `202` tokens on `binanceChainId="56"` (`442` rows across all chains in raw response) with populated `marketCap`, `statusInfo.marketStatus` (`"regular"`, `"postmarket"`, `"overnight"`, `"paused"`, `"closed"`), and `statusInfo.nextOpenTime`.
     - `bstock` returns `46` tokens on `binanceChainId="56"`, all with `marketCap: null`, `statusInfo.marketStatus: null`, and `statusInfo.nextOpenTime: null`.
     - Overlap on BSC (`binanceChainId="56"`): `40` underlying equity/ETF tickers are listed by both `ondo` and `bstock`; `448` unique tickers are listed across either issuer (`AAPL` is listed only on `ondo` as `AAPLon`, `0x390a684ef9cade28a7ad0dfa61ab1eb3842618c4`).

5. **Outlier & Reverse-Split Token (`ENLVon`) in `/rwa/tokens`**
   - **Endpoint**: `GET /build/api/v1/dex/market/rwa/tokens?binanceChainId=56&platformId=ondo`
   - **UTC Timestamp**: `2026-10-01T00:48:35Z`
   - **Observation**: `ENLVon` (`0x66bf7df72d3fa2e2b54fdba6df0ab0a2f4d97b93`) returned `tokenPrice="1.0725036841628343"`, `referencePrice="16.05"`, `tokenToShareRatio="0.06666667"`, `volume24H="0"`. Because `1 ENLVon = 1/15 ENLV share` after a 1-for-15 reverse split (`$1.0725 * 15 = $16.0875/share`), naive `(tokenPrice - referencePrice) / referencePrice` computation yields `-93.32%`. Share-adjusted cost per share is mandatory: `execution_price_per_share = amount_usd / (tokens_received * tokenToShareRatio)`.

6. **Ondo Session Boundary Pause (`statusInfo.marketStatus="paused"`)**
   - **Endpoint**: `GET /build/api/v1/dex/market/rwa/tokens?binanceChainId=56&platformId=ondo`
   - **UTC Timestamp**: `2026-09-30T20:02:51Z` (4:02 PM ET, 2 minutes after US regular session close)
   - **Observation**: All `ondo` tokens returned `statusInfo: {"openState": false, "marketStatus": "paused", "reasonCode": "MARKET_PAUSED", "reasonMsg": "", "nextOpenTime": 1790884980000}` for the 3-minute transition window (`20:00–20:03 UTC`) before switching to `"postmarket"` with `openState: true` at `20:03:00 UTC`.

7. **Ondo `$5.00` Minimum Order Business Error (`[40375]`)**
   - **Endpoint**: `GET /build/api/v1/dex/aggregator/quote?binanceChainId=56&fromTokenAddress=0x55d398326f99059ff775485246999027b3197955&toTokenAddress=0xa9998e732f483032e3d9702f25e2102c92f907a7&amount=2000000000000000000`
   - **UTC Timestamp**: `2026-10-01T15:30:12Z`
   - **Observation**: Requesting a `$2.00` quote (`amount=2000000000000000000`) on any Ondo token (`NVDAon`, `AAPLon`, `SPYon`) returns HTTP `200` with JSON body `{"code": 40375, "msg": "Minimum order amount is 5 USD."}`. Dinari `bstock` tokens (`NVDAB`, `SPYB`, `TSLAB`) accept `$2.00` orders without a `$5.00` floor.

8. **`GET /build/api/v1/dex/market/token/top-liquidity` Null `liquidityUsd` on Ondo PMM Pools**
   - **Endpoint**: `GET /build/api/v1/dex/market/token/top-liquidity?binanceChainId=56&tokenContractAddress=0xa9998e732f483032e3d9702f25e2102c92f907a7`
   - **UTC Timestamp**: `2026-10-01T15:28:44Z`
   - **Observation**: For `NVDAon`, `/top-liquidity` returns 3 pools (`Bebop`, `PancakeSwap V3`, `Uniswap V3`) where the primary `Bebop` RFQ/PMM pool has `liquidityUsd: null` and the two AMM pools have `"0"` or negligible TVL. For `NVDAB` (`0x02fca66c1d1afb4e2a7884261eb00f63598a7436`), `/top-liquidity` returns 3 AMM pools with `total_pool_liquidity_usd = $6,064,347.90` (led by `PancakeSwap V3` at `$4,917,885.60`).

9. **Reproducible `+40.7%` Execution Spread on `SPYon` at `$250` (`priceImpactPercent` Fractional Scale)**
   - **Endpoint**: `GET /build/api/v1/dex/aggregator/quote?binanceChainId=56&fromTokenAddress=0x55d398326f99059ff775485246999027b3197955&toTokenAddress=0x6a708ead771238919d85930b5a0f10454e1c331a&amount=250000000000000000000`
   - **UTC Timestamp**: `2026-10-02T00:16:52Z` through `2026-10-02T00:18:53Z` (5 consecutive runs, 30 seconds apart)
   - **Observation**:
     - At `$25` (`amount=25e18`) and `$100` (`amount=100e18`), `SPYon` (`referencePrice = $772.52–$772.71`, `tokenToShareRatio = 1.00947307`) routes through `LiquidMesh` at `$767.30/share` (`-0.69%`) and `$771.46/share` (`-0.15%`).
     - At `$250` (`amount=250e18`), in `5/5` runs, `SPYon` falls back to a thin `Pancakeswap V3` pool (`vendorName="LiquidMesh"`, `dexName="Pancakeswap V3"`, `tradeFee="0.625"`), returning `toTokenAmount="227742382361888825"` (`0.227742 SPYon = 0.229899 SPY shares`), which is ~29.1% fewer shares than the `$100` rate and an execution price of **`$1,087.43/share` (`+40.73%` to `+40.76%` above `$772.52` reference)**.
     - In the same `$250` responses, `priceImpactPercent` is `"0.2974289557"`. The field is a `0–1` fraction (`29.74%` output reduction, matching the `29.1%` share drop vs the `$100` rate where `1 / (1 - 0.2974) - 1 = +42.3%` cost increase) mislabeled as `Percent` in the key name — it does **not** understate once multiplied by `100.0` (`_parse_price_impact_pct()` in `bine/quote_engine.py`).

10. **Transaction API `/pre-transaction/simulate` Zero-Allowance Behavior**
    - **Endpoints**:
      - `GET /build/api/v1/dex/aggregator/swap`
      - `GET /build/api/v1/dex/aggregator/approve-transaction`
      - `POST /build/api/v1/dex/pre-transaction/simulate`
    - **UTC Timestamp**: `2026-10-01T16:12:08Z`
    - **Observation**: Simulating the raw swap calldata from `/api/v1/dex/aggregator/swap` (`to="0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5"`, `LiquidMesh` router) for a wallet that has not yet approved USDT returns `{"status": "FAILED", "failReason": "BEP20: transfer amount exceeds allowance"}`. Fetching `/api/v1/dex/aggregator/approve-transaction` (`to="0x55d398326f99059ff775485246999027b3197955"`, `spenderAddress="0xb44446b0c8e56988c34f7ff73ae904982b5fdda5"`) and passing that calldata to `/api/v1/dex/pre-transaction/simulate` returns `{"status": "SUCCESS", "allowanceChanges": [{"tokenAddress": "0x55d398326f99059ff775485246999027b3197955", "spender": "0xb44446b0c8e56988c34f7ff73ae904982b5fdda5", ...}]}`.

11. **Binance Agentic Wallet CLI (`@binance/agentic-wallet@1.10.0`) Order Lifecycle & Per-Issuer Execution Path**
    - **Package / Reference**: `@binance/agentic-wallet@1.10.0` (`dist/index.js` & `skills/binance-web3/binance-agentic-wallet/references/market-order.md`)
    - **UTC Timestamp**: `2026-10-02T00:18:20Z`
    - **Observation**:
      - `baw market-order swap --fromTokenQty <qty> --fromToken <addr> --toToken <addr> --binanceChainId 56 --slippage 0.5 --mev true --gasLevel MEDIUM --json` is **asynchronous**: it returns `{"success": true, "data": {"orderId": "...", "clientOrderId": "..."}}`.
      - **Per-issuer backend routing inside `baw`**:
        - **`bstock` (Backed / Dinari, e.g. `NVDAB`, `SPYB`)**: Routes through the standard Web3 DEX aggregator order endpoint `POST /bapi/defi/v1/public/wallet-direct/web-dex/agent/place-order` (matching `/api/v1/dex/aggregator/quote` and `/api/v1/dex/aggregator/swap` `LiquidMesh` routes).
        - **`ondo` (Ondo Global Markets, e.g. `NVDAon`, `AAPLon`, `SPYon`)**: Routes through Ondo's dedicated order endpoint `POST /bapi/defi/v1/public/wallet-direct/web-dex/ondo/place-order` when detected as an Ondo RWA token by `baw`. Because `/api/v1/dex/aggregator/quote` queries the DEX aggregator (`LiquidMesh`), Bine explicitly labels Ondo aggregator quotes as **indicative** for live `baw` execution.
      - **Order polling**: Token approval is handled inside the Agentic Wallet service; callers must poll `baw market-order list --orderId <orderId> --json` until `data.list[0].status` reaches `"FINISHED"` (which populates `txHash`) or `"FAILED"` (or time out with `LIVE_TIMEOUT` if polling exhausts `poll_attempts`).
