# BINE — AI Context & Handoff Memory

## 1. Project Overview
- **What it is**: BINE is a **pre-trade guard for tokenized stocks on BNB Smart Chain (`chainId="56"`)**. Before a person or an agent buys a tokenized stock, Bine answers: *is it safe right now, what will I really get, and if not, why not.*
- **Why this product focus**: Across our 48,700+ recorded samples, the average cross-issuer price gap between Ondo and bStocks is ~1 bp, the cheaper issuer flips between ticks, and each issuer is cheaper on 20 of 40 overlapping tickers. The real user-protecting value is the deterministic **refusals** (share-ratio traps, Ondo's `$5.00` minimum order `[40375]`, session pauses, thin DEX/PMM pool depth such as `SPYon`'s reproducible `+40.75%` spread at `$250`, and sub-`$1` outlier tokens like `ENLVon`). Issuer comparison is a one-line tiebreak (`within 5 bps → "Either works"` with deterministic tiebreak: deeper AMM liquidity → lower minimum order → alphabetical).
- **Plug-and-play surfaces**:
  1. **Frozen HTTP API (`GET /api/quote`, `POST /api/execute`, `/docs`)**: `schema_version: "1"` response contract.
  2. **CLI (`bine check <TICKER> <USD> [--json]`, `bine buy <TICKER> <USD>`)**: Console entry point for humans and shell scripts.
  3. **MCP Server (`python -m bine.mcp_server`, stdio)**: Exposes `bine_check(ticker, amount_usd)` and `bine_buy(ticker, amount_usd, confirm=False)`.
  4. **Binance Wallet Skill (`skills/bine-pre-trade-guard/SKILL.md`)**: Instructs Agentic Wallet (`baw`) agents to run `bine check` before any `baw market-order swap` on a tokenized stock.
  5. **One-Screen Web UI (`frontend/`)**: Thin client of the same HTTP API with light/dark mode and a collapsed technical `Details` disclosure.

## 2. Architecture
- **Signed HTTP Client (`backend/bine/client.py`)**: Async `httpx` wrapper (`BinanceClient`) for `https://web3.binance.com/build`. Re-computes `X-OC-TIMESTAMP` and `X-OC-SIGN` on **every retry attempt**. Includes optional `DEV_DNS_FALLBACK=true` (`8.8.8.8` resolver) for local routers.
- **Live RWA Token Catalog (`backend/bine/quote_engine.py`)**: Fetches `/api/v1/dex/market/rwa/tokens` (`ondo` + `bstock` on BSC `56`) live per request with a 60-second in-memory cache (`442` Ondo + `46` bStocks = `448` unique tickers).
- **Data Quality Filter (`backend/bine/quality.py`)**: Enforces minimum price (`$1.00`), minimum 24h volume (`$1.0M`), and split-ratio bounds (`0.25x–20.0x`), quarantining outliers like `ENLVon` and `SOXSon`.
- **Deterministic Pre-Trade Guard (`backend/bine/quote_engine.py`)**: Evaluates 8 refusal codes (`unknown_ticker`, `amount_over_cap`, `quality_unreliable`, `market_closed`, `reference_stale`, `below_issuer_minimum`, `depth_thin`, `slippage_too_high`), enforces a 5 bps tie band (`"Either works"`), and returns the frozen `schema_version: "1"` payload.
- **Safe Execution Engine (`backend/bine/execution.py`)**: Dry-runs unsigned swap calldata (`/api/v1/dex/aggregator/swap`) + ERC-20 allowance (`/api/v1/dex/aggregator/approve-transaction`) via `POST /api/v1/dex/pre-transaction/simulate` against the `LiquidMesh` router (`0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`). Live execution via `baw market-order swap` requires `BINE_LIVE_MODE=true`, `BINE_ADMIN_TOKEN`, and stays within `BINE_MAX_TRADE_USD=6.00` and `BINE_DAILY_CAP_USD=10.00`.
- **Offline Evidence Collector (`tools/collect_evidence.py`)**: Optional standalone research script moved out of the live request path.

## 3. Tech Stack
- **Backend**: Python 3.13 (`.venv`), `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `aiosqlite`, `httpx`, `pydantic`, `pydantic-settings`, `pytest`, `pytest-asyncio`, `respx`.
- **Database**: Optional small SQLite (`./bine.db`) / PostgreSQL database storing `decision_log`.
- **Frontend**: React 19, Vite 8, TypeScript, Tailwind CSS v4, `@tanstack/react-query`, `@fontsource-variable/inter` (bundled, zero external font requests), `motion` (`motion/react`), `@paper-design/shaders-react` (`LiquidMetal`).
- **APIs**: Binance Web3 Wallet REST APIs (`https://web3.binance.com/build`).
- **Execution**: Binance Agentic Wallet CLI (`@binance/agentic-wallet` v1.10.0, `baw market-order swap` + `baw market-order list`).

