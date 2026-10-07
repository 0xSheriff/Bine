# Bine UI Design Rules & System Guide

## 1. Design Tokens (`frontend/src/index.css`)

### Light Theme (`[data-theme="light"]`, Default on First Visit)
- **Canvas background (`--bg-page` / `--bg`)**: `#F3F3F5`
- **Card surface (`--bg-card` / `--surface`)**: `#FFFFFF`
- **Subtle inset surface (`--surface-subtle`)**: `#F7F7F9`
- **Primary text (`--text`)**: `#0B0B0D` (`17.8:1` contrast on `#FFFFFF`)
- **Secondary text (`--text-secondary`)**: `#5A5B63` (`6.7:1` contrast on `#FFFFFF`, `5.9:1` on `#F3F3F5`)
- **Hairline & border (`--hairline` / `--border`)**: `rgba(11, 11, 13, 0.08)` / `rgba(11, 11, 13, 0.12)`
- **Primary pill (`--pill-primary-bg` / `--pill-primary-text`)**: `#0B0B0D` / `#FFFFFF`
- **Status semantics**:
  - `BUY` / Pass (`--good`, `--chip-good-bg`): `#0D7A43` on `rgba(13, 122, 67, 0.11)`
  - `REFUSE` / Error (`--bad`, `--chip-bad-bg`): `#C5282F` on `rgba(197, 40, 47, 0.11)`
  - Warning (`--warn`, `--chip-warn-bg`): `#A85900` on `rgba(168, 89, 0, 0.12)`

### Dark Theme (`[data-theme="dark"]`)
- **Canvas background (`--bg-page` / `--bg`)**: `#060608`
- **Card surface (`--bg-card` / `--surface`)**: `#101014`
- **Subtle inset surface (`--surface-subtle`)**: `#17171D`
- **Primary text (`--text`)**: `#F5F5F7` (`17.6:1` contrast on `#101014`)
- **Secondary text (`--text-secondary`)**: `#9E9FA8` (`7.3:1` contrast on `#101014`)
- **Primary pill (`--pill-primary-bg` / `--pill-primary-text`)**: `#F5F5F7` / `#060608`
- **Status semantics**:
  - `BUY` / Pass (`--good`, `--chip-good-bg`): `#34D378` on `rgba(52, 211, 120, 0.14)`
  - `REFUSE` / Error (`--bad`, `--chip-bad-bg`): `#FF6B70` on `rgba(255, 107, 112, 0.14)`
  - Warning (`--warn`, `--chip-warn-bg`): `#FBBF24` on `rgba(251, 191, 36, 0.14)`

### Shape & Elevation
- **Card radius (`--card-radius`)**: `24px` (`rounded-2xl` / `16px` for nested panels)
- **Pill radius (`--pill-radius`)**: `9999px`
- **Card shadow (`--card-shadow`)**: `0 1px 2px rgba(11, 11, 13, 0.04), 0 8px 24px rgba(11, 11, 13, 0.03)` in light mode; `1px` subtle border in dark mode.

---

## 2. Typography & Spacing Grid

- **Font family**: Bundled `@fontsource-variable/inter` for UI and prose (zero external font requests); system monospace (`ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`) with `font-variant-numeric: tabular-nums` for all prices, share counts, spreads, addresses, and timestamps.
- **Scale**:
  - Hero `<h1>` (`.bine-hero-headline`): `clamp(40px, 4.6vw, 68px)`, `font-weight: 600`, `line-height: 1.05`, `letter-spacing: -0.035em`, `text-wrap: balance`.
  - Page `<h1>` and section `<h2>` (`.bine-section-heading`): `clamp(28px, 3vw, 38px)`, `font-weight: 600`, `line-height: 1.15`, `letter-spacing: -0.03em`, `text-wrap: balance`.
  - Body prose (`.bine-body-copy`, `.bine-body`): `17px`, `line-height: 1.55`, `text-wrap: pretty`, `max-width: 520px-680px`.
