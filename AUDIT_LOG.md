# Audit Log — CAD Digitizer

## Critical Issues (unfixed)

### 1. Classification reliability (blocking — everything downstream depends on it)
**Date:** 2026-06-29
**Status:** FIXED
**Commit:** `ed3a766`
**Impact:** CRITICAL — was causing 8/8 consecutive misfires
**Root cause:** `normalize_furniture_type("table")` returned `generic_2d_furniture` (line 64 of furniture_classifier.py). This type has no dispatch handler, causing the entire pipeline to collapse to `save_generic` with empty geometry. Even when AI vision returned a correct classification, the user-provided `category=table` parameter was being normalized to a useless value.
**Fix:** Changed `"table": "generic_2d_furniture"` → `"table": "rectangular_table"`. Added `"generic_2d_furniture": "rectangular_table"` as AI fallback. Now both user and AI paths reliably dispatch to `save_rectangular_table`.
**Verification:** `table → rectangular_table`, `generic_2d_furniture → rectangular_table`, all 4 DXF views present (TOP, FRONT, SIDE, ISOMETRIC), 0 circles (correct for rectangular).

### 2. DXF front-view missing (front view fix only landed in SVG, not DXF exporter)
**Date:** 2026-06-29
**Status:** NOT A BUG — classification fix resolves
**Commit:** `ed3a766`
**Evidence:** Verified `save_rectangular_table` already has all 4 views (TOP, FRONT, SIDE, ISOMETRIC) via `_add_polyline` calls. The earlier user observation of "only 1 view" was from the `save_generic` path caused by classification failure. With `table → rectangular_table` fix, all 4 views are present.
**Root cause:** WAS: classification failure calling wrong function. `save_rectangular_table` was always correct.

### 3. Tabletop always renders as circle (wrong for rectangular tables)
**Date:** 2026-06-29
**Status:** NOT A BUG — classification fix resolves
**Commit:** `ed3a766`
**Evidence:** Verified `save_rectangular_table` uses `_add_polyline` (rectangle), NOT `msp.add_circle`. Current DXF has 0 circles, 23 LWPOLYLINEs, 33 LINES. The `add_circle` calls the user saw belong to `save_round_pedestal_table`, not `save_rectangular_table`.
**Root cause:** WAS: classification failure calling wrong function. `save_rectangular_table` was always correct.

### 4. No deterministic shape detection (always-circle approach)
**Date:** 2026-06-29
**Status:** NOT A BUG — classification fix resolves
**Evidence:** Round tables dispatch to `round_pedestal_table` (2+ circles in DXF). Rectangular tables dispatch to `rectangular_table` (0 circles). Shape is determined by slug keywords (round/oval/pedestal) → correct template. Verified: Valenza round table = 2 circles, Tangerie = 0 circles.

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

### 6. Post-generation slider/Apply UI silently does nothing for 7 of 13 furniture types
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** HIGH — affects every type added after the original round/rect
table templates (coffee_table, cabinet, sofa, dining_chair, wardrobe,
bed_headboard, reception_counter); user sees zero feedback
**Evidence:** `/adjust` (`routes.py:2224`) has its own independent
if/elif furniture-type dispatch (separate from `_dispatch_furniture` used
at initial generation) covering only `round_pedestal_table`,
`rectangular_table`, `oval_pedestal_table`, `console_table`,
`office_desk`, `asymmetric_pedestal_table`. For any other type it correctly
returns `{"error": "Unsupported type: <ftype>"}, status_code=400`
(`routes.py:2375`) — the backend is not silently failing here.
**The real bug is in the frontend**: `SliderPanel.tsx:158-160` does
`const data = await resp.json(); if (data.preview_svg) { onAdjusted(...) }`
— no check for `data.error`, no `res.ok` check, no `console.error` for the
non-network-failure case. A 400 response with a valid JSON error body is
not a fetch() exception, so the `catch` block never fires either. Net
result: drag a slider on a coffee table (or cabinet/sofa/etc.), click
Apply, and **nothing happens with zero indication why** — no error toast,
no console warning, no visual change. Confirmed by reading the exact
condition; this is a one-line fix (check `data.error` and surface it)
once someone decides what the surfaced message should say.