## 4. Current State
- **Phases 0–9 Complete (plus two verified live `$2.00` `NVDAB` swaps and `ui-redesign` branch)**:
  - **Phase 0**: Reconciled summary contradictions, verified `baw` CLI flags and order lifecycle, proved `SPYon` `$250` `+40.75%` spread across 5/5 runs, and separated `below_issuer_minimum`.
  - **Phase 1**: Frozen `GET /api/quote` `schema_version: "1"` contract with 13 top-level keys, 8 refusal codes, 5 bps tie band (`Either works`), deterministic tiebreak, and any-ticker (`448` tickers including `AAPL`) support.
  - **Phase 2**: Removed background sampler from the live request path; `/api/quote` uses a 60s in-memory `/rwa/tokens` cache; moved sampler to `tools/collect_evidence.py`; simplified `backend/Procfile` and `docs/optional-hosting.md`; removed `/evidence` page.
  - **Phase 3**: Implemented `bine` CLI (`backend/bine/cli.py`), stdio MCP server (`backend/bine/mcp_server.py`), and Binance Wallet Skill (`skills/bine-pre-trade-guard/SKILL.md`).
  - **Phase 4**: Set default demo amount to `$5.00`, `BINE_MAX_TRADE_USD=6.00`, added `BINE_ADMIN_TOKEN` `403` gate on `execute_live=true`, per-IP sliding-window rate limiting, tightened CORS, and documented approval handling. Live swap verified twice (`Decision #16` and `Decision #18`).
  - **Phase 5 & 6**: Rebuilt `frontend/` into a single-screen pre-trade guard with zero-flash Light & Dark themes (`prefers-color-scheme` + `localStorage['bine-theme']` + sun/moon toggle), plain-English main view, inline dry-run confirm panel, and collapsed `<details>` disclosure.
  - **Phase 7**: `51/51` `pytest` tests passing (`backend/tests/`), `npm run build` succeeding with 0 TypeScript errors, cold load measured at ~1.5s, and 24 screenshots captured across `390px`, `768px`, and `1440px` in both light and dark themes.
  - **Phase 8**: Created `docs/devex-facts.md`, `docs/devex-report-facts.md`, and `docs/devex-report-map.md`.
  - **UI Redesign & 7-Phase Refinement Pass (`ui-redesign` branch, `pre-redesign` tag at `aa3d56f`)**:
    - Completed skin-only frontend redesign (`LiquidMetal` shader logo, 2D SVG tilted lavender ring + 3D gold coin hero art, bundled `@fontsource-variable/inter`) followed by the 7-phase refinement pass (`PHASE 0` through `PHASE 6`):
      - `PHASE 0` (`b203cc7`): Wrote `docs/ui-audit.md` with baseline screenshots, CDP layout/a11y/bundle measurements, and per-screen scores.
      - `PHASE 1` (`b58e63f`): Split `/` (Landing) and `/guard` (interactive Pre-Trade Guard), changed cold default theme to Light, added `LiveModeChip`, lazy-loaded routes and `LiquidMetal`, reducing main JS chunk to `470.93 kB` raw (`< 500 kB`).
      - `PHASE 2` (`463e90d`): Built `frontend/src/pages/Guard.tsx` with WAI-ARIA APG combobox (`ArrowDown`/`ArrowUp`/`Enter`/`Escape`/`Home`/`End`), 4 presets, 5 plain-English decision metrics, 6 guard checks, ticking quote age + `"Refresh quote"`, progressive disclosures (`How this was calculated`, `Compare issuers`, `Recent checks`), 503/network error banners, and humanized `market_closed` copy (`51/51` pytest tests passing).
      - `PHASE 3` (`03f9b7b`): Built `frontend/src/pages/Home.tsx` (`2.51` screens tall at `1440px`) with Hero, Proof strip, How Bine works, What Bine refuses (`frontend/src/data/recorded-refusals.json`), Verified on BNB Chain (`frontend/src/data/onchain-receipts.json`), and Closing band.
      - `PHASE 4` (`c6f73f7`): Rebuilt `frontend/src/pages/Refusals.tsx` (8-rule legend, 6 recorded refusals from Oct 5 regular + overnight sessions, one-at-a-time `"Run live now"` comparator), `frontend/src/pages/Receipts.tsx` (summary cards, expandable BscScan/BscTrace receipt details with filled vs quoted shares, block number, and BNB gas, empty state via `?empty=1`), and `frontend/src/pages/Integrate.tsx` (WAI-ARIA APG tabs `HTTP`/`CLI`/`MCP`/`Agent skill` with `ArrowLeft`/`ArrowRight`/`Home`/`End`, live `"Try it"` runner, 13-key response table, and `401/403`/`429`/`503` errors table).
      - `PHASE 5` (`d9e4eba`): Executed real headless Chrome CDP pass across all 30 screen/viewport/theme combinations + interactive states (`0` horizontal overflow, `0` undersized tap targets, `0` em dashes, `0` console errors, `0` external network requests, verified `<h1>` route-change focus and keyboard navigation) and updated `docs/ui-audit.md` (`9.2/10` to `9.5/10`).
      - `PHASE 6` (`7fd9564`): Added `docs/ui-design-rules.md`, updated `docs/screenshots/*.png`, added `"For judges"` section at the top of `README.md`, and verified all final checks.
    - **4-Phase Polish Pass (`PHASE A` through `PHASE D` on `ui-redesign`)**:
      - `PHASE A` (`1a63f46`): Eliminated every displayed underscore (`_`) outside `[data-raw-code]` across all 5 routes via `frontend/src/lib/humanize.ts`, verified `recorded-refusals.json` against `docs/raw/regular_hours_quotes_2026-10-05.jsonl` and `docs/devex-facts.md`, and added `scripts/check_underscores.py` (`TOTAL_UNDERSCORE_OFFENDERS=0`).
      - `PHASE B` (`42c4010`): Unified header logo, footer logo, and `favicon.svg` onto monochrome silver/chrome (`colorTint="#ffffff"` on `#000000`, frozen `LiquidMetal` at `speed={0}` under `prefers-reduced-motion: reduce`), unified container widths (`max-w-[1240px]`), and verified `0px` logo `x` drift (`100px`) and `0.0000/255` pixel diff via `scripts/verify_logo_and_alignment.py`.
      - `PHASE C` (`4a68c5c`): Built `frontend/src/components/GlassStack.tsx` and liquid-glass CSS (`.bine-glass-panel` + `.bine-glass-scrim` + `@supports (backdrop-filter: url(#bine-glass))` Chromium SVG refraction + `rAF` specular cursor highlight + `390px` mobile sheet) across all 5 routes (`Home`, `Guard`, `Refusals`, `Receipts`, `Integrate`), keeping the main JS chunk at `485.90 kB` raw (`< 500 kB`).
      - `PHASE D`: Captured and inspected all 30 `docs/screenshots/glass_<page>_<theme>_<width>.png` screenshots, verified performance traces (`0` long tasks `> 50 ms`) and WCAG 2.2 AA contrast (`> 14:1`), updated `memory.md`, and codified the 4 standing frontend rules in `.agents/skills/bine-ui-standing-rules/SKILL.md`.

