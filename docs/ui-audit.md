# Bine Frontend Usability, Visual & Accessibility Audit (`ui-redesign`)

Audited on branch `ui-redesign` (`HEAD be5c09f`) against live servers on `http://localhost:5174` and `http://localhost:8000` across `390px`, `768px`, and `1440px` viewports in both light and dark themes.

---

## 1. Foundational Principles & Primary Sources

| Principle | Source URL | What it means for Bine |
|---|---|---|
| **Nielsen's 10 Usability Heuristics** | https://www.nngroup.com/articles/ten-usability-heuristics/ | Always show system status (live mode vs dry-run, ticking quote age, loading state), speak the user's language (plain English instead of raw API paths or `(regular)` closed-session contradictions), prevent input errors with inline bounds (`$0 < amount <= $2,500`), and offer actionable recovery on refusals and `503`/network errors. |
| **Norman's Gulfs of Execution & Evaluation** | https://www.nngroup.com/articles/two-ux-gulfs-evaluation-execution/ | Close the gulf of execution with an explicit `Check trade` submit button, preset examples (`NVDA $5.50`, `SPYon $250`, `AAPL $2`), and ticker combobox; close the gulf of evaluation with an unmistakable `BUY` or `REFUSE` verdict, 8-rule pass/fail checklist, and side-by-side filled-vs-quoted receipts. |
| **Signifiers & Affordances** | https://www.nngroup.com/articles/affordances-and-signifiers/ | Interactive controls (`Check trade`, `Preview trade (dry-run)`, `Copy as curl`, `Run live now`, expandable receipt rows, and disclosures) must look clickable with clear borders/fills, hover states, and focus rings, while static badges (`BUY`, `REFUSE`, rule pills) must not mimic buttons. |
| **Fitts's Law** | https://www.nngroup.com/articles/fitts-law/ | Keep primary actions (`Check trade`, quick-amount pills, preset chips, `Preview trade`) large (`>= 44px` height) and placed immediately adjacent to the inputs or verdict they act upon, eliminating long pointer travel across dead whitespace. |
| **Hick's Law** | https://www.interaction-design.org/literature/article/hick-s-law-making-the-choice-easier-for-users | Reduce decision time by offering 3 curated trade presets (`NVDA $5.50` buy, `SPYon $250` refusal, `AAPL $2` below minimum), 4 quick USD amounts, and a single primary CTA in the header (`Check a trade` -> `/guard`). |
| **Doherty Threshold (< 400 ms)** | https://lawsofux.com/doherty-threshold/ | Respond to every user interaction within `400 ms` by showing an immediate `Checking issuers` skeleton on quote submission, instant tab switching on `/integrate`, and immediate `Copied` badge feedback (`1.5s`) on clipboard actions. |
| **Progressive Disclosure** | https://www.nngroup.com/articles/progressive-disclosure/ | Show the plain-English verdict, key share/price metrics, and best issuer route up front; tuck raw router addresses (`0xB444...` vs `0xb300...`), contract addresses, and the full multi-issuer comparison table behind `<details>` disclosures (`Route details` and `Compare issuers`). |
| **Recognition over Recall** | https://www.nngroup.com/articles/recognition-and-recall/ | Provide an accessible ticker combobox populated from `/api/tickers` with company names and issuer chips (`bStocks`, `Ondo`), plus an 8-rule legend on `/refusals` so users never have to memorize ticker suffixes (`NVDAB` vs `NVDAon`) or rule codes. |
| **Gestalt Proximity & Similarity** | https://www.nngroup.com/articles/gestalt-proximity/ | Group the hero headline, CTA buttons, and lead paragraph tightly together (`16px-24px` vertical rhythm) instead of pinning the paragraph to the bottom of a `680px` stage; style all 8 guard rules and metric cells with consistent visual structure. |
| **WCAG 2.2 AA (1.4.3, 2.4.7, 2.5.8, 1.4.10)** | https://www.w3.org/TR/WCAG22/ | Maintain `>= 4.5:1` contrast for body/secondary text in light and dark themes, visible `:focus-visible` outlines on every control, minimum `44x44px` touch targets on mobile (`390px`), and zero horizontal overflow (`scrollWidth <= clientWidth`) across `390px`, `768px`, and `1440px`. |
| **WAI-ARIA APG: Tabs & Combobox** | https://www.w3.org/WAI/ARIA/apg/patterns/combobox/ | Implement the `/guard` ticker selector as a WAI-ARIA 1.2 combobox (`role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, `ArrowDown`/`ArrowUp`/`Enter`/`Escape`) and the `/integrate` code switcher as WAI-ARIA tabs (`role="tablist"`, `role="tab"`, `role="tabpanel"`, `ArrowLeft`/`ArrowRight`/`Home`/`End`). |

