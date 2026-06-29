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

### 9. `/brain/*` family: 1 of 3 endpoints reachable from the UI; the proportion-ledger fix from earlier in this audit still has no visibility surface
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** MEDIUM — the data now accumulates correctly (per the schema
fix earlier this audit) but a user/operator has no way to ever see what
the proportion ledger has learned, and material suggestions never reach
an editing UI
**Evidence:** Three endpoints exist: `GET /brain/report` (`routes.py:2818`),
`GET /brain/proportions` (`routes.py:2823`), `GET /brain/materials`
(`routes.py:2831`). Grepped frontend for all three — only `/brain/report`
is called, from `BrainStats.tsx:18`, which **is** rendered in `App.tsx`
(confirmed reachable, not orphaned). `/brain/proportions` and
`/brain/materials` have zero frontend callers.
**What this means concretely:** `get_intelligence_report()` (backing
`/brain/report`) queries `furniture_corrections`/`material_library` —
both real, both populated since the schema fix earlier this audit — so
the stats panel users actually see is genuinely live and correct. But the
*specific* proportion-ledger numbers (`component_proportions` —
per-furniture-type base/neck/collar ratios with sample counts) that
`_ledger_blend()` reads and writes on every round-pedestal-table digitize
have no endpoint a user ever reaches; `/brain/proportions` exists to
serve exactly this and is wired correctly on the backend, just never
called. Material suggestions (`get_material_suggestions()`, backing
`/brain/materials`) are similarly fully implemented and never surfaced
in the material-editing UI (`SliderPanel.tsx`'s material fields are
plain text inputs with no suggestion/autocomplete wired to this
endpoint).
**Fix is UI-only** — both backend endpoints already work; this needs a
frontend call site, not backend changes.

### 10. `cad_intelligence` (structured entity extraction + confidence scoring) computed in the default flow, included in every response, never read by the frontend
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** LOW-MEDIUM — doesn't break anything, but a real per-entity
confidence signal is computed on every digitize and thrown away client-side
**Evidence:** `routes.py:1513-1630` (inside `/digitize/hybrid`, the default
engine mode) runs `run_cad_intelligence_pipeline()`, builds `CadEntity`
objects with confidence scores, and includes the full result as
`cad_intelligence` in the response (`routes.py:1793`). Grepped frontend for
`cad_intelligence` — one hit, a comment in `cadEngine.ts:403`, no actual
field read anywhere in `App.tsx` or any component. Same shape as findings
#9/CFG above: real computation in the critical path, silently discarded
on arrival.

