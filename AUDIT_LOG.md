# Audit Log — CAD Digitizer

## Critical Issues (unfixed)

### 1. Classification reliability (blocking — everything downstream depends on it)
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** CRITICAL — when AI vision returns `generic_2d_furniture`, entire pipeline collapses
**Evidence:** 8/8 consecutive calls with same image returned `generic_2d_furniture` after a previous session produced `coffee_table`
**Root cause:** The AI vision call (OpenAI/Gemini) is non-deterministic. When it misfires, no classification fallback exists. The `_dispatch_furniture` function has no branch for `generic_2d_furniture`, so it falls through to `save_generic` with empty geometry.
**Fix required:** Slug-based fallback when AI classification confidence is low. The URL slug and extracted dimensions together can determine furniture type more reliably than the AI vision call alone.

### 2. DXF front-view missing (front view fix only landed in SVG, not DXF exporter)
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** HIGH — generated DXFs only have TOP VIEW, missing FRONT VIEW, SIDE VIEW, ISOMETRIC VIEW
**Evidence:** The front-view drawing code was added to the SVG preview path but never ported to `dxf_exporter.py`. Downloadable DXF has only 1 view.
**Root cause:** Two independent rendering paths (SVG preview vs DXF export) — the DXF path was missed.

### 3. Tabletop always renders as circle (wrong for rectangular tables)
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** HIGH — rectangular tables get a circular top in the DXF
**Evidence:** `save_rectangular_table` uses `msp.add_circle()` for the top view instead of a rectangular polyline. For a 140x80 table, the circle diameter is 80cm (`min(width, depth)`) — actively wrong, silently dropping the 140cm dimension.
**Root cause:** The circular tabletop was inherited from the round pedestal table template and never replaced with rectangular geometry.

### 4. No deterministic shape detection (always-circle approach)
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** MEDIUM — the DXF never reflects the actual product shape
**Evidence:** Every table gets a circular top view regardless of whether it's round or rectangular. Shape detection should be based on dimension ratios (width vs depth) and product page data (variant JSON, body_html).

## Fixed Issues

### F1. Round→rectangular dispatch (fixed, but blocked by issue #1)
**Date:** 2026-06-29
**Commit:** `f1407c6`
**Fix:** Slug-based shape detection (round/oval/pedestal keywords) maps to correct template. However, this only works when the AI doesn't override the category to `generic_2d_furniture`.

### F2. Variant dimension extraction (fixed)
**Date:** 2026-06-29
**Commits:** `feafb78`, `db8ea5c`, `90be31f`
**Fix:** Added W/L/H label patterns, mm→cm conversion, median height selection, body_html scanning, length→depth mapping.

### F3. OpenAI API key exposure (fixed)
**Date:** 2026-06-29
**Commit:** `78200fa`
**Fix:** Key redacted from 3 .env files, .gitignore hardened, old key revoked.

### 5. A `top_shape` signal already exists for coffee tables — but it's computed, used for an unrelated purpose, then discarded before reaching the renderer
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** MEDIUM — directly relevant to fixing issue #3/#4 (always-circle), but not a ready-made fix as-is
**Evidence:** `routes.py:1455` inside `/digitize/hybrid` computes
`ai_top_shape = 'circle' if 'round' in str(ai_result.get('furniture_type','')).lower() else 'rectangle'`,
then passes it into a `FurnitureAnalysis` object (`routes.py:1472`) that
only feeds `match_template()` — used solely to generate
`uncertainty_questions` for the `SmartConfirmations` UI component, then
discarded. It is **never passed to `_dispatch_furniture()` or
`build_coffee_table_model()`** — confirmed via grep, `ai_top_shape` has
exactly 2 references in the whole file (set once, read once, both inside
the confirmation-question path).
**Root cause / why this isn't a 1-line fix:** the heuristic itself is too
coarse to reuse as-is — it checks for the literal word "round" in the
*furniture_type string*, which for `coffee_table` is always `False`
(the string never contains "round"), so wiring this exact value through
would make every coffee table render as rectangular, including round
ones — flipping issue #3/#4 rather than fixing it. A real fix needs an
actual shape signal (AI vision asked explicitly about top shape, or
derived from width≈depth ratio + page data), not this string match.
**Related:** `required_views` shows the same discard-after-compute
pattern. `FurnitureAnalysis.required_views` defaults to
`['top','front','side']` and `app/furniture_intelligence/services/
vision_prompt.py`/`vision_service.py` ask for an even fuller
`['top','front','side','section','isometric']` — but nothing in
`_dispatch_furniture`/`dxf_exporter.py` ever reads `required_views` to
decide which views to actually draw. It only flows into
`furniture_intelligence/geometry/preview_generator.py`'s own preview
text and the confirmation-question metadata — never into the real DXF
view count, which is hardcoded per-function as documented in issues #2/#3
above. The `furniture_intelligence` module independently "knows" a coffee
table should get 5 views; `dxf_exporter.py` independently gives it 1; they
never talk to each other.

## Priority Order for Remaining Fixes

1. **Classification fallback** — without this, nothing else matters
2. **Shopify JSON direct parse** — skip the two-independent-guesses pattern
3. **DXF front view** — port from SVG preview to DXf exporter
4. **Rectangular tabletop** — replace circle with rectangle for rectangular tables