- **Container & column widths**:
  - Outer `.bine-container`: `max-width: 1440px` with responsive horizontal padding (`20px` at `390px`, `40px` at `640px`, `64px` at `1024px`, `100px` at `1280px+`).
  - Inner content column: `max-width: 1120px` centered across `/`, `/guard`, `/refusals`, `/receipts`, and `/integrate`.
  - Landing page vertical budget: `~2.5` screens at `1440x900` (`2.51` measured); no section taller than one viewport.

---

## 3. Core Components & Interaction Patterns

1. **`TopHeader` (`frontend/src/components/shared.tsx`)**:
   - Sticky `80px` header with `BineWordmarkLockup`, 4 route links (`Guard` `/guard`, `Refusals` `/refusals`, `Receipts` `/receipts`, `Developers` `/integrate`), theme toggle button, and primary CTA pill (`"Check a trade"` -> `/guard`).
   - All header controls enforce `min-h-[44px]` (`min-w-[44px]` on icon buttons).
2. **WAI-ARIA APG Combobox (`frontend/src/pages/Guard.tsx`)**:
   - `role="combobox"`, `aria-autocomplete="list"`, `aria-expanded`, `aria-controls`, and `aria-activedescendant`.
   - Supports `ArrowDown`, `ArrowUp`, `Enter` (select highlighted ticker), and `Escape` (close suggestion list).
3. **WAI-ARIA APG Tabs (`frontend/src/pages/Integrate.tsx`)**:
   - `role="tablist"` with `role="tab"` buttons (`HTTP`, `CLI`, `MCP`, `Agent skill`), roving `tabIndex` (`0` on active tab, `-1` on inactive tabs), and `ArrowLeft` / `ArrowRight` / `Home` / `End` keyboard navigation.
4. **Progressive Disclosure (`<details>` / Expandable Cards)**:
   - On `/guard`, the primary verdict card shows the plain-English headline, 5 key metrics (`You receive`, `Price per share`, `Versus market price`, `Price impact`, `Pool depth`), and the `8/8` guard check grid. Raw routing and cross-issuer tables live inside `<details>` disclosures (`Route details` and `Compare issuers`).

---

## 4. Motion & Performance Rules

- **Easing**: `cubic-bezier(0.22, 1, 0.36, 1)` (`--ease-out-expo`) for hover and reveal transitions; spring (`stiffness: 260, damping: 28`) for verdict card transitions.
- **Scroll reveals**: `opacity: 0 -> 1` and `y: 12 -> 0` once per section (`viewport={{ once: true, amount: 0.2 }}`).
- **Reduced motion**: Every animated component checks `usePrefersReducedMotion()` (`(prefers-reduced-motion: reduce)`) and disables motion/parallax/shader animation when enabled.
- **Code splitting**: Route pages (`Guard`, `Refusals`, `Receipts`, `Integrate`) and the `@paper-design/shaders-react` `LiquidMetal` shader are lazy-loaded via `React.lazy` + `Suspense`, keeping the entry JS chunk at `470.93 kB` raw (`< 500 kB` limit).

---

## 5. Copy & Domain Honesty Rules

1. **Zero em dashes**: Never use `—` (`\u2014`) in UI copy, refusal strings, or tooltips. Use commas, periods, colons, or parentheses.
2. **One-sentence refusal reasons**: Every refusal states the exact metric and threshold in plain English, followed by `Not buying.` or a concrete recovery action (e.g., `Try $5.50.`).
3. **Humanized durations & timestamps**:
   - Never print raw minute counts over 60m (such as `1784m ago`). Use `formatSecondsAgo` (`seconds`, `minutes`, `hours`, `days`) and `formatAbsoluteAndRelative` (`"Oct 5, 16:05 WAT, 1 day ago"`).
   - Convert backend `nextOpenTime` strings (`"0d 8h 11m"`) via `_humanize_open_duration()` into `"8 hours 11 minutes"`, and never print `"(regular)"` as a closed session name.