---

## 2. Screen-by-Screen & State-by-State Browser Defect Log

### Screen A: Landing & Embedded Guard (`/`)
Screenshots inspected: `redesign_home_light_1440.png`, `redesign_home_light_768.png`, `redesign_home_light_390.png`, `redesign_home_dark_1440.png`, `redesign_home_dark_768.png`, `redesign_home_dark_390.png`, `audit_state_buy_nvda_1440.png`, `audit_state_error_503_1440.png`.

| ID | Severity | Defect Observed in Browser | Screenshot | Principle Violated | Fix (Phase) |
|---|---|---|---|---|---|
| **D-01** | High | **Hero headline wraps to 4 lines with orphan `"Guard"`**: At `1440px` (`font-size: 74.88px`, `.hero-top` `max-width: 580px`), `<h1>` breaks as `"Your Pre-Trade" / "Guard" / "for Tokenized" / "Stocks"` (4 lines). | `redesign_home_light_1440.png` | Gestalt Proximity / Visual Hierarchy | Set `font-size: clamp(40px, 4.6vw, 68px)`, `text-wrap: balance`, and widen headline column (`max-width: 680px`) so it renders cleanly in 2 balanced lines at desktop (Phase 3). |
| **D-02** | Medium | **Hero lead paragraph has orphan word `"reason."`**: `.hero-sub` (`max-width: 470px`, `16px`) wraps its final line to a single word `"reason."` (or two words `"one reason."`). | `redesign_home_light_1440.png` | Readability / Typography (`text-wrap: pretty`) | Place paragraph directly below hero buttons at `17px`, `max-width: 520px`, `text-wrap: pretty`, with balanced phrasing (Phase 3). |
| **D-03** | High | **Dead vertical gap (`~210px`) between hero buttons and paragraph**: `.hero-stage` uses `justify-content: space-between` with `min-height: 680px`, pushing `.hero-sub` to the bottom far away from `.hero-actions`. | `redesign_home_light_1440.png` | Gestalt Proximity | Stack headline, CTA buttons, and lead paragraph in a single cohesive flex column with `20px-24px` spacing inside `min(88vh, 760px)` (Phase 3). |
| **D-04** | High | **Hero 3D ring clipped with a hard bottom edge into the Guard section**: `.hero-art-wrap` (`width: 900px`, `height: 660px`, `bottom: -40px`) overflows `.hero-stage` (`overflow: hidden`), slicing the bottom rim of the ring with a flat horizontal cut. | `redesign_home_light_1440.png`, `redesign_home_dark_1440.png` | Signifiers / Visual Craft | Scale and position `HeroArt` inside the stage bounds so the entire lower rim and soft drop shadow clear both the top nav and bottom edge without clipping (Phase 3). |
| **D-05** | High | **Landing page mixes marketing hero with the full interactive tool**: `/` embeds the Guard inputs directly below the hero and lacks a dedicated `/guard` route, proof strip, how-it-works overview, refusal preview, or verified swap highlight. | `redesign_home_light_1440.png` | Progressive Disclosure / Hick's Law | Split `/guard` into its own dedicated route (`Phase 1 & 2`) and structure `/` as a focused 2.5-screen landing page with live proof strip, 3-step overview, recorded refusal card, and verified swap card (`Phase 3`). |
| **D-06** | High | **Guard form lacks an explicit submit button, combobox, and example presets**: Users only see two bare inputs (`Stock ticker`, `Amount (USD)`) with a hidden 280ms debounce. No ticker suggestions, no quick amounts, no preset buttons, and no idle state. | `audit_state_buy_nvda_1440.png` | Norman's Gulf of Execution / Recognition over Recall | Build left panel on `/guard` with WAI-ARIA APG ticker combobox (`/api/tickers`), `$` amount input, quick amounts, 3 example presets (`NVDA $5.50`, `SPYon $250`, `AAPL $2`), and primary `Check trade` submit button (`Phase 2`). |
| **D-07** | High | **Guard result copy is jargon-heavy and exposes raw endpoint paths in primary view**: Displays `Indicative quote from /dex/aggregator/quote; live Agentic Wallet execution routes Ondo tokens via /ondo/place-order.` directly under the headline. | `audit_state_buy_nvda_1440.png` | Nielsen's Match Between System & Real World / Progressive Disclosure | Show plain-English verdict, 5 clear metrics (`You receive`, `Price per share`, `Versus market price`, `Price impact`, `Pool depth`), `Best route` line, and `Guard checks` pass/fail list; move endpoint/router details into a `Route details` disclosure (`Phase 2`). |
| **D-08** | Medium | **Static quote age text (`"Quoted 34s ago."`)**: `formatAge(response.timestamp)` computes once when rendered and never ticks live or warns when stale (`> 60s`). | `redesign_home_light_1440.png` | Nielsen's Visibility of System Status | Add a 1-second timer hook on `/guard` that ticks `"Quoted 12s ago"` live and transitions to `"Quote expired, refresh"` with a refresh button after `60s` (`Phase 2`). |
| **D-09** | High | **`503` and network failure states lack actionable recovery**: On `503` or network error, only a single red text banner appears without backend setup commands or a retry button. | `audit_state_error_503_1440.png` | Nielsen's Help Users Recognize, Diagnose, and Recover from Errors | Render a structured `503` setup card with the README start commands and a network-failure card with `"Check that the backend is running on port 8000"` and a `Retry` button (`Phase 2`). |
| **D-10** | Medium | **Static `"Live trading is off on this server."` string**: Hardcoded sentence ignores `/api/health` (`live_mode`, `max_trade_usd`, `daily_cap_usd`) and gives no explanation of how CLI Agentic Wallet swaps and caps work. | `audit_state_buy_nvda_1440.png` | Nielsen's Visibility of System Status | Replace with `LiveModeChip` wired to `/api/health` with an accessible info popover explaining the `$6` per-trade and `$10` daily CLI caps (`Phase 1`). |
| **D-11** | High | **`market_closed` backend message prints contradictory `"non-trading session (regular)"` and raw `"0d 0h 0m"`**: When Ondo rejects with `[40367]`/`[40369]` during its `20:00-20:03 UTC` pause while `market_status` is `"regular"`, `quote_engine.py` outputs `"is in a non-trading session (regular). Expected to open in 0d 0h 0m."` | `redesign_refusals_light_1440.png` | Nielsen's Match Between System & Real World | Fix `quote_engine.py` Rule 3 so `"regular"` is never printed as a closed session (`"{symbol} is not accepting orders right now. Expected to reopen in about {humanized_duration}."`) and humanize `"Xd Yh Zm"` durations (`"less than a minute"`, `"8 hours 11 minutes"`) (`Phase 2`). |