## 5. Recent Changes
- **2026-10-02 (Item 1 — State Check & Dead Code Trim)**:
  - Verified `48/48` `pytest -v` tests pass and `npm run build` succeeds (`274ms`, 0 TypeScript errors).
  - Removed dead legacy files (`backend/bine/sampler.py`, `backend/bine/schemas.py`, `docs/deploy-always-on.md`, `frontend/src/pages/Evidence.tsx`, `frontend/src/pages/Compare.tsx`, `frontend/src/pages/WeekendGap.tsx`, `frontend/src/pages/TokenDetail.tsx`, `frontend/src/pages/Agent.tsx`, `frontend/src/pages/HowItWorks.tsx`).
  - Added new rebuild files: `backend/bine/cli.py` (242 lines), `backend/bine/mcp_server.py` (204 lines), `tools/collect_evidence.py`, `skills/bine-pre-trade-guard/SKILL.md`, `docs/optional-hosting.md`, `docs/devex-facts.md`.
  - Trimmed `backend/bine/quote_engine.py` from `1,014` lines (697 pre-rebuild baseline) down to `657` lines and `frontend/src/pages/Home.tsx` from `1,035` lines (baseline) down to `625` lines (`3,982` total lines across all `backend/bine/*.py` + `frontend/src/pages/*.tsx`).
- **2026-10-02 (Item 2 — Clean Install in `/tmp/v`)**:
  - Updated `backend/pyproject.toml` `[project.scripts]` with `bine = "bine.cli:main"` and `bine-mcp = "bine.mcp_server:main"`.
  - Verified in fresh `/tmp/v` venv (`/tmp/v/bin/pip install -e backend`) that `/tmp/v/bin/bine check NVDA 5` and `/tmp/v/bin/bine-mcp` (`tools/list`) execute with zero manual edits.
- **2026-10-02 (Item 3 — Screenshot Hooks Removed from Production Build)**:
  - Removed `ss`, `vw`, and `dry_run` query params from `frontend/src/pages/Home.tsx` and gated `receipt` strictly inside `if (import.meta.env.DEV)`.
  - Verified via `npm run build` and `grep -oE '"(ss|vw|receipt|dry_run)"' dist/assets/*.js` that zero test hooks appear in the production bundle (`dist/assets/index-CO_HJepa.js`).
- **2026-10-02 (Item 4 — `priceImpactPercent` Scale Verified & Documented)**:
  - Verified `_parse_price_impact_pct()` in `backend/bine/quote_engine.py` converts the `0–1` fractional string (`"0.2974289557"`) into `29.7429%` (`0–100` scale).
  - Updated `docs/friction-log.md` and `docs/devex-facts.md` (item 9) to explain that `priceImpactPercent` is a `0–1` fraction (`29.74%` output drop, matching the ~29.1% share reduction from `$100` to `$250` on `SPYon`) mislabeled as `Percent`, and removed any claim that it understates.
