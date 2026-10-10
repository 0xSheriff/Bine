---
name: bine-ui-standing-rules
description: >-
  Enforces the 7 standing Bine frontend UI and media rules across all routes and components:
  (1) zero displayed underscores outside [data-raw-code], (2) consistent BineLogoTile
  rendering and exact left-edge alignment across nav and footer, (3) readable liquid-glass
  cards with inner contrast plates and one-card-per-stack interaction, (4) derive counts
  from data, never hard-code them, (5) mandatory real-browser CDP inspection and
  verification before committing frontend changes, (6) distinguish issuer minimums from
  safety caps, and (7) real captured states and provenance binding for media and demos.
---

# Bine Frontend Standing Rules (`bine-ui-standing-rules`)

## Overview
Activate this skill whenever creating, editing, or auditing frontend code (`frontend/src/`) or UI documentation in Bine. These 7 standing rules prevent regressions in copy clarity, brand consistency, glass readability, data-driven counts, browser verification, cap terminology, and demo ground truth.

## Standing Rules

### 1. Never Render Raw Identifier Underscores in UI Copy
- **Rule**: No underscore character (`_`) may appear in any visible text, `aria-label`, `title`, tooltip, `placeholder`, `alt` text, or `document.title` outside raw code/command blocks (`<pre>`, `<code>`, or `[data-raw-code]`).
- **Implementation**:
  - Route all refusal codes (`slippage_too_high`, `below_issuer_minimum`, `quality_unreliable`, etc.), execution statuses (`LIVE_SUBMITTED`, `DRY_RUN_OK`, `REQUIRES_APPROVAL`), depth sources (`amm_pools`, `catalog_volume_24h`), and response schema field names through `frontend/src/lib/humanize.ts` (`humanizeRuleCode`, `humanizeStatus`, `humanizeDepthSource`, `humanizeFieldKey`, `humanizeCode`).
  - Wrap genuine CLI flags, JSON payloads, or MCP tool names (`bine_check`, `bine_buy`) in `<code data-raw-code>` or `<pre data-raw-code>`.
- **Automated Check**:
  - Run `backend/.venv/bin/python scripts/check_underscores.py` and verify `TOTAL_UNDERSCORE_OFFENDERS=0` (with `glass_open=True` on every interactive route/state including `guard_refuse` and `guard_below_min`).

### 2. Identical Logo Component & Left-Edge Container Alignment
- **Rule**: The header brand lockup, footer brand lockup, and favicon must share one monochrome silver/chrome visual identity (`colorTint="#ffffff"` on `#000000`), and the nav and footer logo tiles must align to the exact same `x` coordinate at `1440px` across every route (`0px` drift).
- **Implementation**:
  - Always use `<BineWordmarkLockup tileSize={36} />` from `frontend/src/components/BineLogo.tsx` in both `TopHeader` and `Footer`.
  - Under `prefers-reduced-motion: reduce`, keep `LiquidMetal` mounted at `speed={0}` (frozen shader frame) rather than swapping to a differently colored static gradient.
  - Inside `.bine-container`, use a unified `max-w-[1240px] mx-auto` wrapper across `TopHeader`, `Footer`, and all 5 route pages (`Home.tsx`, `Guard.tsx`, `Refusals.tsx`, `Receipts.tsx`, `Integrate.tsx`).
- **Automated Check**:
  - Run `backend/.venv/bin/python scripts/verify_logo_and_alignment.py` and verify `UNIQUE_LOGO_X_COORDS_AT_1440=[100]` (`0px` drift) and nav-vs-footer logo pixel diff `<= 2/255`.

### 3. Liquid Glass Outer Frame (~0.50 Tint) & Inner Contrast Plate (<= 0.85 Alpha, >= 4.5:1 WCAG)
- **Rule**: Tint the outer `.bine-glass-panel` at roughly `0.50` so blur and refraction remain visible, and place all text inside an inner contrast plate (`.bine-glass-scrim`, `<= 0.85` alpha) that maintains `>= 4.5:1` WCAG 2.2 AA contrast in both Light and Dark themes. Mount `<BineGlassFilterDef />` only while a glass panel is open.
- **Implementation**:
  - Use `GlassStack` and `GlassDetailPanel` (`frontend/src/components/GlassStack.tsx`) for interactive card groups.
  - Keep at most one card open per stack (`aria-expanded`, `aria-controls`, `role="region"`), support `Escape` and `Close` button dismissal returning focus to the trigger, recede unselected siblings subtly on desktop/tablet (`opacity: 0.58; transform: scale(0.985)`), and expand inline on `390px` mobile without sibling scale transforms.