---

### Screen B: Refusals (`/refusals`)
Screenshots inspected: `redesign_refusals_light_1440.png`, `redesign_refusals_light_768.png`, `redesign_refusals_light_390.png`, `redesign_refusals_dark_1440.png`, `redesign_refusals_dark_768.png`, `redesign_refusals_dark_390.png`.

| ID | Severity | Defect Observed in Browser | Screenshot | Principle Violated | Fix (Phase) |
|---|---|---|---|---|---|
| **D-12** | High | **Static card labels mismatch live refusal codes during Ondo pauses or off-hours**: Cards hardcode titles like `"SPYon at $250.00, Thin PMM/DEX pool cliff"` or `"Share ratio outside 0.25-5.00x"`, but fetch live `/api/quote` on mount. During `20:00-20:03 UTC` (Ondo transition pause) or off-hours, the live badge says `market_closed` while the card title claims it is a share-ratio or pool-cliff refusal. | `redesign_refusals_light_1440.png` | Nielsen's Consistency & Standards / Gulf of Evaluation | Separate recorded evidence from live checks: render recorded refusal cards from `recorded-refusals.json` (built from `docs/raw/` & `docs/*.json` with exact UTC timestamp and session), and add a single-request `"Run live now"` button per card that displays the live result beside the recorded one (`Phase 4`). |
| **D-13** | High | **Fires 5 live `/api/quote` requests in parallel on page load**: Every visit to `/refusals` leaves all 5 cards stuck in `"loading / Querying live API..."` for several seconds while hammering upstream APIs. | `redesign_refusals_light_1440.png` | Doherty Threshold (< 400 ms) | Render recorded evidence cards immediately (`0 ms` wait) and only call `/api/quote` one request at a time when the user clicks `"Run live now"` (`Phase 4`). |
| **D-14** | Medium | **Missing 8-rule guard legend and live session banner**: Users only see 5 example cards with no explanation of all 8 guard rules (`amount_over_cap`, `below_issuer_minimum`, `market_closed`, `reference_stale`, `depth_thin`, `slippage_too_high`, `quality_unreliable`, `unknown_ticker`) or their thresholds. | `redesign_refusals_light_1440.png` | Recognition over Recall | Add an 8-rule legend table/grid with plain names, what each protects, and exact backend thresholds, plus a live session status banner (`Phase 4`). |
| **D-15** | Medium | **Page title `"Live Refusals"` is styled at `16px` (`font-size: 16px` kicker) instead of a proper page heading**: `h1FontSize` measured in CDP is `16px`. | `redesign_refusals_light_1440.png` | Visual Hierarchy / WCAG 2.4.6 Headings and Labels | Style `<h1>Why Bine says no</h1>` with proper page display typography (`clamp(28px, 3.2vw, 40px)`, `font-weight: 600`, `letter-spacing: -0.03em`) (`Phase 4`). |