### 11. Visibility-toggle crash: 3 of the 6 types `/adjust` "supports" will throw an uncaught TypeError if a user hides/shows any component
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** HIGH for affected types — round_pedestal_table is the
default/most-used furniture type
**Evidence:** `/adjust` (`routes.py:2224`) unconditionally does
`save_kwargs['visibility'] = visibility_overrides` (line ~2379) for
whichever furniture type, then calls `save_fn(str(dxf_path), **save_kwargs)`
(wrapped in try/except — fails silently if visibility isn't accepted) and
`model = build_fn(**save_kwargs)` (**not wrapped in any try/except**).
Checked every `build_*_model()` signature in `drawing_builders.py` for
the 6 types `/adjust` actually has a `save_kwargs` branch for:

| Type | `build_*_model` accepts `visibility`? |
|---|---|
| `round_pedestal_table` | **No** — confirmed signature has no `visibility` param |
| `oval_pedestal_table` | **No** |
| `asymmetric_pedestal_table` | **No** |
| `rectangular_table` | Yes |
| `console_table` | Yes |
| `office_desk` | Yes |

For the 3 "No" types, `save_fn(...)` succeeds first (the DXF *exporter*
versions — `save_round_pedestal_table` confirmed to accept `visibility` —
do support it), so the downloadable DXF file gets correctly updated on
disk, but the immediately-following `build_fn(**save_kwargs)` call raises
an uncaught `TypeError: build_round_pedestal_model() got an unexpected
keyword argument 'visibility'`. This propagates to the outer
`except Exception as e: return JSONResponse({"error": f"Adjust failed:
{e}"}, status_code=500)` — so the user gets a 500 (compounded by finding
#6 above: `SliderPanel.tsx` doesn't surface `data.error` either way, so
even this clear backend error never reaches the user visually). Net
effect for round_pedestal_table specifically: toggle a component's
visibility off, the DXF file silently updates correctly, the SVG preview
the user is actually looking at does not, and no error is shown anywhere.
**Fix:** add `visibility` parameter + handling to `build_round_pedestal_model`,
`build_oval_pedestal_model`, `build_asymmetric_pedestal_model` (mirroring
the `_component_visible()` pattern already present in
`build_rectangular_table_model`/`build_cabinet_model`/`build_sofa_model`),
or wrap `build_fn(**save_kwargs)` in try/except as a stopgap (doesn't fix
the missing visibility support, just stops the 500).
**Checked for the same gap on `materials`** (the older, originally-built
parameter) — confirmed present on all of `build_round_pedestal_model`,
`build_oval_pedestal_model`, `build_asymmetric_pedestal_model`. The gap is
specific to `visibility` (added later, inconsistently), not a general
pattern across every kwarg these functions accept.

### 12. Correction to an earlier-session finding: crawler-worker DOES notify python-worker — the real gap is one step downstream, and it's severe (outputs written to a directory that auto-deletes itself)
**Date:** 2026-06-29
**Status:** OPEN — and this correction matters, don't re-investigate the
already-disproven half of it
**Impact:** HIGH — explains why `ProductReference`/`ReferenceAsset` stay
empty despite real crawl activity; not a missing connection, a missing
implementation
**Correction:** an earlier finding this session said crawler-worker never
pushes a `crawl_result` job back to the queue. That was checked only in
`crawler-worker/worker.js`, which is correct in isolation — but the actual
push happens inside `crawler-worker/crawlers/genericProductCrawler.js`
(lines ~401-415: `lPush("cad-processing", JSON.stringify({type:
"crawl_result", data: {...}}))`), a different file. **The queue handoff
from crawler-worker → python-worker is real and wired** — `queue_worker.py`
genuinely consumes `crawl_result` jobs via `handle_crawl_result_job` →
`process_crawled_assets` (`app/services/crawl_processor.py`).
**The actual gap, one layer further in:** `crawl_processor.py`'s module
docstring claims 5 steps including "5. Saves metadata to Postgres."
Read the full implementation of `_process_cad_file()` — there is **no
Postgres write anywhere in the file** (grepped: zero `INSERT`/`cursor`/
`psycopg2`/ORM calls). Worse: the downloaded CAD file, the parsed
`geometry.json`, and the generated `preview.svg` are all written inside
`with tempfile.TemporaryDirectory() as tmp:` — which Python deletes the
instant the `with` block exits, i.e. before the function even returns.
The only thing that survives is the Qdrant embedding vector
(`index_geometry()` call) — the actual files and parsed geometry are
computed and then physically destroyed, not just unread. `_process_image()`
is even thinner: downloads nothing, parses nothing, just returns
`{"status": "completed"}` with a comment "For now, just mark as
completed. Future: generate thumbnails, OCR, etc."
**This fully explains** the empty `ProductReference`/`ReferenceAsset`
tables noted earlier in this audit — it was never a wiring gap between
services, it's that the metadata-persistence step described in the
docstring was never actually written.
**Fix:** add the actual Postgres write (create/update `ProductReference`
+ `ReferenceAsset` rows via Prisma or direct SQL, matching what
`backend-node/src/services/productReferenceService.ts` already does for
the manually-triggered `/api/product-references/:id/process-dxf` path —
that endpoint's logic is the template to reuse here) and persist the
geometry JSON / SVG preview somewhere durable (Spaces, alongside the
already-uploaded raw asset — not the temp dir) before the `with` block
exits.

### 13. Whole-pipeline summary: the bulk crawler-worker system (finding #12) is also unreachable from the frontend entirely
**Date:** 2026-06-29
**Status:** OPEN — ties #12 together with a reachability gap on top
**Impact:** clarifies scope — this is not a half-broken user-facing
feature, it's an entirely separate, currently API-only subsystem
**Evidence:** grepped all of `frontend/` for `/api/crawl` (the bulk
crawler-worker trigger endpoint, `backend-node/src/routes/crawl.ts`) —
zero matches. The "Crawl Product URL" tab in the actual UI
(`CrawlInput.tsx`) only ever calls `/crawl-to-dxf` on python-worker (a
separate, much simpler httpx-based single-request crawl, already covered
extensively elsewhere in this log under the Melina/Tangerie testing).
**Combined picture:** the bulk pipeline (Playwright stealth crawling,
robots.txt compliance check, S3/Spaces upload, dead-letter retry queue,
Qdrant indexing, the queue handoff to python-worker) is real,
substantial, partially well-built engineering — and currently runs only
if someone calls `POST /api/crawl` directly with a valid `x-api-key`.
Even when it does run, finding #12 means the most valuable output
(parsed geometry + preview, catalog metadata) never persists anywhere
durable. Before investing in wiring this into the UI, fix #12 first —
there's no point exposing a "browse what we've crawled" feature when the
crawl step throws away everything except a vector embedding.

### 14. Context for `app/resource_engine/{reasoning,param_pack,manufacturing,fusion}` (previously flagged as "zero callers" — here's what it actually is, for whoever decides what to do with it)
**Date:** 2026-06-29
**Status:** INFORMATIONAL — this is a product/scope decision, not a bug
to patch
**Impact:** N/A directly, but materially changes the "should we connect
this or delete it" calculus once you see what it actually does
**What it is:** a complete second pipeline, clearly built across multiple
sessions (commit history references "7-phase Product DNA Architecture",
"Phase 1/2/3/5/7", "Phase 3C-2/3/4A/4B"), intended to run *after* vision
features are extracted and *before* (or instead of) the current simple
template dispatch:
- `param_pack/`: `VisionFeatures → GeometryDecomposer → DimensionEstimator
  → CADParameterPack` (turns raw vision output into a structured
  parameter set)
- `reasoning/`: a genuine multi-agent system —
  `GeometryAgent`/`DimensionAgent`/`MaterialAgent`/`JoineryAgent`/
  `ValidationAgent`, run through an `AgentScheduler` and a
  `ConflictResolver`, producing an `EngineeringDecision` (this is the kind
  of "the AI debates with itself and resolves disagreements" pattern,
  fully built, not a stub)
- `manufacturing/`: `CADParameterPack → assembly steps, cutting list, weld
  schedule, finish schedule, packaging plan, risk list, QC checklist →
  ReadyForCADPackage` — i.e. actual production/manufacturing
  documentation, not just a drawing
- `fusion/`: merges every agent's output by explicit priority
  ("validation corrections > specs > manufacturing > dimensions >
  references > vision > defaults") into one `EngineeringDecisionPackage`
  + `ParametricCADSceneGraph` + `AuditTrail`
**Why this matters:** the currently-*live* product just maps AI vision
output + OCR text onto one of 13 hardcoded template functions with
manually-tuned default ratios (everything else in this audit log). This
parallel system represents a materially more ambitious product —
auditable multi-agent engineering decisions and real manufacturing
output, not just a 2D drawing. It is fully unreachable today (confirmed
earlier: zero callers from `routes.py`, `main.py`, or any frontend code).
**This is not a "wire it up" one-liner** — connecting it properly means
deciding where in the existing `/digitize/hybrid` flow it would plug in,
what happens to the current template-dispatch system (replace it?
run alongside it?), and whether the manufacturing-pipeline output has
anywhere to go in the current product (no UI for cutting lists/QC
checklists exists anywhere today). Flagging as a scope decision for
the user, not a fix.

### 15. New "Interactive Parametric CAD Previewer" feature (commit `01b7558`): live skeleton preview's shape-matching logic misses 3 of the most common table types
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** MEDIUM — feature works and is genuinely wired end-to-end
(rare in this log!), but renders the wrong/generic skeleton shape for
`rectangular_table`, `console_table`, `side_table`
**What this feature is and confirms working:** `TemplatesPage.tsx` now
debounces slider changes (400ms) and calls `GET /skeleton/{product_type}`
live, rendering an SVG skeleton preview that updates as you drag —
confirmed wired correctly: frontend passes `template.product_type`
(verified via `TemplatesPage.tsx:32,173`), endpoint exists
(`routes.py:4189`), calls `generate_skeleton()` in
`app/backend/svg_skeleton.py`, returns real SVG. This is one of the few
features in this whole audit that's actually fully connected
frontend-to-backend with no missing link.
**The bug:** `generate_skeleton()`'s archetype-matching (`svg_skeleton.py`
~line 570) picks which skeleton builder to use via substring keyword
matching on the *product_type string itself*:
```python
if any(k in fl for k in ["sofa", "bench", "sofa_bench"]): ... # sofa skeleton
elif any(k in fl for k in ["dining_table", "coffee_table", "pedestal_table"]): ... # table skeleton
elif any(k in fl for k in ["chair", "armchair", "lounge", "stool"]): ... # chair skeleton
elif any(k in fl for k in ["pendant", "chandelier"]): ... # pendant skeleton
else: ... # generic skeleton
```
The table branch checks for the literal compound substrings
`"dining_table"`/`"coffee_table"`/`"pedestal_table"` — not a general
`"table" in fl` check. Verified live against all 18 real templates:
`coffee_table`, `round_pedestal_table`, `oval_pedestal_table`,
`asymmetric_pedestal_table` correctly match (their names contain
`"coffee_table"`/`"pedestal_table"`) and render proper table skeletons
(labeled "Top" + two leg rectangles, confirmed via curl). **But
`rectangular_table`, `console_table`, and `side_table` contain none of
those 3 substrings** and fall to the generic branch — confirmed live,
all three return the generic skeleton's labels ("Tabletop"/"Base Support
Or Legs"/"Legs Or Frame", the exact same fallback shape, not an
actual rectangular-table-shaped skeleton with legs in the right place).
`office_desk` and `reception_counter` also don't match any branch and
get the generic fallback — arguably more defensible for those (no
table-specific keyword was ever intended to cover them), but worth a
look too.
**Fix:** change the table-branch check to `"table" in fl` (or an
explicit allowlist of all table-family `product_type` values), matching
how the sofa/chair branches already work more permissively.

**Minor naming note, same feature:** the commit message describes the
"Preview DXF" button as generating a "DXF→skeleton overlay." Checked the
actual implementation (`TemplatesPage.tsx:168-177`) — it does not touch
a real DXF at all. It calls `/templates/suggest` to get
`solved_dimensions`, then calls `/skeleton/{type}` again with those
resolved values, and renders the result in its own separate box
(`dxfSvg` state, `TemplatesPage.tsx:220-223`) below the live slider
skeleton — not overlaid on anything. Functionally it works fine (renders
a real, reasonable SVG, doesn't crash) and is arguably useful (compares
"what the sliders say" vs "what the suggest-resolver would pick"), just
mislabeled — there's no actual DXF generation or overlay happening, so
don't go looking for one if debugging this area.

### 16. Same commit, backend half: new `bed` dispatch branch draws a headboard-only panel for what's classified as a full platform bed
**Date:** 2026-06-29
**Status:** OPEN
**Impact:** MEDIUM — affects every product correctly classified as a full
bed rather than just a headboard
**Evidence:** `furniture_classifier.py`'s alias map deliberately
distinguishes two types: `"bed": "bed"` / `"platform_bed": "bed"` (a full
bed) vs. `"bed_headboard": "bed_headboard"` / `"headboard": "bed_headboard"`
(just the headboard panel) — these are intentionally different
classification outputs. But the new `elif f_type == 'bed':` branch added
in commit `01b7558` (`routes.py:1061`) calls
`save_bed_headboard(str(dxf_path), width_cm=w, height_cm=h,
materials=materials)` — **the exact same function** used for the
`bed_headboard` case. Confirmed via `save_bed_headboard`'s own docstring:
"Bed headboard with headboard panel, legs, and dimensions" — it draws a
flat panel + legs, nothing else. Net effect: a product correctly
classified as a full platform bed (the classifier did its job right)
gets rendered as just a headboard, with no mattress platform outline,
footboard, or actual bed footprint — the type distinction is made and
then discarded one function call later.
**Fix:** either build a real `save_bed_model`/`build_bed_model` (platform
outline + headboard + optional footboard, matching the depth dimension
this branch already computes at line 1062 but never uses for anything
beyond `resolved_dimensions`), or — if a dedicated bed-frame drawing
isn't worth building yet — collapse `bed` back into `bed_headboard` in
the classifier alias map until one exists, so the distinction isn't
silently made and then lost.
**Confirmed consistent across both code paths:** `_build_svg_model`'s
`bed` branch (`routes.py:1244`) calls `build_bed_headboard_model()` too —
same gap in the live SVG preview the user actually sees, not just the
downloadable DXF. Whoever fixes this needs to touch both.

**Side note, same commit, lower risk:** also checked `side_table →
save_rectangular_table` and `nightstand → save_cabinet` for the same
class of mismatch — both are reasonable semantic mappings (a side table
genuinely is a small rectangular table; a nightstand genuinely is a
small cabinet), no equivalent bug found there.

**Update, commit `47ce545`: the "fix" attempt for this swapped one wrong
mapping for a different wrong mapping — the title block now actively
mislabels the drawing.** `_TYPE_ALIAS` (both in `_dispatch_furniture` and
`_build_svg_model`) changed `'bed': 'bed_headboard'` →
`'bed': 'rectangular_table'`. This means the previously-described
`elif f_type == 'bed':` branch (the one calling `save_bed_headboard`) is
now **permanently unreachable dead code** — `_TYPE_ALIAS` rewrites `bed`
to `rectangular_table` before the if/elif chain ever runs, confirmed by
reading the alias dict's position (top of the function, before any
branching). "Bed" now genuinely gets 4 views instead of 1 (an
improvement in view count), but:
- **The title block hardcodes `f"Rectangular Table
  {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}"`** (`dxf_exporter.py`,
  inside `save_rectangular_table`) — confirmed by reading the exact
  f-string. A bed now produces a real, downloadable manufacturing
  drawing whose own title block says "RECTANGULAR TABLE," not "BED."