- **2026-10-02 (Item 5 — Execution Path, Async Order Polling, & Indicative Ondo Label)**:
  - Verified `run_agentic_wallet_swap()` in `backend/bine/execution.py` polls `baw market-order list --orderId <id> --json` and handles `FINISHED` (`txHash` -> `LIVE_SUBMITTED`), `FAILED` (`LIVE_ERROR`), and polling timeout (`LIVE_TIMEOUT`). Added `test_baw_async_order_polling_finished_failed_and_timeout` (`49/49` pytest tests pass).
  - Documented per-issuer `baw` routing in `docs/devex-facts.md` (`bstock` -> `/web-dex/agent/place-order`, `ondo` -> `/web-dex/ondo/place-order`) and labeled Ondo aggregator quotes as indicative in `frontend/src/pages/Home.tsx` and `backend/bine/quote_engine.py`.
- **2026-10-02 (Item 6 — Safety Gates & Secret Scan Verified)**:
  - Verified constant-time `hmac.compare_digest` check for `BINE_ADMIN_TOKEN` gating `execute_live=true` in `backend/bine/app.py` (lines 472–480) and `backend/bine/execution.py` (lines 575–587), sliding-window per-IP rate limiting (`60/min` on `/api/quote`, `20/min` on `/api/execute`), restricted CORS (`GET, POST` and `Content-Type, X-Bine-Admin-Token`), and `BINE_LIVE_MODE=false` in `docs/optional-hosting.md`.
  - Confirmed `git check-ignore -v .env` matches `Bine/.gitignore:1:.env` and verified `0` occurrences of `BINANCE_API_KEY` or `BINANCE_SECRET_KEY` across the working tree and git commit history.
- **2026-10-02 (Item 7 — UI Verification & Cold-Load Latency)**:
  - Fixed `quote_stock()` in `backend/bine/app.py` so `GET /api/quote?details=true` preserves the optional `details.issuers` payload while keeping `QuoteResponseModel` on `/docs`.
  - Captured and visually inspected 24 screenshots across `BUY` (`NVDA` `$5`), `REFUSE` (`AAPL` `$2` and `SPYon` `$250`), and the `Confirm` dry-run panel in Light and Dark themes at `390px`, `768px`, and `1440px` using Chrome DevTools `Emulation.setDeviceMetricsOverride`.
  - Measured cold-load latency (`/rwa/tokens` cache cold + 2 live `/aggregator/quote` + 2 `/top-liquidity` calls) at `3.244s`, warm-catalog live quote latency at `0.931s–1.306s`, and warm 15s quote-cache latency at `1.2ms`.
- **2026-10-02 (Item 8 — Final Judge Test Re-Score)**:
  - Re-scored all 12 categories with concrete file/test/screenshot/command evidence (`11/12` categories passing at `9/10–10/10`; `Live On-Chain Execution` explicitly marked `0/10 (UNVERIFIED)` until the user runs the live `$2`/`$5` swap commands).
- **2026-10-03 (Item A.1 — Standalone Git Repo & Staged Secret Scan)**:
  - Initialized a dedicated git repository inside the project root (`git init`), confirmed `git check-ignore -v .env` -> `.gitignore:1:.env	.env`, scanned all staged files for `BINANCE_API_KEY` and `BINANCE_SECRET_KEY` (`staged_key_matches=0`, `staged_secret_matches=0`), and created root commit `1a6e1d1`.
- **2026-10-03 (Item A.2 — `baw` Command Flags & `npx` Fallback)**:
  - Verified `npx --yes @binance/agentic-wallet@1.10.0 market-order swap --help`: uses `--fromTokenQty`, `--fromToken`, `--toToken`, `--binanceChainId 56`, `--slippage` (`"auto"` or `0–100` percentage points, e.g. `0.5` = `0.5%`), `--mev true`, `--gasLevel MEDIUM`, `--json`.
  - Updated `run_agentic_wallet_swap()` in `backend/bine/execution.py` to fall back to `npx --yes @binance/agentic-wallet@1.10.0` when `baw` is not installed globally on `PATH`.
- **2026-10-03 (Item A.3 — `$5.50` Default Amount & Plain-English Minimum Copy)**:
  - Set default order amount to `$5.50` across UI, CLI help, MCP descriptions, `app.py`, `SKILL.md`, and `README.md`.
  - Updated `below_issuer_minimum` message in `backend/bine/quote_engine.py` to `"Ondo's minimum order is $5. After conversion your $5.00 lands just under it. Try $5.50."` and documented the `5.00` vs `5.05` `[40375]` test in `docs/devex-facts.md` (`UNVERIFIED` internal cause since `data` is `null` on `40375`).