---

### Screen C: Receipts (`/receipts`)
Screenshots inspected: `redesign_receipts_light_1440.png`, `redesign_receipts_light_768.png`, `redesign_receipts_light_390.png`, `redesign_receipts_dark_1440.png`, `redesign_receipts_dark_768.png`, `redesign_receipts_dark_390.png`, `audit_state_empty_receipts_1440.png`.

| ID | Severity | Defect Observed in Browser | Screenshot | Principle Violated | Fix (Phase) |
|---|---|---|---|---|---|
| **D-16** | High | **Timestamps display raw minutes (`"Decision #18 · 1784m ago"` and `"Decision #16 · 4289m ago"`)**: Relative time helper divides by `60` and prints `m ago` forever instead of human hours/days alongside the absolute timestamp. | `redesign_receipts_light_1440.png` | Nielsen's Match Between System & Real World | Format timestamps with both absolute date/time and human relative age, e.g., `"Oct 5, 16:05 WAT, 1 day ago"` and `"Oct 3, 22:20 WAT, 3 days ago"` (`Phase 4`). |
| **D-17** | High | **Receipts omit fill details, block numbers, gas in BNB, order IDs, and preceding dry-run links**: Each row only shows `NVDA $2.00 (NVDAB)` and a BscTrace button, hiding shares filled vs quoted (`+7.2 bps` / `-0.13 bps`), all-in price, order ID, block (`125889084` / `125555002`), gas (`0.00003293 BNB` / `0.00005091 BNB`), and `"Dry-run #17, then executed #18"`. | `redesign_receipts_light_1440.png` | Norman's Gulf of Evaluation / Progressive Disclosure | Add a summary strip (swaps count, total USD spent, total BNB gas) and expandable receipt rows containing all verified on-chain metrics from `docs/live_swap_nvda_2usd*.json` and `docs/raw/tx_history_second_swap_2026-10-05.json` (`Phase 4`). |
| **D-18** | Medium | **Page title `"Executed Trade Receipts"` is `16px` instead of a page heading**: Measured `h1FontSize: 16px` in CDP. | `redesign_receipts_light_1440.png` | Visual Hierarchy | Use `<h1>On-chain receipts</h1>` with proper page heading typography (`Phase 4`). |

---

### Screen D: Developers (`/integrate`)
Screenshots inspected: `redesign_integrate_light_1440.png`, `redesign_integrate_light_768.png`, `redesign_integrate_light_390.png`, `redesign_integrate_dark_1440.png`, `redesign_integrate_dark_768.png`, `redesign_integrate_dark_390.png`.

| ID | Severity | Defect Observed in Browser | Screenshot | Principle Violated | Fix (Phase) |
|---|---|---|---|---|---|
| **D-19** | High | **5 stacked code blocks require scrolling and show a stale mock schema**: Card #5 (`Frozen Response Schema`) lists fictitious fields (`verdict`, `all_in_price_per_share`, `refusal.code`) that do not match `QuoteResponseModel` in `backend/bine/app.py` (`action`, `refusal_code`, `selected`, `alternatives`, `guard_parameters`, `quality_notes`, `decision_id`, `live_mode`). | `redesign_integrate_light_1440.png` | Nielsen's Accuracy / Progressive Disclosure | Replace stacked blocks with WAI-ARIA APG tabs (`HTTP`, `CLI`, `MCP`, `Agent skill`), add a live `"Try it"` button on `HTTP`, and add an accurate 13-field `Response fields` table and `Errors` table (`401/403`, `429`, `503`) (`Phase 4`). |
| **D-20** | Medium | **Page title `"Integrate Bine"` is `16px` and nav label says `"Integrate"`**: Measured `h1FontSize: 16px` in CDP. | `redesign_integrate_light_1440.png` | Visual Hierarchy / Clarity | Change nav label to `"Developers"`, set `<h1>Use Bine from your agent</h1>` with heading typography, and add a two-sentence plain intro (`Phase 1 & 4`). |

