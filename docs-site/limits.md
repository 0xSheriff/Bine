# Known Limits

BINE is designed to be honest about what has been empirically verified on-chain versus where coverage is intentionally bounded.

## 1. Unverified Share-Ratio Units Outside `0.25x..5.00x`

- **What we verified**: On `NVDAB` (`tokenToShareRatio = 1.0007782237528078`), two live `$2.00` swaps (`Decision #16` and `Decision #18`) proved that on-chain ERC-20 `balanceOf` credits raw token units (`0.00850539` and `0.00842108` raw tokens), while `baw wallet balance` and `toTokenActualQty` multiply by `tokenToShareRatio` (`0.00851201` and `0.00842763`).
- **What is not verified with a live swap**: Tokens with extreme share ratios such as `KLACon` (`10.0261x`, token price `$20,538.32` vs `$2,048.49` per-share reference), `NFLXon` (`10.0000x`), `PPLTon` (`10.0000x`), and `ENLVon` (`0.0667x`, token price `$1.07` vs `$16.05` reference) have **not** been tested with a live on-chain swap.
- **How BINE handles this**: Rather than guessing how `/aggregator/quote` `toTokenAmount` and `baw` behave on 10x or 0.07x ratios, `quality.py` enforces a hard supported band of `0.25x..5.00x` (`MIN_SANE_SHARE_RATIO = 0.25`, `MAX_SANE_SHARE_RATIO = 5.0`) and refuses tokens outside that band with `quality_unreliable`.

## 2. Thin Regular-Hours Sampling vs. Off-Hours Sampling

- **Dataset distribution**: The historical `token_sample` dataset in `backend/bine.db` (`53,643` rows across `448` tokens) was collected primarily during US post-market, overnight, and weekend sessions (`2026-10-01` through `2026-10-03`), with targeted US regular-hours quote captures on `2026-10-05T15:04Z` (`36` rows in `docs/raw/regular_hours_quotes_2026-10-05.jsonl` + live swap `Decision #18` at `15:05Z`) and `2026-10-07T14:36Z` (`bine.db:decision_log#id=33-34`).
- **Impact**: While `GET /api/quote` always fetches live real-time data on every request, our historical empirical comparison between regular US market hours and overnight/off-hours sessions is based on a much smaller sample count during regular hours than off-hours.

## 3. Live On-Chain Swaps Tested Only on `NVDAB` (`bStocks`)

- **What was executed live on-chain**: Both live `$2.00` swaps (`0x00c0fabd...c228e506` and `0xa3693383...fc2a3e75`) executed into `NVDAB` (`bStocks`) at `$2.00` because Ondo's minimum order is `$5.00` (`[40375]`).
- **What was not executed live on-chain**: We have not executed a live `>= $5.00` on-chain swap into an Ondo token (`NVDAon`, `AAPLon`, `SPYon`) via `baw market-order swap` or `/api/v1/dex/aggregator/ondo/place-order`. For Ondo tokens, `/api/quote` and `/pre-transaction/simulate` dry-runs are verified, and the UI surfaces an explicit execution note when an Ondo route uses `executionMode=RFQ`.

## 4. Hosted Vercel Deployment Is Dry-Run Only (`VERCEL=1`)

- On Vercel (`VERCEL=1`), `BINE_LIVE_MODE` is hard-locked to `False` in `backend/bine/config.py`, `backend/bine/app.py`, and `backend/bine/execution.py`.
- `POST /api/execute` on the hosted deployment runs the full pre-trade guard and Transaction API `/pre-transaction/simulate` dry-run, but never invokes `baw`. Furthermore, SQLite on Vercel uses ephemeral `/tmp/bine.db` storage, so `GET /api/decisions` reflects only the current warm function instance (while the 2 verified BNB Chain swaps are always available on `/receipts` from `frontend/src/data/onchain-receipts.json`).