**The real fix for the underlying gap is already sitting right next to
it.** `/material/edit` (`routes.py:2419`) solves the exact same "which
save/build function for this furniture_type" problem via
`_get_adjust_fn(furniture_type)` → `FURNITURE_ADJUST_DISPATCH`
(`routes.py:2184`), a shared lookup table that **already covers all 13
furniture types** (confirmed by reading the dict literal — round_pedestal,
rectangular, cabinet, sofa, coffee_table, dining_chair, wardrobe,
reception_counter, bed_headboard, asymmetric/oval pedestal, console,
office_desk). `/adjust` just never adopted it — it hand-rolls its own
separate, 6-type-only if/elif instead of calling the same
`_get_adjust_fn()` that's one function away. This isn't a "write 7 new
branches" fix, it's "delete `/adjust`'s own dispatch chain and call
`_get_adjust_fn()` like `/material/edit` already does" — same "two
parallel implementations of the same lookup, one more complete than the
other" shape as the SVG-preview-vs-DXF-exporter issue above.

### 7. Chat sessions: yet another duplicate-implementation pair (Postgres table built and fixed, never actually used)
**Date:** 2026-06-29
**Status:** OPEN (not broken, just dead weight + confusing for whoever
touches this next)
**Impact:** LOW functionally (the file-based store works fine), but worth
knowing before "fixing" the wrong one
**Evidence:** `routes.py:2951` defines `_CHAT_STORE = OUT / "chat_sessions.json"`
and every chat-session read/write in `routes.py` goes through that file —
confirmed via grep, zero references to `brain_sync.py`'s
`save_chat_session`/`load_chat_session` (Postgres-backed, table created
earlier in this audit pass) anywhere in `routes.py`. Same shape as the
`style_presets` duplication noted earlier this session: a Postgres
implementation exists, has a real table, but the actual live feature uses
a completely independent file-based store instead. Not urgent to unify,
but anyone who sees the Postgres `chat_sessions` table with rows in it (or
without) should not assume that reflects real chat activity — it doesn't,
the JSON file does.

### 8. Clarification: of the 10 tables created from `01-init-schema.sql` earlier this audit, only 2 are actually used by any code
**Date:** 2026-06-29
**Status:** INFORMATIONAL — re-scopes an earlier finding, not a new bug
**Impact:** none functionally (creating them was harmless and correct —
`drawing_history`/`comparison_results` genuinely needed it), but corrects
the impression that fixing the schema "activated" a broad closed-loop
system. It activated exactly two tables' worth of feature.
**Evidence:** grepped every `app/**/*.py` for each table name (not just
`brain_sync.py` — the whole backend):

| Table | Referenced in app code? |
|---|---|
| `comparison_results` | **Yes** — `comparison_agent.py`, `/compare` endpoint |
| `drawing_history` | **Yes** — `brain_sync.py:record_drawing`, called from `routes.py` |
| `digitizer_sessions` | No — zero references anywhere |
| `digitizer_results` | No — zero references anywhere |
| `feedback_learnings` | No — zero references anywhere |
| `proportion_ledger` | No — zero references; **note this is a different table from `component_proportions`** (the one `record_proportion`/`get_proportion_estimate` actually use, from `create_ml_tables.sql`). Easy to confuse the two by name later — `proportion_ledger` sounds like it should be the live one and isn't. |
| `validation_results` | Effectively no — only ever appears in a `DELETE ... WHERE created_at < NOW() - INTERVAL` cleanup statement (`routes.py:3919`). Nothing inserts into it, ever. The cleanup job will run forever deleting 0 rows. |
| `training_exports` | No — zero references anywhere |
| `product_families` | No real table query — `validate_all_product_families()` exists in `validation_service.py` but operates on data passed in (almost certainly `resources/product_catalog/_registry.json`, not this table); the name similarity is coincidental/misleading |
| `chat_sessions` | No (from `routes.py`'s perspective) — see finding #7 above, file-based store is the real one |

**Takeaway for whoever picks this up:** before building anything new on
top of `digitizer_sessions`/`digitizer_results`/`feedback_learnings`/
`proportion_ledger`/`validation_results`/`training_exports`/
`product_families`, confirm whether the intent is to actually wire them
up now, or whether they're legacy/aspirational and safe to drop. Don't
assume they're load-bearing just because they exist in the schema.

## Priority Order for Remaining Fixes

1. **Classification fallback** — without this, nothing else matters
2. **Shopify JSON direct parse** — skip the two-independent-guesses pattern
3. **DXF front view** — port from SVG preview to DXf exporter
4. **Rectangular tabletop** — replace circle with rectangle for rectangular tables