---

### Cross-Cutting Accessibility, Theme & Performance Defects

| ID | Severity | Defect Observed in Browser | Screenshot | Principle Violated | Fix (Phase) |
|---|---|---|---|---|---|
| **D-21** | High | **Interactive tap targets under `44x44px` on mobile (`390px`)**: CDP measured top nav links at `41x29px`–`68x29px`, logo at `88x36px`, theme toggle at `40x40px`, and header CTA at `141x40px`. | `redesign_home_light_390.png` | WCAG 2.2 AA 2.5.8 Target Size / Mobile Usability | Ensure all interactive buttons, links, tabs, and pills have `min-height: 44px` (and `min-width: 44px` for icon buttons) (`Phase 1–5`). |
| **D-22** | Medium | **Theme flash risk & no route focus management**: Theme is initialized inside React `useState` rather than a blocking `<head>` script, and navigating between routes leaves focus on the clicked nav link (`first_tab_focus: BODY:`) instead of moving focus to the new page's `<h1>`. | `audit_state_keyboard_focus_1440.png` | WCAG 2.4.3 Focus Order / Dark Mode Best Practices | Add an inline `try/catch` theme bootstrap script in `frontend/index.html` defaulting to `'light'` before first paint, and focus `<h1>` (`tabIndex={-1}`) on route change (`Phase 1`). |
| **D-23** | Medium | **Main JS bundle exceeds `500 kB` raw (`520.23 kB`)**: `LiquidMetal` shader (`@paper-design/shaders-react`) and all route pages are eagerly bundled into the entry chunk. | Build output | Load Performance (LCP / TTI) | Lazy-load route pages (`React.lazy` + `Suspense`) and lazy-load `LiquidMetal` inside `BineLogo.tsx` so the main chunk is well under `500 kB` raw (`Phase 1`). |

---

## 3. Phase 5 Post-Refinement Browser Pass (All 5 Screens, 3 Viewports, 2 Themes, Interactive States)

### 3.1 Automated Browser & Performance Checks (`phase5_browser_pass.py` + `verify_focus_and_perf.py`)
- **Matrix coverage**: 30 viewport/theme runs (`landing` `/`, `guard` `/guard`, `refusals` `/refusals`, `receipts` `/receipts`, `developers` `/integrate` across `390px`, `768px`, and `1440px` in `light` and `dark`) plus interactive states (`idle`, `loading`, `BUY NVDA $5.50`, `REFUSE SPYon $250`, `below_issuer_minimum AAPL $2`, `503` error, network error, empty receipts `?empty=1`, keyboard tab navigation, and `prefers-reduced-motion: reduce`).
- **Cold default theme**: `light` even when OS `prefers-color-scheme: dark` is emulated (`cold_default_theme: "light"`).
- **Horizontal overflow (`scrollWidth <= innerWidth`)**: `0` failures across all 30 runs (`overflow_failures: []`).
- **Interactive tap target height (`>= 44px`)**: `0` failures across all 30 runs (`undersized_failures: []`, after increasing the combobox toggle button in `Guard.tsx` from `40x40px` to `44x44px`).
- **Route change focus management**: Clicking `/guard` focuses `<h1>Pre-Trade Guard</h1>` (`active_on_guard: { tag: "H1", text: "Pre-Trade Guard" }`); clicking `/refusals` focuses `<h1>Why Bine says no</h1>` (`active_on_refusals: { tag: "H1", text: "Why Bine says no" }`).
- **Keyboard navigation**: WAI-ARIA APG combobox (`ArrowDown`, `ArrowUp`, `Enter`, `Escape`) on `/guard` and WAI-ARIA APG tabs (`ArrowRight` moves focus from `#tab-http` to `#tab-cli`, `tab_kb_test: "tab-cli"`) on `/integrate`.
- **Paint & load timings (headless Chrome 154 on `1440x900`)**:
  - `/` (`Home`): `first-paint: 344 ms`, `first-contentful-paint: 500 ms`, `domInteractive: 66 ms`, `loadEventEnd: 336 ms`; total page height `2.51` screens at `1440px`.
  - `/guard` (`Guard`): `first-paint: 92 ms`, `first-contentful-paint: 440 ms`, `domInteractive: 15 ms`, `loadEventEnd: 48 ms`.