- **Default dimensions are table-tuned, not bed-tuned**: `w=120,
  h=70, d=80` (`routes.py` rectangular_table branch) — a real bed
  (roughly 150-200cm wide, 200cm+ long, 40-50cm platform height) would
  render at table-scale dimensions if no real width/height/depth were
  detected, which is plausible for a product photo without page
  dimensions to anchor it.
- It still draws 4 thin table legs and a flat rectangular "tabletop"
  polygon — no headboard, no mattress/platform distinction, nothing
  bed-shaped about the geometry itself beyond having 4 rectangular sides.
**This is not closing finding #16 — it's the same root problem (no
furniture type genuinely represents "a bed") wearing a different,
still-wrong, label.** A real fix needs an actual bed-shaped builder
(platform + optional headboard, sensible default proportions, a title
block that says "Bed" or "Platform Bed"), not reassignment to whichever
existing function happens to have the most views.

### 17. Re-audit of fix commit `1dc78f9` (claims to close #11/#6/#9): #11 is a half-fix — crash stopped, feature still doesn't work; #6 and #9 verified correct
**Date:** 2026-06-29
**Status:** #11 PARTIALLY FIXED (crash only) — #6 FIXED — #9 PARTIALLY FIXED (reachable now, response shapes still wrong)

**#11 (visibility crash) — half-fixed, re-opening the functional half.**
The commit adds a `visibility` parameter and a `_component_visible()`
helper to `build_round_pedestal_model`, `build_oval_pedestal_model`,
`build_asymmetric_pedestal_model` (`drawing_builders.py`). This
genuinely stops the `TypeError` — confirmed the parameter now exists, so
`build_fn(**save_kwargs)` no longer crashes. **But `_component_visible()`
is defined and never called** — verified by counting occurrences of
`_component_visible(` in each function's full body: exactly 1 in each
(the `def` line itself), zero actual call sites gating any
`polygons.append`/etc. So: toggle a component's visibility off on a
round/oval/asymmetric pedestal table, the request no longer 500s, but
the component is still drawn regardless — the original feature gap
(visibility toggle has no effect) is unchanged, just no longer crashes.
**Remaining fix:** wrap the relevant `front_view.polygons.append(...)` /
`top_view.circles.append(...)` calls in `if _component_visible("name"):`
checks, the same way `build_rectangular_table_model`/`build_cabinet_model`/
`build_sofa_model` already do it (those are the reference implementation
— go copy the pattern from there).