- **2026-10-03 (Item A.4 — Local `BINE_API_URL` Default for CLI & MCP)**:
  - Updated `backend/bine/config.py` (`bine_api_url = "http://localhost:8000"`), `backend/bine/cli.py`, and `backend/bine/mcp_server.py` so `bine` and `bine-mcp` default `BINE_API_URL` to `http://localhost:8000` and print a single clear line showing how to start `uvicorn bine.app:app --app-dir backend --port 8000` when the backend is unreachable.
- **2026-10-03 (Item A.5 — Remove `apscheduler` and `test_sampler.py`)**:
  - Removed `apscheduler>=3.10` from `backend/pyproject.toml`, removed `bine_sample_interval_minutes` from `backend/bine/config.py`, deleted `backend/tests/test_sampler.py`, and updated `tools/collect_evidence.py` to use a plain `asyncio.sleep` loop with zero `apscheduler` dependency.
- **2026-10-03 (Item B — Four Routes `/`, `/integrate`, `/refusals`, `/receipts` & SPA Fallback)**:
  - Updated `TopHeader` in `frontend/src/components/shared.tsx` with wordmark, 4-route nav (`Guard`, `Integrate`, `Refusals`, `Receipts`), and theme toggle.
  - Added `frontend/src/pages/Integrate.tsx` (123 lines), `frontend/src/pages/Refusals.tsx` (122 lines, live API calls for `AAPL $2`, `SPYon $250`, `ENLV $5.50`, catalog share-ratio trap `KLAC`, and catalog session-closed token `ICHR`), and `frontend/src/pages/Receipts.tsx` (79 lines, `live_only=true` filtering rows with `tx_hash`).
  - Added SPA static file and deep-link fallback route in `backend/bine/app.py`. Gzip bundle grew by only `3.18 kB` (`101.34 kB -> 104.52 kB`).
- **2026-10-03 (Item C — Root `README.md`)**:
  - Created `README.md` with one-sentence product definition, "Run it in 3 commands" quickstart (requiring `BINANCE_API_KEY` and `BINANCE_SECRET_KEY` in `.env`), local URL (`http://localhost:8000`), HTTP API / CLI / MCP / Wallet Skill usage, screenshot index, and safety defaults.
- **2026-10-03 (Item A.6 — Re-capture & Inspect All 24 Screenshots)**:
  - Re-captured all 24 screenshots (`BUY NVDA $5.50`, `REFUSE AAPL $2`, `REFUSE SPYon $250`, and `Confirm` dry-run panel at `390px`, `768px`, and `1440px` in Light and Dark themes) on the current 4-route build (`dist/assets/index-B71wR5wL.js`).
  - Opened and inspected all 24 PNGs via `view_file`: confirmed `ui_confirm_light_1440.png` and all 5 other `ui_confirm_*` screenshots render the expanded `SIMULATION PASSED` panel (`Decision #9–#14`), all `768px` and `1440px` screenshots render the updated `Details` bar (`2 issuers · market offhours` / `1 issuer · market offhours`), and all 24 screenshots show the 4-route header (`Bine | Guard Integrate Refusals Receipts`) and `$5.50` default with zero defects.
- **2026-10-03 (Item D — 12-Category Re-Score)**:
  - Completed the 12-category evaluation (`minimalism`, `real-world usefulness`, `immediate usability`, `plug and play`, `technical execution`, `originality`, `UX`, `visual quality`, `demonstration potential`, `hackathon differentiation`, `clarity`, `technical story`) with concrete file, test, command, and screenshot evidence (`Overall: 9.0/10` before live swap, `9.5/10` after live `$2 NVDAB` swap verification).
- **2026-10-03 (Live `$2.00` `NVDAB` Swap Verification & Dynamic `--toToken` Generator Fix)**:
  - Added `build_baw_swap_command_from_quote(quote, expected_address=...)` in `backend/bine/execution.py` and wired it into `execute_trade_pipeline()`, `run_agentic_wallet_swap()`, and `backend/bine/cli.py` (`bine check --baw` and `bine buy`) so `--toToken` is always read directly from `quote["token"]["address"]` (`0x02fca66c1d1afb4e2a7884261eb00f63598a7436` for `NVDAB`) and verified character-by-character before any swap.
  - Verified Agentic Wallet (`0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730` on BSC `56`) balance (`5.00 USDT`, `0.00025936 BNB`), ran and saved the Transaction API dry-run (`docs/dry_run_nvda_2usd.json`), and executed the `$2.00` `NVDAB` live swap (`docs/live_swap_nvda_2usd.json`, `Decision #16`).
  - Confirmed on-chain (`txHash: 0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506`, BSC Block `125555002`, approve `txHash: 0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64`, total gas `0.00005091 BNB` $\approx \$0.040$): `0.00851201289192116` `NVDAB` shares (`8505393792444895` wei = `0.008505393792444894` raw `NVDAB` tokens * `1.0007782237528078` `tokenToShareRatio`) landed at `0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730` (`-0.13 bps` vs immediate `0.00851212` quote, `-4.7 bps` vs earlier `0.008516` quote).
  - Discovered and fixed parent-vs-child `orderId` split on `approve` + `swap` in `run_agentic_wallet_swap()` (`swap` returned parent `orderId: 26100300001937918699` while `market-order list` recorded child `orderId: 26100300001937918737`).
