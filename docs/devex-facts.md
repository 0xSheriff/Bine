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

7. **Ondo `$5.00` Minimum Order Business Error (`[40375]`) & `$5.00` Boundary Check**
   - **Endpoint**: `GET /build/api/v1/dex/aggregator/quote?binanceChainId=56&fromTokenAddress=0x55d398326f99059ff775485246999027b3197955&toTokenAddress=0xa9ee28c80f960b889dfbd1902055218cba016f75&amount=5000000000000000000&userWalletAddress=0x5B38Da6a701c568545dCfcB03FcB875f56beddC4`
   - **UTC Timestamp**: `2026-10-02T23:57:05Z`
   - **Observation**:
     - Requesting `$2.00` (`2e18`) or `$5.00` (`5000000000000000000`) on `NVDAon` returns `{"code": 40375, "msg": "Minimum order amount is 5 USD.", "data": null}`.
     - Requesting `$5.05` (`5050000000000000000`) immediately after succeeds (`code: 0`) and returns `fromToken.tokenUnitPrice: "0.9998174209196552"` and `tradeFee: "0.02024673"`.
     - **Peg / Fee Hypothesis Status — UNVERIFIED**: While `5.00 * 0.9998174209196552 = 4.999087` and `5.00 - 0.02024673 = 4.97975` both fall under `5.00`, the `[40375]` error response body has `data: null` and contains no field proving which internal formula triggered the rejection. Therefore the exact internal cause is marked **UNVERIFIED**, and Bine uses `$5.50` as the default order size with plain-English copy (`"Ondo's minimum order is $5. After conversion your $5.00 lands just under it. Try $5.50."`).

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

11. **Binance Agentic Wallet CLI (`@binance/agentic-wallet@1.10.0`) Order Lifecycle, Approve + Swap Parent/Child `orderId` Split, & Per-Issuer Execution Path**
    - **Package / Reference**: `@binance/agentic-wallet@1.10.0` (`dist/index.js` & `skills/binance-web3/binance-agentic-wallet/references/market-order.md`)
    - **UTC Timestamp**: `2026-10-03T21:18:17Z`
    - **Observation**:
      - `baw market-order swap --fromTokenQty <qty> --fromToken <addr> --toToken <addr> --binanceChainId 56 --slippage 0.5 --mev true --gasLevel MEDIUM --json` is asynchronous and returns `{"success": true, "data": {"orderId": "..."}}`.
      - **Approve + swap parent/child `orderId` behavior**: First-time swaps run an `approve` tx (`0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64`) before the `swap` tx (`0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506`). `baw market-order swap` returns the parent `orderId` (`26100300001937918699`), `baw market-order list --orderId 26100300001937918699 --json` on that parent ID returns an empty list (`"list": []`), and only `baw market-order list --json` (without `--orderId`) shows the child order (`orderId` `26100300001937918737`, `"status": "FINISHED"`, `"txHash": "0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506"`). `run_agentic_wallet_swap()` in `bine/execution.py` falls back to `baw market-order list --json` when `--orderId` returns an empty list.
      - **Per-issuer backend routing inside `baw`**:
        - **`bstock` (Backed / Dinari, e.g. `NVDAB`, `SPYB`)**: Routes through `POST /bapi/defi/v1/public/wallet-direct/web-dex/agent/place-order` (matching `/api/v1/dex/aggregator/quote` and `/api/v1/dex/aggregator/swap` `LiquidMesh` routes).
        - **`ondo` (Ondo Global Markets, e.g. `NVDAon`, `AAPLon`, `SPYon`)**: Routes through `POST /bapi/defi/v1/public/wallet-direct/web-dex/ondo/place-order` when detected as an Ondo RWA token by `baw`. Because `/api/v1/dex/aggregator/quote` queries the DEX aggregator (`LiquidMesh`), Bine labels Ondo aggregator quotes as indicative for live `baw` execution.

12. **Live `$2.00` `NVDAB` Proof Swap on BSC (`txHash: 0x00c0fabd...e506`) — Dry-Run, Reconciliation, and Quote vs. Fill**
    - **Contract & Wallet**:
      - `USDT` (`fromToken`): `0x55d398326f99059fF775485246999027B3197955`
      - `NVDAB` (`toToken`, read directly from `quote.token.address`): `0x02fca66c1d1afb4e2a7884261eb00f63598a7436`
      - Agentic Wallet (`chainId="56"`): `0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730`
    - **Pre-Swap Quote (`2026-10-03T21:18:06Z`, `market.status = "offhours"`)**:
      - `shares`: `0.008512` (`0.00851212` unrounded; `tokens_received = 0.00850550` `NVDAB` tokens * `token_to_share_ratio = 1.0007782237528078`).
      - `all_in_price_per_share`: `$237.06` vs `reference_price_per_share`: `$235.07` (`spread_pct = +0.85%`, and `+0.90%`–`+0.99%` on preceding off-hours samples).
    - **Transaction API Dry-Run (`docs/dry_run_nvda_2usd.json`)**:
      - In `docs/dry_run_nvda_2usd.json`, `"passed": true` with `"fail_reason": "execution reverted: BEP20: transfer amount exceeds allowance"` is the expected pre-approval state when simulating the swap calldata before USDT is approved to the router (`0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`), and the approval simulation (`"approval_simulation_status": "SUCCESS"`, `/api/v1/dex/aggregator/approve-transaction` for `2000000000000000000` wei) returned `SUCCESS`.
    - **Reconciliation Note (`docs/live_swap_nvda_2usd.json`, `DecisionLog #16`, and `docs/raw/`)**:
      - The first live `$2` `NVDAB` swap recorded the parent `orderId` (`26100300001937918699`) and no `txHash` (`status: "LIVE_TIMEOUT"`). `docs/live_swap_nvda_2usd.json` and `DecisionLog #16` were reconciled afterwards from `baw market-order list --json` (child `orderId` `26100300001937918737`) and the BSC receipt for `0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506`. Untouched `baw` outputs and the commands that produced them are saved in `docs/raw/`.
    - **On-Chain Execution (`2026-10-03T21:18:17Z`, BSC Block `125555002`)**:
      - **Approve Tx**: `0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64` (`feeValue = 0.000002932518144096 BNB`).
      - **Swap Tx**: `0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506` (`status = 0x1`, `gasUsed = 775,387`, `feeValue = 0.000047976548789549 BNB`, total gas = `0.00005091 BNB` $\approx \$0.040$).

13. **`baw wallet balance` vs. On-Chain `eth_call` `balanceOf` Share-Ratio Gap**
    - **Observation**:
      - `baw wallet balance --binanceChainId 56 --json` (and `toTokenActualQty` in `baw market-order list --json`) shows `0.00851201289192116` `NVDAB`.
      - On-chain `eth_call` `balanceOf(0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730)` on `0x02fca66c1d1afb4e2a7884261eb00f63598a7436` returns `8505393792444895` wei (`0.008505393792444894` raw tokens, or `0.0085053938` rounded).
      - The gap equals `tokenToShareRatio` `1.0007782237528078`:
        `0.008505393792444894 * 1.0007782237528078 = 0.00851201289192116`.
      - Compared against Bine's pre-swap quote (`0.00850550` raw tokens / `0.00851212` shares), the on-chain fill is within `-0.12 bps` (`-0.13 bps` in shares), and `-4.7 bps` against the earlier `0.008516` off-hours quote.