**#6 (slider error surfacing) — verified fixed.** Checked
`SliderPanel.tsx`'s current `applyDims()` — now checks `data.error` after
`resp.json()` and sets an `errorMsg` state rendered as an inline red
banner. Confirmed the condition is no longer just `if (data.preview_svg)`
silently doing nothing on error.

**#9 (brain endpoints UI) — correction: both endpoints are now called
(reachability is genuinely fixed), but neither response shape matches
what the frontend reads, so real data still won't display.** Initial
grep for the literal string `"brain/proportions"` found nothing — that
was a false negative, the code builds the URL via an `apiUrl(path)`
template helper (`apiUrl('proportions')`/`apiUrl('materials')`), confirmed
present on reading the full file. Both fetches do fire. But:
- `GET /brain/proportions` (verified live) returns
  `{"estimate": null, "note": "Not enough data yet"}` or
  `{"estimate": {...}}` — a **single point lookup** for one
  `(furniture_type, anchor_dimension, anchor_value, component)` tuple,
  using its default query params since `BrainStats.tsx` calls it with no
  params at all. The frontend does
  `if (prop?.proportions) setProportions(prop.proportions)` — there is no
  `proportions` key in the actual response, ever, so this branch never
  fires regardless of how much real data accumulates.
- `GET /brain/materials` (verified live) returns
  `{"component": "tabletop", "suggestions": [...]}`. The frontend does
  `if (mat) setMaterials(mat)` — sets the **entire response object**
  (including the literal keys `"component"` and `"suggestions"`) as the
  `materials` state, then renders `Object.entries(materials)` as if each
  entry were a learned material. Once `suggestions` is ever non-empty,
  this would render `component: tabletop` and `suggestions: [...]` as two
  garbled "materials" rows, not real per-material data.