- **Console errors / uncaught exceptions**: `0` (`console_errors: []`).
- **External network hosts**: `0` (`external_hosts: []`).

### 3.2 Screen-by-Screen Post-Refinement Scores (`0-10`)

#### 1. Landing (`/`)
- **Screenshots**: `p5_landing_light_1440.png`, `p5_landing_dark_1440.png`, `p5_landing_light_768.png`, `p5_landing_light_390.png`
- **Scores**: Usability `9/10` | Simplicity `9/10` | Aesthetics `9/10` | Layout `9/10`
- **Justification for scores > 8**: Total desktop height is `2.51` screens (`2259px` at `1440x900`), the hero headline sits cleanly in 2 balanced lines with generous separation from the 3D lavender ring and gold coin, the primary and secondary pills sit directly below the headline followed by the `520px` body copy, and the proof strip links live counts (`448` tokens, `8` rules, `2` verified swaps) directly to `/guard`, `/refusals`, and `/receipts`.
- **5 Worst Remaining Defects / Tradeoffs**:
  1. On `390px` mobile, the stacked 3D ring SVG adds ~`210px` of vertical height between the intro paragraph and the proof strip.
  2. The proof strip shows `448` catalog tickers only after `/api/tickers` resolves (initial render shows `448` fallback, which matches the current catalog size).
  3. The featured refusal card on `/` shows one representative case (`SPYon $250`); users must click through to `/refusals` to compare all 6 recorded refusals.
  4. The `LiquidMetal` header tile relies on WebGL and falls back to a static metallic gradient when WebGL or `prefers-reduced-motion` is active.
  5. BscTrace links open in a new tab (`target="_blank"`), requiring an external block explorer to inspect raw logs.

#### 2. Guard (`/guard`)
- **Screenshots**: `p5_guard_light_1440.png`, `p5_state_guard_buy_1440.png`, `p5_state_guard_refuse_spyon_1440.png`, `p5_state_guard_below_min_1440.png`, `p5_guard_light_390.png`
- **Scores**: Usability `9/10` | Simplicity `9/10` | Aesthetics `9/10` | Layout `9/10`
- **Justification for scores > 8**: Dedicated two-column workspace (`max-width: 1120px`) with WAI-ARIA APG combobox (`448` searchable tickers with issuer badges), quick amount chips (`$2`, `$5.50`, `$25`, `$250`), inline validation (`> $0` and `<= $2,500`), 3 one-click presets, 5 plain-English metrics on `BUY`, all `8/8` guard checks shown with pass/fail badges, progressive disclosure for `Route details` and `Compare issuers`, and recovery CTA on `REFUSE`.
- **5 Worst Remaining Defects / Tradeoffs**:
  1. At `768px` tablet width, the 5-metric grid wraps into 3+2 cards rather than a single 5-column row.
  2. The `Compare issuers` table requires horizontal scrolling inside its card container on `390px` viewports due to 7 data columns.
  3. Live quote evaluation takes ~`0.9s-1.3s` when the backend fetches fresh `/aggregator/quote` and `/top-liquidity` data from Binance Web3 APIs.
  4. The combobox filters up to 8 visible suggestions at a time (`slice(0, 8)`) to keep the dropdown compact, so broad queries require typing 2+ characters.
  5. Dry-run simulation against router `0xB444...` reports `Sim router needs allowance` even when the `baw` router (`0xb300...`) already has `uint256.max` allowance (explained via tooltip and README).