- **2026-10-05 (Asset Cleanup, `docs/screenshots/`, `AuthError` `HTTP 503`, Share-Ratio Limit Copy, Regular-Hours Quotes & Second `$2.00` `NVDAB` Swap)**:
  - Removed unused `frontend/src/assets/hero.png`, `react.svg`, `vite.svg`, and `docs/schema.json` via `git rm`; copied the 12 README screenshots into `docs/screenshots/` and updated `README.md` links.
  - Added `AuthError` (`backend/bine/errors.py`, `backend/bine/client.py`, `backend/bine/app.py`, `backend/bine/cli.py`, `50/50` pytest tests passing) so missing or rejected Binance API keys (`40101`, `40102`, `HTTP 302/401/403`, or non-JSON response) return `HTTP 503` (`{"detail": "Binance API keys missing or rejected"}`) on `/api/quote` and print a single line with exit code `1` in `bine`. Saved keyless response evidence in `docs/raw/rwa_tokens_no_key_2026-10-05.txt`.
  - Updated share-ratio refusal copy in `backend/bine/quality.py`, `backend/bine/quote_engine.py`, and `frontend/src/pages/Refusals.tsx` to state the ratio and the supported `0.25–5.00x` limit instead of calling the data unreliable, and prioritized `depth_thin` first when `/api/v1/dex/aggregator/quote` fails with `40374` (`Insufficient liquidity`) with the share-ratio note included on a second line.
  - Ran the US regular-hours quote matrix (`2026-10-05T15:04Z`, `marketStatus = "regular"`, 94 minutes after open / `11:04` New York, saved to `docs/raw/regular_hours_quotes_2026-10-05.jsonl`) and executed the second live `$2.00` `NVDAB` swap (`bine buy NVDA 2 --yes`) with zero hand edits (`DecisionLog #17` dry-run + `DecisionLog #18` live execution, `orderId: 26100500001942767719`, `txHash: 0xa3693383a9493600df08ae10a6a64faa6a7543e3bde9f6bbca3fd7acfc2a3e75`, BSC Block `125889084`, `docs/live_swap_nvda_2usd_second_2026-10-05.json`).
  - Verified on-chain USDT allowances (`docs/raw/usdt_allowance_2026-10-05.txt`): `allowance(0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730, 0xb300000b72DEAEb607a12d5f54773D1C19c7028d)` is `uint256.max - 4 * 10^18` while `allowance(..., 0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5)` is `0`. Updated `run_transaction_dry_run()` in `backend/bine/execution.py` to check `allowance(wallet, 0xb300...)` via BSC RPC when a wallet address is configured (`51/51` pytest tests passing), and created `docs/devex-report-facts.md`.
- **2026-10-06 (Copy-and-Logic Cleanup, DevEx Report Map, & `ui-redesign` Branch)**:
  - **Items 1–4 & A–D on `master`**: Updated `REQUIRES_APPROVAL` display label + tooltip, separated `quality_unreliable` vs `market_closed` (`[40367]`/`[40369]`) vs `depth_thin` (`[40374]`), refined share-ratio and negative-spread `slippage_too_high` messages, removed em dashes (`—`), and created `docs/devex-report-map.md`.
  - **`ui-redesign` Branch (Skin-Only Frontend Redesign)**:
    - Added `@fontsource-variable/inter` (bundled, removed external Google Fonts links from `frontend/index.html`), `motion` (`motion/react`), and `@paper-design/shaders-react` (`LiquidMetal`).
    - Created `frontend/src/assets/bine-mark.svg`, `frontend/src/assets/bine-mark.png` (`512x512` transparent-background white `B` mask), `frontend/public/favicon.svg`, and `frontend/src/components/BineLogo.tsx` (`BineLogoTile` + `BineWordmarkLockup` with `LiquidMetal`, `IntersectionObserver` offscreen pause, and WebGL/reduced-motion CSS fallback).
    - Created `frontend/src/components/HeroArt.tsx` (2D SVG tilted lavender ring with 3D wall/bevel/shadow + 3D gold coin with rim ridges, embossed `BINE` mark, `offset-path` rolling entrance, `rAF` pointer parallax, and scroll fade).
    - Updated `frontend/src/index.css`, `frontend/src/components/shared.tsx` (`TopHeader` with `"Check a trade"` pill and `Footer` with circular GitHub/X pills), `frontend/src/App.tsx`, and all 4 pages (`Home.tsx`, `Integrate.tsx`, `Refusals.tsx`, `Receipts.tsx`).
    - Verified `51/51` pytest tests pass, production build adds `+59.10 kB` JS gzipped (`+61.68 kB` total CSS+JS gzipped, under the `120 kB` budget), `0` em dashes in `frontend/src`, `0` console errors/warnings, `0` external network requests, and 34 screenshots captured across all routes, themes, viewports, and motion sequences.