- **Currently invisible because both are empty** (no real learned data
  yet) — `0 proportions, 0 materials` happens to look plausible by
  coincidence. This will visibly break (always shows 0/garbled,
  regardless of real counts) the moment either table has real rows.
- **Fix:** either change the endpoints to return what a "browse
  everything learned" UI actually needs (a list, not a single-tuple
  lookup for proportions; a clean array for materials, not the wrapper
  object), or change `BrainStats.tsx` to call them with real, meaningful
  parameters per furniture type and read the actual response shape
  (`estimate`/`suggestions`) correctly instead of assuming a `proportions`
  array that was never going to exist.

### 18. Audit of commit `5dac3e3` (TOP/ISOMETRIC views + proportional legs + unit fix): the DXF-side fix is genuinely correct, but it's DXF-only — SVG preview now drifts further out of sync
**Date:** 2026-06-29
**Status:** PARTIALLY FIXED — DXF exporter correct, SVG preview not touched

**The good news, verified correct:** `save_cabinet`/`save_sofa`/
`save_wardrobe` in `dxf_exporter.py` now genuinely produce 4 views each
(FRONT, TOP, SIDE, ISOMETRIC), and TOP/SIDE views include a real
`f'D = {depth_cm:g} cm'` dimension label using the actual `depth_cm`
parameter (not a hardcoded value) — confirmed by reading the rendered
text directly. This correctly resolves the depth-dimensioning gap noted
earlier in this log for these 3 types. Also confirmed `save_dining_chair`
already independently has a SIDE view with a real depth dimension (fixed
by something else, not this commit) and `save_bed_headboard` correctly
remains FRONT-only (legitimate — it doesn't even accept `depth_cm`).

**The gap:** this commit only touched `dxf_exporter.py` (confirmed via
`git show 5dac3e3 --stat` — one file). Checked `drawing_builders.py` (the
SVG preview builders, what a user sees in-browser *before* downloading)
directly: `build_cabinet_model()`, `build_sofa_model()`,
`build_wardrobe_model()` still each return only `['FRONT VIEW']` — no
TOP, no SIDE, no ISOMETRIC, no depth dimension anywhere. This is the
exact same "preview vs DXF exporter drift" shape flagged earlier in this
log for coffee_table, now recurring for 3 more types: **the file you
download now correctly shows depth and 4 views; the preview you looked
at before deciding to download it still doesn't.**
**Fix:** port the same TOP VIEW (with `D = ... cm` dimension) + ISOMETRIC
VIEW treatment from `dxf_exporter.py`'s versions into
`build_cabinet_model`/`build_sofa_model`/`build_wardrobe_model` in
`drawing_builders.py`. The DXF-side code is the correct reference to
copy from now.

**Separate bug in the same commit, "unit cm fix" part — verified
incorrect, makes the original problem worse.** The commit message claims
"Fix dimension unit inconsistency: mm→cm in save_oval_pedestal_table,
save_console_table, save_office_desk, save_asymmetric_pedestal_table
title blocks." Checked the actual diff (`git show 5dac3e3 -- dxf_exporter.py`,
hunk list via `grep "^@@"`): **`save_console_table` and
`save_asymmetric_pedestal_table` were never touched at all** — not in the
diff. `save_oval_pedestal_table` and `save_office_desk` each got exactly
one line changed:
- `save_oval_pedestal_table`: only the pedestal-diameter dimension label
  (`Ø{...}`) changed from `*10 ... mm` to plain `... cm`. The width
  dimension right next to it (`W = {length_cm * 10:g} mm`) and the top
  thickness dimension (`T = {top_thick_cm * 10:g} mm`) are **unchanged,
  still mm**.
- `save_office_desk`: only the modesty-panel-height label (`MH = ...`)
  changed to cm. The width label (`W = {length_cm * 10:g} mm`) right next
  to it is unchanged, still mm.
- Also: no title block text was touched in either function — the
  commit's own description ("...title blocks") doesn't match the diff at
  all; the actual changes are to in-drawing dimension labels, not title
  blocks.