### 4. Derive Counts From Data, Never Hard-Code Them
- **Rule**: Derive every rule count, recorded refusal count, token count, or receipt count directly from the underlying dictionary or data array (`GUARD_RULES_COUNT = Object.keys(GUARD_RULE_DEFINITIONS).length`, `recordedRefusals.length`, `tokenCount`, `receipts.length`) rather than hard-coding literal integers like `"8 rules"` or `"6 recorded refusals"` in JSX copy.
- **Implementation**:
  - Keep `REFUSAL_CODE_LABELS` and `GUARD_RULE_DEFINITIONS` in `frontend/src/lib/humanize.ts` in 1-to-1 sync with the backend refusal codes and threshold constants in `backend/bine/quote_engine.py` and `backend/bine/quality.py`.
- **Automated Check**:
  - Run `backend/.venv/bin/python scripts/verify_rules_truth_table.py` and verify `MISMATCH_ROWS=0` and `Hard-coded rule/refusal count strings in frontend/src: 0`.

### 5. Real-Browser CDP Verification Before Every Frontend Commit
- **Rule**: Reading source code does not count as a UI audit. Every frontend change must be inspected in a real headless Chrome session via CDP across `390px`, `768px`, and `1440px` in both Light and Dark modes before committing.
- **Anti-Rigging & Evidence Rules**:
  - Never default a UI to open just to satisfy a test.
  - Never report a check as verified unless the script computes it.
- **Verification Checklist**:
  1. `backend/.venv/bin/python scripts/verify_rules_truth_table.py` -> `MISMATCH_ROWS=0`, `0` hard-coded rule/refusal counts
  2. `backend/.venv/bin/python scripts/check_underscores.py` -> `TOTAL_UNDERSCORE_OFFENDERS=0` (`glass_open=True` across all interactive states)
  3. `backend/.venv/bin/python scripts/verify_logo_and_alignment.py` -> `0px` logo `x` drift and identical nav/footer tile rendering
  4. `backend/.venv/bin/python scripts/verify_glass_and_perf.py` -> `OVERFLOW_FAILURES=0`, `CONTRAST_FAILURES=0`, `initial_panel_open: false`, `glass_panel_opened: true`, `0` long tasks `> 50 ms`, and 30 `glass_<page>_<theme>_<width>.png` screenshots captured from real clicks and visually inspected
  5. `grep -rn "—" frontend/src/` -> `0` matches
  6. `npm --prefix frontend run build` -> main JS chunk `<= 480 kB` raw

### 6. Distinguish Issuer Minimums from Safety Caps
- **Rule**: Never refer to a safety ceiling or trade cap as a "minimum". Upstream issuer floors ($5.00 Ondo minimum [40375]; $0.01 bStocks tie-break floor) are minimums. BINE safety caps ($6.00 single-trade cap `BINE_MAX_TRADE_USD`, $10.00 daily cap `BINE_DAILY_CAP_USD`, $2,500.00 single-quote cap) are caps.
- **Implementation**:
  - In user-facing UI, documentation, and video copy, use "live trade cap" or "safety cap" for $6.00 / $10.00 / $2,500.00.
  - Reserve "minimum order" exclusively for issuer order rejection thresholds.

### 7. Real Captured States & Provenance Binding for Media/Demos
- **Rule**: When creating demo videos, screenshots, or visual assets for BINE, never construct synthetic HTML result boxes with placeholder figures. Always capture and embed real product states recorded from the live/hosted application after verified fixes.
- **Implementation**:
  - Every on-screen number, symbol, address, and date must trace back to a verified file cited in `sources.json`.
  - For live swaps, calculate execution accuracy directly from receipts (`docs/live_swap_*.json`), labeling deltas in plain words (e.g., "within 1 bp of quote").
  - In HyperFrames video builds, scene timing must strictly follow the master audio timeline ("picture follows audio"), inactive scenes must unmount with `visibility: hidden; display: none;`, and audio element durations must match media length to the decimal.