- **2026-10-07 (`PHASE 0`–`PHASE 6` Refinement Pass + `PHASE A`–`PHASE D` Polish Pass on `ui-redesign`)**:
  - Tagged `pre-redesign` at `aa3d56f` for rollback safety.
  - **`PHASE 0`–`PHASE 6` (`b203cc7`..`7fd9564`)**: Audited all screens via Chrome CDP (`docs/ui-audit.md`), split `/` and `/guard`, added WAI-ARIA APG combobox and tabs, rebuilt `Refusals.tsx`, `Receipts.tsx`, and `Integrate.tsx`, added `docs/ui-design-rules.md`, and verified all 30 screen/theme/viewport states.
  - **`PHASE A` (`1a63f46`)**: Created `frontend/src/lib/humanize.ts` and `scripts/check_underscores.py`, removing all displayed underscores outside `[data-raw-code]` (`TOTAL_UNDERSCORE_OFFENDERS=0`).
  - **`PHASE B` (`42c4010`)**: Unified `BineLogo.tsx`, `Footer`, and `favicon.svg` on monochrome chrome (`speed={0}` when `prefers-reduced-motion: reduce`), unified `max-w-[1240px]` containers across all 5 pages, and verified `0px` logo `x` drift (`100px`) and `0.0000/255` pixel diff via `scripts/verify_logo_and_alignment.py`.
  - **`PHASE C` (`4a68c5c`)**: Created `frontend/src/components/GlassStack.tsx` and `.bine-glass-panel` / `.bine-glass-scrim` CSS with SVG refraction and cursor specular highlight across all 5 routes; verified `0` long tasks `> 50 ms`, `> 14:1` contrast, `0` overflow failures, and `485.90 kB` main JS chunk via `scripts/verify_glass_and_perf.py`.
  - **`PHASE D`**: Captured and inspected all 30 `docs/screenshots/glass_*.png` files, updated `memory.md`, and created `.agents/skills/bine-ui-standing-rules/SKILL.md`.

## 6. Important Decisions
- **5 bps Tie Band (`"Either works"`)**: When both issuers are eligible and within 5 bps on all-in price per share, Bine does not claim a price winner; it says `"Either works"` and picks deterministically (deeper AMM liquidity first → lower minimum order → alphabetical).
- **`below_issuer_minimum` Refusal Code**: Separated `[40375] Minimum order amount is 5 USD.` from `depth_thin` into its own refusal code `below_issuer_minimum`.
- **Single Stateless Web Service**: No background worker is required in production; `decision_log` uses optional SQLite/Postgres.

## 7. Known Issues & Domain Quirks
- **Ondo `$5` Minimum Order (`[40375]`)**: Ondo rejects orders under `$5.00` (and `$5.00` exact lands under `$5` after conversion; `$5.05+` succeeds), while `bStocks` executes down to `$2.00`. Default order amount is `$5.50` and `BINE_MAX_TRADE_USD=6.00` so both issuers are executable.
- **`SPYon` Reproducible `+40.75%`–`+82.07%` Spread at `$250` Off-Hours vs. `+0.0037%` Regular Hours**: Off-hours, `SPYon` executes near reference at `$25` and `$100` on `PancakeSwap V3`, then jumps to `+40.75%`–`+82.07%` above reference at `$250` across all runs (caught deterministically by `slippage_too_high`). During US regular trading hours (`marketStatus = "regular"`), `SPYon` routes through `Ondo RWA` at `+0.0037%` (`+0.37 bps`).
- **Local DNS**: Pass `DEV_DNS_FALLBACK=true` on local networks where default DNS times out on `web3.binance.com`.

## 8. Current Task
- Completed both the 7-phase frontend refinement pass (`PHASE 0`–`PHASE 6`) and the 4-phase polish pass (`PHASE A`–`PHASE D`) on branch `ui-redesign`.

## 9. Next Steps
1. Review `ui-redesign` branch in browser at `http://localhost:5174` and merge to `master` when approved by user.