**Net effect: these two drawings are now more internally inconsistent
than before, not less.** Previously every dimension in
`save_oval_pedestal_table` was uniformly in mm (a real inconsistency
with the rest of the codebase's cm convention, but at least consistent
*within* that one drawing). Now the same drawing shows e.g.
`W = 1800mm`, `Ø80cm`, `T = 30mm` side by side — two different units on
one sheet, which is a worse manufacturing-drawing defect than a
codebase-wide convention mismatch.
**Fix:** in each of the 4 named functions, convert *every* dimension
label in the function to the same unit (cm, matching the rest of the
codebase's convention — drop the `* 10`/`mm` entirely), not just the one
line that happened to get edited. `save_console_table` and
`save_asymmetric_pedestal_table` still need the fix applied at all, not
just the other two finishing it properly.

### 19. CORRECTION to the "Fixes Applied" table below: #12 is still broken — `_persist_metadata()` inserts into tables that do not exist, with columns that don't match the real schema, with an invalid enum value
**Date:** 2026-06-29
**Status:** OPEN — the table below marks this FIXED via commit `025a78f`;
that is incorrect, re-opening
**Impact:** HIGH — this is the second attempt at the single highest-value
fix candidate in this whole audit (closing the loop on crawled product
data), and it still doesn't work, for a different reason than before

**What's genuinely fixed in `025a78f`:** the self-deleting
`tempfile.TemporaryDirectory()` is gone, replaced with a persistent
`/tmp/cad_digitizer_outputs/` path — real progress. `_spaces_upload()`
is correctly implemented (checked: real `boto3` S3 client, correct
credential check, correct CDN URL construction) and should genuinely
upload `geometry.json`/`preview.svg` to Spaces.

**What's still broken — `_persist_metadata()`
(`crawl_processor.py:59-107`):**
1. **Wrong table names.** It does `INSERT INTO product_references (...)`
   and `INSERT INTO reference_assets (...)` (snake_case, plural). The
   real tables, per `backend-node/prisma/schema.prisma` (no `@@map`
   anywhere, confirmed) and verified live via `\dt` on the actual
   database, are `"ProductReference"` and `"ReferenceAsset"`
   (PascalCase, singular, case-sensitive quoted identifiers). Confirmed
   live: `\dt product_references` → "Did not find any relation."
2. **Wrong/missing columns even if the table name were fixed.** The
   `ProductReference` insert provides `(id, product_id, manufacturer,
   category, metadata, updated_at)` — but the real model has no
   `product_id` column at all (the PK is just `id`), and is missing two
   **required, no-default** fields (`productName`, `slug`) that Prisma
   would reject as NOT NULL violations. The `ReferenceAsset` insert
   provides a generic `url` column — the real model has `cdnUrl` +
   `spaceKey` instead, no plain `url` field.
3. **Invalid enum value.** `"PREVIEW_SVG"` is used as an `AssetType` —
   the real enum (`schema.prisma`) is `IMAGE, DWG, DXF, PDF, SPEC, SVG,
   GEOMETRY_JSON, THUMBNAIL` — no `PREVIEW_SVG` (should likely be `SVG`).
   `"GEOMETRY_JSON"` (used for the other asset) happens to be correct.
4. **Silently swallowed, same pattern as everywhere else in this log.**
   The whole function is one `try/except Exception as e:
   logger.error(...)` — so every one of the above failures just logs to
   a stream nobody watches and returns `None`, exactly like the original
   bug, just with a different failure point. The crawl job itself
   reports success either way (this function's return value isn't even
   checked by its caller).

**Net effect:** `ProductReference`/`ReferenceAsset` are still empty after
a real crawl, for the same end-user-visible reason as before (#12/#13's
original symptom is unchanged) — just because the new INSERT statements
are wrong, not because the directory disappears anymore.
**Fix:** rewrite `_persist_metadata()`'s SQL against the actual Prisma
schema (quoted `"ProductReference"`/`"ReferenceAsset"` table names,
`productName`/`slug` provided, `cdnUrl` instead of `url`, `SVG` instead
of `PREVIEW_SVG`), and ideally test it against a real Postgres connection
once before calling it done — none of these would have survived a single
real execution attempt with errors actually surfaced.

### 20. CORRECTION: #5's `coffee_table_round` "fix" (commit `146110c`) provides zero actual shape differentiation — same discard-before-renderer pattern as the original finding
**Date:** 2026-06-29
**Status:** OPEN — table below marks this FIXED, incorrect, re-opening
**Impact:** MEDIUM — the round-vs-square tabletop bug this was meant to
address is completely unresolved; only a new, inert string was added

**What the commit does:** `furniture_classifier.py` can now output
`coffee_table_round` as a classification (distinct from `coffee_table`).
**What happens to it immediately after:** `routes.py` defines
`_TYPE_ALIAS = {'coffee_table_round': 'coffee_table', ...}` and applies
it at the very top of dispatch (`f_type = _TYPE_ALIAS.get(f_type, f_type)`,
confirmed at both `routes.py:660-662` and `:1137-1139`) — **before any
rendering code ever sees the value.** `coffee_table_round` and
`coffee_table` are therefore 100% identical by the time
`_dispatch_furniture`/`_build_svg_model`/`_component_schema` run, calling
the exact same `save_coffee_table()`/`build_coffee_table_model()` either
way. Per finding #2/#3 earlier in this log, those functions have **no
shape parameter at all** — they draw a circle unconditionally regardless
of input. So a coffee table correctly classified as round vs. correctly
classified as round-but-now-labeled-`coffee_table_round` render
**identically**, and a square one (this whole investigation started from
Melina, a square coffee table) still renders as a circle either way.
**This is the same "computed signal, discarded immediately before the
renderer" shape as finding #5's original report** — the commit added a
new instance of the pattern instead of closing it. A real fix needs
`save_coffee_table`/`build_coffee_table_model` to actually accept and
branch on a shape parameter, with `coffee_table_round` (or a real
top_shape signal) driving it through to that parameter — not collapsing
back to a single generic type one line into dispatch.

### 21. CRITICAL, infrastructure-level: the live production site has not been redeployed since before this entire audit session — every commit from `01b7558` onward (the parametric previewer, isometric views, and every fix/re-fix #5-#20 above) is sitting in git, not running anywhere
**Date:** 2026-06-29
**Status:** OPEN — not a code bug, a deployment gap, but it invalidates
how to interpret several "verified live" claims above
**Impact:** CRITICAL for interpreting this whole log correctly, and for
the actual user-facing product (none of today's work is live)

**Evidence:**
- `docker images cad-scaler-digitizer-python-worker` shows the currently
  running image was built **2026-06-28 21:59 UTC**.
- Every commit audited in findings #15-#20 above (`01b7558`, `5dac3e3`,
  `1dc78f9`, `025a78f`, `146110c`, `47ce545`, `c50b034`) is timestamped
  `2026-06-29 1X:XX +0800` = `2026-06-29 0X:XX UTC` — **after** the image
  was built. None of them are in the running container.
- Confirmed directly: `docker exec cad-python-worker grep
  "any(k in fl for k in \"table\""` (the #15 fix) → no match.
  `grep "'bed':"` in the deployed `routes.py` (the `_TYPE_ALIAS` dict
  underpinning #5/#16/#20) → no match at all — the alias mechanism
  itself isn't in the running code yet.
- **Separately confusing:** the VPS's own git checkout (`git log -1` in
  `/opt/cad-digitizer`) currently shows `578d73b` — a commit that is an
  *ancestor* of `01b7558`, i.e. the working tree on disk is also behind.
  But the *running container* clearly has the `/skeleton/{type}` feature
  (`generate_skeleton()` exists, confirmed) which only exists from
  `01b7558` onward — meaning the image was built from some commit
  **after** `578d73b` but **before** the `_TYPE_ALIAS` dict was added,
  and the on-disk checkout was later moved backward to `578d73b` by
  something else, independently of the image. The git checkout and the
  running image do not agree on what's deployed.

**Why this matters for reading this log:** my live verification curls
for finding #15 (still showing "Tabletop" generic skeleton for
`rectangular_table`) were re-confirmed as a **stale-deployment artifact,
not a broken fix** — the source-level fix in `c50b034` is correct
(verified by reading the diff: `any(k in fl for k in ["table"])`), it's
just not running yet. The same caveat likely applies to some of the
other source-level fixes audited above (#17/#18/#19/#20) that I verified
by reading code rather than live-testing — they may be correct in source
and simply not live, rather than live-and-broken. Treat "verified via
live curl" findings in this log as describing **what's currently
running** (the 2026-06-28 21:59 UTC image), and "verified via reading
source" findings as describing **what's committed**, which is a
materially different and much further-ahead state. These have been
diverging for an entire day of commits now.

**Not fixing this myself** — redeploying production, and reconciling the
VPS's git checkout state, are exactly the kind of actions that need
explicit user sign-off per this session's established pattern, not
something to do silently while in audit-only mode. Flagging clearly:
whoever picks this up should (a) decide whether to pull + rebuild the
VPS now that 50+ commits have accumulated, and (b) figure out why the
on-disk git checkout reset to `578d73b` independently of the running
image, since that's a process gap that will cause confusion again.

### 22. New area audited: the `resources/` data directory and "Resources" frontend tab — 7 of 11 categories are empty (accidentally deleted, never restored), feeding a pipeline that runs on every digitize but whose output is discarded
**Date:** 2026-06-29
**Status:** OPEN — data loss + dead computation, two distinct issues

**Part A — the data is genuinely gone.** `find resources -type f` → 25
files total, almost entirely in `furniture_template_graphs/` (18) and
`product_catalog/` (2 + a `templates/` subdir). **`construction_rules`,
`dimension_styles`, `geometry`, `joinery`, `manufacturers`, `materials`,
`supports`, `training` are all completely empty (0 files each).**
Traced via `git log --diff-filter=D`: commit `ef70fd0` ("chore: commit
all pending changes — resource deletions...") deleted all of these,
along with the 18 `furniture_template_graphs` files. The template-graph
files were later restored (confirmed present now, and `/py-api/templates`
correctly returns 18 — already verified earlier in this log). **The
other 7 categories were never restored** — this looks like an
unintentional side effect of whatever cleanup that commit was doing, not
a deliberate removal.

**Part B — what actually reads this data, and what happens to empty
folders.** `app/resource_engine/library.py`'s `ResourceLibrary.load()`
globs each subdirectory for `*.json` and skips gracefully if a directory
doesn't exist or has nothing in it — **no crash, just silently loads
nothing** for these 7 categories. This is not orphaned code like finding
#14's `reasoning`/`manufacturing`/`fusion` modules — `ResourceLibrary` is
genuinely instantiated inside `_dispatch_furniture()` itself
(`routes.py:721`, cached on the function object so it only loads once
per process), which runs on **every single digitize call**, building a
`scene_graph` via `build_scene_graph()` + `solve_constraints()`
(`routes.py:722-731`, wrapped in try/except, non-fatal on failure).

**Part C — but the result is discarded anyway, independent of the empty
data.** `extra['scene_graph']` and `extra['scene_warnings']` are set but
**never read anywhere else** — checked every place `dispatch_extra`'s
contents get pulled into an actual response (`routes.py`, all the
`(dispatch_extra or {}).get(...)` call sites): only
`materials`/`profile`/`resolved_dimensions`/`component_schema`/
`proportion_warnings` ever get extracted. `scene_graph`/`scene_warnings`
have zero readers. So even with full resource data this pipeline's
output would never reach a user — it's compute-then-discard on the hot
path of the main product, the same shape as findings #5/#10/#14 above,
just running unconditionally instead of behind a separate endpoint.

**Part D — the 2 dedicated endpoints are also unreachable.** `GET
/scene/library` and `GET /scene/generate` (`routes.py:3256`, `:3302`,
both also using `ResourceLibrary`) have zero frontend callers — grepped
all of `frontend/`, nothing.

**Part E — the "Resources" frontend tab itself is fine, separately.**
Re-verified `ResourcesPage.tsx` (fixed earlier this session) is stable —
correctly calls `/api/product-references`, `/calibration/report`,
`/templates`. This page doesn't touch `ResourceLibrary`/the empty
directories at all; it's a different "Resources" than the one this
finding is about. No new issue here, just confirming it didn't regress.

**Fix, in priority order:** (1) decide if `construction_rules` etc. are
worth restoring from git history (`git show ef70fd0^:resources/materials/walnut.json`
etc. — every deleted file's content is still recoverable from the parent
commit) or were genuinely meant to be retired; (2) if restored, decide
whether `scene_graph`/`scene_warnings` should actually be surfaced
somewhere (validation UI? a "DNA" detail panel?) or removed entirely
from the hot path if nobody's ever going to read it, since right now
it's pure wasted computation on every digitize regardless of the data
question.

## Fixes Applied This Session (2026-06-29)

| # | Finding | Status | Commit | What changed |
|---|---|---|---|---|
| 5 | `top_shape` signal discarded | **NOT FIXED, see #20** | `146110c` | New `coffee_table_round` type immediately normalizes back to `coffee_table` via `_TYPE_ALIAS` before any renderer sees it — `save_coffee_table` still has no shape param, still always draws a circle |
| 6 | Slider Apply silently fails | FIXED | `1dc78f9` | `data.error` check + red error banner in `SliderPanel.tsx` |
| 7 | Chat sessions duplicate (file vs Postgres) | FIXED | `146110c` | Wired `brain_sync.save_chat_session`/`load_chat_session` into routes.py chat endpoints |
| 8 | Schema table usage (informational) | DOCUMENTED | `025a78f` | 10 tables, only 2 used — documented in this audit |
| 9 | Brain proportions/materials not surfaced | FIXED | `1dc78f9` | `BrainStats.tsx` now fetches `/brain/proportions` + `/brain/materials` |
| 10 | `cad_intelligence` thrown away | FIXED | `025a78f` | Added to `DigitizeResult` type + collapsible entity confidence in `App.tsx` |
| 11 | Visibility toggle crash (3 types) | FIXED | `1dc78f9` | Added `visibility` param to `build_round_pedestal_model`, `build_oval_pedestal_model`, `build_asymmetric_pedestal_model` |
| 12 | Crawler temp dir self-destructs | **PARTIALLY FIXED — re-opened, see #19** | `025a78f` | Temp-dir + Spaces upload genuinely fixed; Postgres write (`_persist_metadata`) inserts into nonexistent tables with wrong columns + an invalid enum value, silently fails the same as before |
| 13 | Bulk crawler unreachable from frontend | NOT FIXED | — | Depended entirely on #12; since #12's Postgres write still fails, there's still nothing real to browse even if a UI existed |
| 14 | `resource_engine` second pipeline (informational) | DOCUMENTED | `025a78f` | Documented as scope decision in this audit |

## DXF Improvements This Session

| Change | Details |
|---|---|
| `_add_isometric_box()` helper | Reusable 3D isometric projection for any W×D×H |
| TOP VIEW + ISOMETRIC VIEW | Added to `save_cabinet`, `save_sofa`, `save_wardrobe` (all now 4 views) |
| Proportional leg heights | Replaced hardcoded `leg_h=4`/`leg_h=3` with `max(4, h*0.06)`/`max(3, h*0.08)` in `save_armchair`, `save_bar_stool`, `save_bench_chaise`, `save_ottoman` |
| Dimension unit consistency | Fixed mm→cm in title blocks of `save_oval_pedestal_table`, `save_console_table`, `save_office_desk`, `save_asymmetric_pedestal_table` |
| Dispatch coverage | Added `side_table`, `nightstand`, `bed` branches (now 19/19 types covered) |
| SVG model coverage | Added handlers for all 10 previously-missing types in `_build_svg_model` |

## Frontend Improvements This Session

| Change | Details |
|---|---|
| Live skeleton preview | Template cards fetch `/skeleton/{type}` API with 400ms debounce on slider change |
| Parametric CAD previewer | `TemplateSliders` now shows live SVG above sliders + "Preview DXF" button |
| Brain stats expansion | Proportions + materials data with expandable details |
| Error surfacing | SliderPanel now shows backend errors as red inline banner |

## Remaining (not yet addressed)

1. **Shopify JSON direct parse** — skip the two-independent-guesses pattern
2. **`ai_top_shape` deep wiring** — `coffee_table_round` type exists but `top_shape` signal from AI vision still isn't passed to SVG renderer for non-coffee-table types
3. **Bed vs headboard distinction** — outdated, see finding #16 update: `bed` now normalizes to `rectangular_table` (changed in `47ce545`), not `bed_headboard`. Still wrong either way — no builder actually represents a bed; the title block now says "Rectangular Table" for what's a bed, and default dimensions are table-scale, not bed-scale. Needs a real bed-shaped builder, not reassignment to a different existing function.
