---
name: bine-ui-standing-rules
description: >-
  Enforces the 4 standing Bine frontend UI rules across all routes and components:
  (1) zero displayed underscores outside [data-raw-code], (2) consistent BineLogoTile
  rendering and exact left-edge alignment across nav and footer, (3) readable liquid-glass
  cards with inner contrast scrims and one-card-per-stack interaction, and (4) mandatory
  real-browser CDP inspection and verification before committing frontend changes.
---

# Bine Frontend Standing Rules (`bine-ui-standing-rules`)

## Overview
Activate this skill whenever creating, editing, or auditing frontend code (`frontend/src/`) or UI documentation in Bine. These 4 standing rules prevent regressions in copy clarity, brand consistency, glass readability, and browser verification.

## Standing Rules

### 1. Never Render Raw Identifier Underscores in UI Copy
- **Rule**: No underscore character (`_`) may appear in any visible text, `aria-label`, `title`, tooltip, `placeholder`, `alt` text, or `document.title` outside raw code/command blocks (`<pre>`, `<code>`, or `[data-raw-code]`).
- **Implementation**:
  - Route all refusal codes (`slippage_too_high`, `below_issuer_minimum`, `quality_unreliable`, etc.), execution statuses (`LIVE_SUBMITTED`, `DRY_RUN_OK`, `REQUIRES_APPROVAL`), depth sources (`amm_pools`, `catalog_volume_24h`), and response schema field names through `frontend/src/lib/humanize.ts` (`humanizeRuleCode`, `humanizeStatus`, `humanizeDepthSource`, `humanizeFieldKey`, `humanizeCode`).
  - Wrap genuine CLI flags, JSON payloads, or MCP tool names (`bine_check`, `bine_buy`) in `<code data-raw-code>` or `<pre data-raw-code>`.
- **Automated Check**:
  - Run `backend/.venv/bin/python scripts/check_underscores.py` and verify `TOTAL_UNDERSCORE_OFFENDERS=0`.

### 2. Identical Logo Component & Left-Edge Container Alignment
- **Rule**: The header brand lockup, footer brand lockup, and favicon must share one monochrome silver/chrome visual identity (`colorTint="#ffffff"` on `#000000`), and the nav and footer logo tiles must align to the exact same `x` coordinate at `1440px` across every route (`0px` drift).
- **Implementation**:
  - Always use `<BineWordmarkLockup tileSize={36} />` from `frontend/src/components/BineLogo.tsx` in both `TopHeader` and `Footer`.
  - Under `prefers-reduced-motion: reduce`, keep `LiquidMetal` mounted at `speed={0}` (frozen shader frame) rather than swapping to a differently colored static gradient.
  - Inside `.bine-container`, use a unified `max-w-[1240px] mx-auto` wrapper across `TopHeader`, `Footer`, and all 5 route pages (`Home.tsx`, `Guard.tsx`, `Refusals.tsx`, `Receipts.tsx`, `Integrate.tsx`).
- **Automated Check**:
  - Run `backend/.venv/bin/python scripts/verify_logo_and_alignment.py` and verify `UNIQUE_LOGO_X_COORDS_AT_1440=[100]` (`0px` drift) and nav-vs-footer logo pixel diff `<= 2/255`.

### 3. Liquid Glass Readability Scrim & Single-Open-Card Stack Discipline
- **Rule**: Every `.bine-glass-panel` must wrap its text/content inside `.bine-glass-scrim` so body and secondary text maintain `>= 4.5:1` WCAG 2.2 AA contrast in both Light and Dark themes. Never place text directly over raw blurred background.
- **Implementation**:
  - Use `GlassStack` and `GlassDetailPanel` (`frontend/src/components/GlassStack.tsx`) for interactive card groups.
  - Keep at most one card open per stack (`aria-expanded`, `aria-controls`, `role="region"`), support `Escape` and `Close` button dismissal returning focus to the trigger, recede unselected siblings subtly on desktop/tablet (`opacity: 0.58; transform: scale(0.985)`), and expand inline on `390px` mobile without sibling scale transforms.

### 4. Real-Browser CDP Verification Before Every Frontend Commit
- **Rule**: Reading source code does not count as a UI audit. Every frontend change must be inspected in a real headless Chrome session via CDP across `390px`, `768px`, and `1440px` in both Light and Dark modes before committing.
- **Verification Checklist**:
  1. `backend/.venv/bin/python scripts/check_underscores.py` -> `TOTAL_UNDERSCORE_OFFENDERS=0`
  2. `backend/.venv/bin/python scripts/verify_logo_and_alignment.py` -> `0px` logo `x` drift and identical nav/footer tile rendering
  3. `backend/.venv/bin/python scripts/verify_glass_and_perf.py` -> `OVERFLOW_FAILURES=0`, `0` long tasks `> 50 ms`, and 30 `glass_<page>_<theme>_<width>.png` screenshots captured and visually inspected
  4. `grep -rn "—" frontend/src/` -> `0` matches
  5. `npm --prefix frontend run build` -> main JS chunk `< 500 kB` raw