## 10. Important Files
- `memory.md` — Primary AI context and handoff state.
- `README.md` — Root documentation (`For judges` section, 3-command quickstart, and safety defaults).
- `docs/ui-audit.md` — Phase 0 baseline, Phase 5 post-refinement, and Phase C liquid-glass UI audit with performance traces.
- `docs/ui-design-rules.md` — Frontend design rules, tokens, typography, and component patterns.
- `.agents/skills/bine-ui-standing-rules/SKILL.md` — Workspace skill enforcing the 4 standing frontend UI rules.
- `scripts/check_underscores.py` — Automated CDP underscore scanner across all routes/themes/states.
- `scripts/verify_logo_and_alignment.py` — Automated CDP logo `x`-coordinate and pixel-diff verifier.
- `scripts/verify_glass_and_perf.py` — Automated CDP liquid-glass screenshot, contrast, overflow, and performance trace verifier.
- `docs/PROJECT_BRIEF.md` — Original brief.
- `docs/friction-log.md` — Empirical friction log with raw API measurements.
- `docs/devex-facts.md` — Raw verified DevEx facts (Phase 8).
- `docs/devex-report-facts.md` — Concise bullet fact sheet of all DevEx findings.
- `docs/devex-report-map.md` — Form-aligned Developer Experience Report mapping table.
- `docs/optional-hosting.md` — Optional single-service hosting guide (Phase 2).
- `docs/dry_run_nvda_2usd.json` — Saved Transaction API dry-run output before live swap.
- `docs/live_swap_nvda_2usd.json` — Saved first `$2.00` `NVDAB` live swap receipt (`Decision #16`).
- `docs/live_swap_nvda_2usd_second_2026-10-05.json` — Saved second `$2.00` `NVDAB` live swap receipt (`Decision #18`, zero hand edits).
- `tools/collect_evidence.py` — Standalone evidence sampler utility.
- `backend/bine/client.py` — `BinanceClient` + `maybe_enable_dev_dns_fallback`.
- `backend/bine/quality.py` — Data-quality filter (`assess_token_quality`, `MAX_SHARE_RATIO = 5.0`).
- `backend/bine/quote_engine.py` — Live `/rwa/tokens` 60s cache + deterministic pre-trade guard (`schema_version: "1"`).
- `backend/bine/execution.py` — Transaction API `/simulate` dry-run + `BINE_ADMIN_TOKEN` + `baw` (`npx` fallback) execution.
- `backend/bine/cli.py` — `bine check` and `bine buy` CLI entry point (defaults to `BINE_API_URL=http://localhost:8000`).
- `backend/bine/mcp_server.py` — Stdio MCP server (`bine_check`, `bine_buy`).
- `skills/bine-pre-trade-guard/SKILL.md` — Wallet Skill for Binance Agentic Wallet.
- `frontend/src/lib/humanize.ts` — Plain-English formatter for refusal codes, statuses, depth sources, field keys, and `GUARD_RULE_DEFINITIONS`.
- `frontend/src/components/BineLogo.tsx` — `LiquidMetal` shader logo tile + wordmark lockup with monochrome chrome fallback and frozen `speed={0}` reduced-motion support.
- `frontend/src/components/GlassStack.tsx` — `BineGlassFilterDef`, `GlassDetailPanel`, and `GlassStack` liquid-glass interactive card system.
- `frontend/src/components/HeroArt.tsx` — 2D SVG lavender ring + 3D gold coin with `offset-path` roll and pointer parallax.
- `frontend/src/components/shared.tsx` — `TopHeader` (`80px` nav bar, `LiveModeChip`, route-change `<h1>` focus) and `Footer` (`Connect` social pills).
- `frontend/src/pages/Home.tsx` — `/` 2.5-screen Landing page with interactive glass proof strip and how-it-works cards.
- `frontend/src/pages/Guard.tsx` — `/guard` Interactive Pre-Trade Guard with WAI-ARIA APG combobox, glass metric tiles, and glass guard-rule checks.
- `frontend/src/pages/Refusals.tsx` — `/refusals` 8-rule interactive glass table, 6 recorded refusal glass cards, and one-at-a-time live runner.
- `frontend/src/pages/Receipts.tsx` — `/receipts` verified on-chain receipts with expandable liquid-glass verification details.
- `frontend/src/pages/Integrate.tsx` — `/integrate` WAI-ARIA APG tabbed reference (`HTTP`, `CLI`, `MCP`, `Agent skill`), live `"Try it"` runner, and interactive glass response field table.
- `frontend/src/data/recorded-refusals.json` — Recorded Oct 5 regular-hours and overnight refusal samples.
- `frontend/src/data/onchain-receipts.json` — Verified BNB Chain swap receipts (`Decision #16` and `Decision #18`).

## 11. Environment & Configuration
- **Python**: `3.13.0` virtualenv at `backend/.venv`.
- **Environment variables (`.env` at repo root, never commit)**:
  - `BINANCE_API_KEY`, `BINANCE_SECRET_KEY`
  - `BINE_LIVE_MODE=false`
  - `BINE_ADMIN_TOKEN` (required when `execute_live=true`)
  - `BINE_MAX_TRADE_USD=6.00`
  - `BINE_DAILY_CAP_USD=10.00`
  - `DEV_DNS_FALLBACK=false`

## 12. Development Rules
- **Minimal, decision-driving, plug-and-play**: No dashboards, charts, chat, notifications, or speculative metrics.
- **Never fabricate or interpolate data**: Only verified numbers and errors.
- **Never expose secrets**: API keys stay server-side and never appear in logs or responses.
- **Follow `.agents/skills/bine-ui-standing-rules/SKILL.md`**: Zero displayed underscores outside `[data-raw-code]`, identical monochrome `BineWordmarkLockup` in header and footer aligned at `100px` (`1440px`), `.bine-glass-scrim` contrast layer inside every `.bine-glass-panel`, and real-browser CDP verification before every frontend commit.
