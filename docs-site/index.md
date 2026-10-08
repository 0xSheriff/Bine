# BINE Overview

**BINE is a pre-trade safety check for tokenized stocks on BNB Smart Chain (`chainId = "56"`).**

Every US stock on BNB Chain can be issued by more than one provider (`Ondo Global Markets` and `bStocks`), with different order minimums, share ratios, trading hours, and DEX pool depth. Before you or your AI agent buys a tokenized stock, BINE queries the live Binance Web3 RWA catalog, DEX aggregator quotes, and pool liquidity across both issuers, evaluates all 8 deterministic safety rules, and returns one answer:

- **BUY** and the exact verified BSC token contract address to use, or
- **REFUSE** (`DO NOT BUY`) and the exact reason in plain English.

Live demo: TODO add Vercel URL after deploy.  Demo video: TODO.

## Why a Pre-Trade Guard Exists

Across 48,700+ recorded catalog samples (`448` BSC tokens across `Ondo` and `bStocks`, with `40` overlapping dual-issuer tickers), the average cross-issuer price gap when both issuers are healthy is only about 1 basis point (`0.01%`), and the cheaper issuer flips between ticks.

The real danger to humans and autonomous agents is not picking the wrong issuer by 1 basis point; it is executing into a broken trade:

1. **Issuer minimum rejections**: Ondo rejects orders under `$5.00` with business code `[40375] Minimum order amount is 5 USD.` while bStocks fills `$2.00` orders cleanly.
2. **Off-hours pool exhaustion**: Outside US market hours, `SPYon` at `$250.00` falls back to a thin PancakeSwap V3 pool and quotes `$1,087.43` per share against a `$772.52` reference (`+40.75%` to `+82.07%` over reference).
3. **Share-ratio and price outliers**: Tokens like `KLACon` (`10.0261` shares per token, `$20,538.32` token price vs `$2,048.49` per-share reference), `NFLXon` (`10.0000x`), `PPLTon` (`10.0000x`), and `ENLVon` (`0.0667x`, `$1.07` token vs `$16.05` reference) have non-1:1 share ratios outside the verified `0.25-5.00x` band.
4. **Session pauses and thin books**: Single-issuer tokens with `reasonCode="UNSUPPORTED"` (`ICHRon`) or zero routable pool depth (`CVNAon`, `NOWon` returning `[40374] Insufficient liquidity for a quote`) fail on-chain if not caught before swap construction.

## What BINE Checks in One Call

1. **Live Catalog & Session Check**: Pulls `/api/v1/dex/market/rwa/tokens` (`chainId=56`, `ondo` + `bstock`) and checks `openState`, `marketStatus`, `reasonCode`, `referencePrice`, and `tokenToShareRatio`.
2. **Live Quote & Pool Depth Check**: Pulls `/api/v1/dex/aggregator/quote` and `/api/v1/dex/market/token/top-liquidity` for every available issuer of that ticker, converting token amounts into share-adjusted prices (`tokens_out * tokenToShareRatio`).
3. **5 bps Tie Band & Deterministic Tiebreak**: If both `Ondo` and `bStocks` pass all 8 safety rules and their all-in per-share prices are within `5 bps` (`0.05%`), BINE notes `"Either works (within 5 bps)"` and breaks ties deterministically by deeper AMM liquidity, then lower minimum order (`bStocks $0.01 < Ondo $5.00`), then alphabetical symbol.
4. **Transaction API Dry-Run before Any Swap**: On `POST /api/execute` or `bine buy`, BINE builds calldata via `/api/v1/dex/aggregator/swap` and simulates via `POST /api/v1/dex/pre-transaction/simulate` (plus `/approve-transaction` simulation when router allowance is zero) before any live `baw` command can run.

## Next Steps

- [2. Quickstart](/quickstart): Set up keys, run your first check, and run a Transaction API dry-run.
- [3. How BINE Decides](/how-bine-decides): Inspect all 8 safety rules, exact thresholds, and recorded real-world refusals.
- [4. API Reference](/api-reference): Frozen `schema_version: "1"` JSON contract and HTTP endpoints.
- [5. CLI and MCP](/cli-and-mcp): Terminal commands, Model Context Protocol server, and Agentic Wallet skill.
- [6. On-Chain Evidence](/evidence): Verified BNB Smart Chain transactions (`Decision #16` and `Decision #18`).
- [7. Developer Experience Findings](/devex-findings): Sourced ledger of Binance Web3 API findings.
- [8. Known Limits](/limits): Scope boundaries and unverified edge cases.