4. **Simulation vs. live router clarity**: Display `REQUIRES_APPROVAL` as `Sim router needs allowance` with the tooltip explaining that the Transaction API dry-run simulates against router `0xB444...` while live swaps through `baw` use router `0xb300...`.

---

## 6. Required State & Accessibility Checklists

### State Checklist
- [x] `idle`: `/guard?idle=1` or after clicking `Clear result`
- [x] `loading`: Skeleton placeholders with `aria-busy="true"` and `aria-live="polite"`
- [x] `BUY`: Plain-English headline, 5 metric tiles, `8/8` passed guard checks, dry-run preview CTA
- [x] `REFUSE`: Tinted red header, refusal code badge, plain-English reason, failed rule highlighted in the 8-check grid, one-click recovery CTA (`Try $5.50` / `Try NVDA at $5.50`)
- [x] `503` API key error: Dedicated card with exact `.env` setup command and `Retry` button
- [x] `network` error: Dedicated card with exact `uvicorn` start command and `Retry` button
- [x] `empty` receipts: Clean empty state on `/receipts?empty=1` with CTA to `/guard`

### Accessibility Checklist
- [x] Every standalone button, link, tab, input, and toggle is `>= 44x44px` (`0` undersized controls across all 30 viewport/theme runs)
- [x] Text contrast `>= 4.5:1` in both light and dark modes
- [x] Navigating to a new route moves focus to the newly mounted page's `<h1>` (`tabIndex={-1}`)
- [x] `aria-live="polite"` announces quote loading, copy confirmations (`Copied`), and live refusal checks
- [x] Zero horizontal overflow (`scrollWidth <= innerWidth`) at `390px`, `768px`, and `1440px`

---

## 7. Mistakes Found During Audit & How to Avoid Them

| Defect ID | Mistake Found in Phase 0 / Phase 5 | How to Avoid It |
|---|---|---|
| `D-01` .. `D-07` | Embedding the full Guard tool below the landing hero created a cramped single page where users had to scroll past the hero to use the tool, and the 3D ring clipped near the header/headline. | Give the landing page (`/`) a dedicated narrative role (`<= 2.5` screens) and give the tool its own route (`/guard`) with a two-column layout. |
| `D-08` .. `D-12` | Showing raw refusal codes without a rule legend or recovery button forced users to guess what thresholds were checked. | Render all 8 guard checks with pass/fail status on every quote and provide a one-click recovery action on `REFUSE`. |
| `D-13` .. `D-15` | Firing 5 parallel `GET /api/quote` requests on `/refusals` mount caused slow loads and mixed live session results with historical refusal examples. | Display verified recorded refusals (`recorded-refusals.json`) immediately on load and provide a one-at-a-time `"Run live now"` comparator button. |
| `D-16` .. `D-18` | Dividing elapsed seconds by `60` without hour/day branches produced `"1784m ago"` and `"4289m ago"`, and hid on-chain fill vs quote diffs. | Always pair absolute dates with human relative units (`hours`/`days`) and show filled vs quoted shares, block number, and BNB gas in expandable receipt rows. |
| `D-19` .. `D-20` | Stacking 5 code blocks with a hand-typed mock schema drifted from the actual API fields. | Use WAI-ARIA APG tabs, a live `"Try it"` button that renders real API output, and a field table derived directly from the 13 frozen contract keys. |
| `D-21` .. `D-23` | Icon buttons (`w-10 h-10` = `40px`) failed the `44px` tap target check, and `focusPageHeading()` ran before `React.lazy` finished mounting the new page's `<h1>`. | Use `min-w-[44px] min-h-[44px]` on all icon buttons, and wait until `document.querySelector('main h1')` differs from the previous page's `<h1>` before calling `.focus()`. |