#### 3. Refusals (`/refusals`)
- **Screenshots**: `p5_refusals_light_1440.png`, `p5_state_refusals_live_run_1440.png`, `p5_refusals_dark_1440.png`, `p5_refusals_light_390.png`
- **Scores**: Usability `9/10` | Simplicity `9/10` | Aesthetics `9/10` | Layout `9/10`
- **Justification for scores > 8**: Combines the complete 8-rule specification table (rule name, code, protection purpose, threshold) with 6 recorded refusal cards from `recorded-refusals.json` and a one-request-at-a-time `"Run live now"` comparator that displays the live verdict and market session right beside the recorded Oct 5 evidence without firing 5 parallel API calls on page load.
- **5 Worst Remaining Defects / Tradeoffs**:
  1. On `390px` mobile, the 4-column rule legend table scrolls horizontally inside its card wrapper.
  2. Running a live check on a recorded refusal during a different market session (e.g., `overnight` vs `regular`) can return a different refusal code or a `BUY` verdict, which requires reading the session badge in the comparison box.
  3. Only one `"Run live now"` request can run at a time (`disabled={Boolean(runningId)}`), so checking all 6 cards sequentially takes 6 clicks.
  4. The live session banner uses `NVDA` `$5.50` as its reference probe (`quote-session-banner`).
  5. Recorded refusal timestamps are shown in `UTC` (`Recorded Oct 5, 15:04 UTC (regular session)`) to match the raw JSONL logs.

#### 4. Receipts (`/receipts`)
- **Screenshots**: `p5_receipts_light_1440.png`, `p5_state_receipts_empty_1440.png`, `p5_receipts_dark_1440.png`, `p5_receipts_light_390.png`
- **Scores**: Usability `9/10` | Simplicity `9/10` | Aesthetics `9/10` | Layout `9/10`
- **Justification for scores > 8**: Displays computed summary totals (`2` verified swaps, `$4.00` total USDT spent, `0.00008384 BNB` total gas) above expandable receipt cards with both absolute and human-relative timestamps (`Oct 5, 16:05 WAT, 1 day ago`), filled vs quoted shares (`-0.53 bps` and `-0.13 bps`), block numbers (`125889084` and `125555002`), BNB gas fees, one-click `Copy tx hash` with `aria-live` feedback, and preceding dry-run sequence notes.
- **5 Worst Remaining Defects / Tradeoffs**:
  1. Only `Decision #18` is expanded by default on initial load; `Decision #16` requires clicking `Show details` to inspect its `approve_tx_hash` and block number.
  2. Long 66-character hexadecimal transaction hashes wrap onto two lines on `390px` screens (`break-all`).
  3. USD value of BNB gas (`~$0.04`) is not shown next to the raw BNB amount (`0.00008384 BNB`) because historical BNB/USD spot price at the block timestamp is not stored in `decision_log`.
  4. If a new live swap is executed without updating `onchain-receipts.json`, `block_number` and `gas_bnb` fall back to `N/A` until reconciled from RPC.
  5. Dry-run-only decisions (`DRY_RUN_OK`) are excluded from `/receipts` by design and only appear in the Guard page's recent decisions disclosure.

#### 5. Developers (`/integrate`)
- **Screenshots**: `p5_developers_light_1440.png`, `p5_developers_dark_1440.png`, `p5_developers_light_768.png`, `p5_developers_light_390.png`
- **Scores**: Usability `9/10` | Simplicity `9/10` | Aesthetics `9/10` | Layout `9/10`
- **Justification for scores > 8**: Replaces 5 long stacked code blocks with WAI-ARIA APG keyboard-navigable tabs (`HTTP`, `CLI`, `MCP`, `Agent skill`), includes an interactive `"Try it"` button on the `HTTP` tab that executes a live `GET /api/quote?ticker=NVDA&amount_usd=5.50` call and renders the real JSON payload inline, and documents all 13 frozen `schema_version: "1"` response fields plus the `401/403`, `429`, and `503` error contracts.
- **5 Worst Remaining Defects / Tradeoffs**:
  1. The live `"Try it"` button is only available on the `HTTP` tab (since `CLI`, `MCP`, and `Agent skill` run in the user's terminal or MCP client).
  2. The live JSON response preview caps height at `max-h-[340px]` with internal scroll to avoid pushing the response fields table off-screen.
  3. On `390px` mobile, the `Response fields` and `Errors` tables require horizontal scrolling inside their card containers.
  4. Code blocks use `http://localhost:8000` as the default `BINE_API_URL` rather than dynamically substituting a remote host.
  5. Syntax highlighting is intentionally omitted in `<pre><code>` blocks to keep bundle weight zero-dependency and high-contrast in both themes.

---

## 4. Phase C Liquid Glass Interactive Stack & Performance Trace

### 4.1 Liquid Glass Architecture (`frontend/src/components/GlassStack.tsx` + `frontend/src/index.css`)
- **Two-Layer Readability Architecture**:
  - **Outer Glass Frame (`.bine-glass-panel`)**: Translucent specular glass (`backdrop-filter: blur(22px) saturate(165%)`), progressive `@supports (backdrop-filter: url(#bine-glass))` Chromium SVG `<feTurbulence>` + `<feDisplacementMap>` edge refraction (`scale="6"`), top specular rim (`inset 0 1px 0`), inner rim (`inset 0 0 0 1px`), and radial cursor specular highlight (`--mx`, `--my` updated via `requestAnimationFrame`).
  - **Inner Readability Scrim (`.bine-glass-scrim`)**: High-contrast surface (`rgba(255, 255, 255, 0.78)` in Light mode, `rgba(14, 16, 22, 0.80)` in Dark mode) behind all text, numbers, badges, and tables so text never sits directly on raw blurred background.
- **Interactive Stack Behavior (`GlassStack`)**:
  - One active card per stack (`aria-expanded`, `aria-controls`, `role="region"`), sibling recession (`opacity: 0.58; transform: scale(0.985)` on desktop/tablet), `Escape` and `Close` button dismissal returning focus to the triggering card, `document.startViewTransition` progressive enhancement, and `390px` mobile inline sheet expansion (`max-height: 78vh; overflow-y: auto`) without sibling scale transforms.
- **Interactive Coverage Across All 5 Routes**:
  1. `/` (`Home.tsx`): Proof strip cards (`448` tokens, `8` guard rules, `2` on-chain swaps) and `How Bine works` 3-step cards.
  2. `/guard` (`Guard.tsx`): 5-metric grid tiles (`You receive`, `Price per share`, `Versus market price`, `Price impact`, `Pool depth`) and 8 Guard check pills.
  3. `/refusals` (`Refusals.tsx`): 8-rule legend rows and 6 recorded empirical refusal cards.
  4. `/receipts` (`Receipts.tsx`): Expandable on-chain receipt cards (`Decision #18` and `Decision #16`).
  5. `/integrate` (`Integrate.tsx`): 13 `schema_version: "1"` response field rows with `[data-raw-code]` sample JSON.

### 4.2 Before vs. After Load & Click Performance (`scripts/verify_glass_and_perf.py`)

| Route | Metric | Phase 5 Baseline | Phase C (Liquid Glass) | Status |
|---|---|---|---|---|
| `/` (`Home`) | `first-paint` | `344 ms` | `324 ms` | Pass |
| `/` (`Home`) | `first-contentful-paint` | `500 ms` | `596 ms` | Pass (`< 1.0s`) |
| `/` (`Home`) | `domInteractive` | `66 ms` | `35 ms` | Pass |
| `/` (`Home`) | `loadEventEnd` | `336 ms` | `322 ms` | Pass |
| `/` (`Home`) | Click handler (`GlassStack` open) | N/A | `0.7 ms` (`0` long tasks `> 50 ms`) | Pass (`60 fps`) |
| `/guard` (`?ticker=NVDA&amount=5.5`) | `first-paint` | `92 ms` | `104 ms` | Pass |
| `/guard` (`?ticker=NVDA&amount=5.5`) | `first-contentful-paint` | `440 ms` | `480 ms` | Pass (`< 1.0s`) |
| `/guard` (`?ticker=NVDA&amount=5.5`) | `domInteractive` | `15 ms` | `19 ms` | Pass |
| `/guard` (`?ticker=NVDA&amount=5.5`) | `loadEventEnd` | `48 ms` | `53 ms` | Pass |
| `/guard` (`?ticker=NVDA&amount=5.5`) | Click handler (`GlassStack` open) | N/A | `0.4 ms` (`0` long tasks `> 50 ms`) | Pass (`60 fps`) |

### 4.3 Contrast, Overflow & Bundle Verification
- **WCAG 2.2 AA Contrast inside `.bine-glass-scrim`**:
  - Light mode: `rgb(10, 10, 10)` on `rgba(255, 255, 255, 0.78)` (`> 15:1`, pass `>= 4.5:1`).
  - Dark mode: `rgb(245, 245, 245)` on `rgba(14, 16, 22, 0.80)` (`> 14:1`, pass `>= 4.5:1`).
- **Horizontal Overflow (`scrollWidth <= innerWidth`)**: `0` failures across all 30 `glass_<page>_<theme>_<width>.png` screenshots (`390px`, `768px`, `1440px` in light and dark).
- **Displayed Underscores (`scripts/check_underscores.py`)**: `TOTAL_UNDERSCORE_OFFENDERS=0` across all 16 route/state/theme combinations.
- **Main JS Bundle Size**: `485.90 kB` raw (`< 500 kB` guardrail).
