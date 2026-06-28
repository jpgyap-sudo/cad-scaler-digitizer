# Audit Log — Multi-Agent Coordination

## 2026-06-29 (continued audit) — Claude (Sonnet 4.6) — CFG/Grammar/SelfCritic (1000+ lines, substantial) only reachable via a non-default mode; matching dead endpoint pair on the other "mode"

**Status:** DOCUMENTED. Not fixed (investigation-only).

`app/backend/cfg/` (canonical_furniture_graph.py, models.py, router.py — 1002
lines total) implements a genuinely substantial furniture taxonomy/grammar
system: 31 furniture types across 6 families (`GET /py-api/cfg/types`,
verified live, real rich data), plus `/cfg/evaluate`, `/cfg/generate`,
`/cfg/self-critic`. Mounted in `app/main.py:43` as `app.include_router(cfg_router)`
— **note it's mounted without the `/py-api` prefix variant the other router
gets** (`main.py:40-41` mounts the main router under both `/api` and
`/py-api` explicitly; cfg_router only gets included once, relying on its
own internal `prefix="/api/cfg"`). In practice `/py-api/cfg/types` still
resolves correctly (nginx rewrites `/py-api/X` → `/api/X` before forwarding),
but `/py-api/cfg/health` returned 404 live — not yet root-caused, worth a
look (possibly a route-registration-order collision with another `/health`
path; low priority, the substantive endpoints work).

**Bigger finding — reachability:** grepped frontend + `app/api/routes.py` +
`app/services/` for any caller of the CFG endpoints or its underlying
classes (`FurnitureGrammar`, `CanonicalFurnitureGraph`, `SelfCritic`)
**outside the module itself** — found exactly one: `routes.py` lines
1990-2021, inside the `/digitize/unified` endpoint (Phase 8: "SelfCritic
Auto-Correction Loop"). Nowhere else in the entire codebase invokes any of
this system.

Traced whether `/digitize/unified` is actually what real usage hits:
- Frontend's main upload flow (`App.tsx` ~line 225-240) branches on
  `engineMode`, which **defaults to `'hybrid'`** (`App.tsx:108`) — calls
  `/digitize/hybrid`, not `/digitize/unified`. A user has to manually
  switch the engine-mode toggle to "Smart" to reach `/digitize/unified`
  (confusingly, the UI labels that mode "Smart" while the function it
  calls is `digitizeUnified()` hitting `/digitize/unified` — a *separate*
  `/digitize/smart` endpoint exists in `routes.py` and a matching
  `digitizeSmart()` exists in `cadEngine.ts`, but **`digitizeSmart()` is
  never called from anywhere in the frontend** — fully dead pairing,
  distinct from the unified/CFG one).
- `crawl_to_dxf.py` (the other major entry point — bulk/automated
  digitization via the crawler) calls `/digitize/hybrid` directly (see
  earlier entries in this log) — never reaches `/digitize/unified` either.

**Net effect:** a substantial, real piece of engineering (furniture
grammar + self-critic auto-correction) is fully wired into exactly one
endpoint, which is reachable only by a manual UI toggle most users won't
touch by default, and is never reached at all by the automated crawl path.
Whether this should become the default engine mode, or get folded into
`/digitize/hybrid` so the crawl path benefits too, is a product decision —
flagging, not deciding.


## 2026-06-29 (continued audit) — Claude (Sonnet 4.6) — SECURITY: real OpenAI key in plaintext frontend env files + client-side calling pattern

**Status:** FLAGGED, HIGH PRIORITY. Not fixed — rotating/removing a live API
key is the user's call, not something to do silently mid-audit. Confirmed
NOT currently exposed via the live production site (see below), but the
underlying pattern is a real vulnerability if ever deployed any other way.

**What's there:** `frontend/.env` and `frontend/.env.production` both set
`VITE_OPENAI_API_KEY` to a real, live-looking OpenAI key (matches the key
seen earlier this session in the legacy `cad-digitizer-api` container's
environment). `frontend/services/ai.ts` and `frontend/services/agent.ts`
both read `import.meta.env.VITE_OPENAI_API_KEY` and call
`https://api.openai.com/v1/chat/completions` **directly from the browser**.
`agent.ts` even logs the key prefix to the browser console
(`console.log(... API_KEY.substring(0, 8) ...)`).

Any env var prefixed `VITE_` is intentionally public by Vite's design — it
gets statically inlined into the built JS bundle, readable by anyone who
opens dev tools or downloads the bundle file. An OpenAI key embedded this
way is fully extractable by any visitor and could be used to run up
unlimited charges on the account or for unrelated purposes.

**Why this isn't currently live on `cad.abcx124.xyz`:** `.dockerignore`
correctly excludes `**/.env` and `**/.env.*` from the Docker build context,
so `Dockerfile.frontend`'s `npm run build` (the one that actually produces
what's deployed) never sees these files — `import.meta.env.VITE_OPENAI_API_KEY`
resolves to `undefined` in the real deployed bundle. Verified this is also
not a git-history leak: `git log --all -- frontend/.env frontend/.env.production`
returns nothing — these files have never been committed.

**But:** the key still sits in cleartext on disk in 2 local files right now,
and I found it because a stray local (non-Docker) `npm run build` baked it
into an untracked `frontend/dist/` folder — confirming the leak path is real
whenever anyone builds the frontend outside the Docker pipeline (local
testing, a different host, a different deploy method, accidentally sharing
`dist/`). The architecture itself — client-side code calling OpenAI directly
with an embedded key — is the root problem, not just this one instance of
it; the *server-side* OpenAI integration in `python-worker` already exists
and does this correctly (key never leaves the server). `ai.ts`/`agent.ts`
look like an older/parallel implementation that should probably be removed
entirely in favor of the server-side path, not just have its key swapped.

**Confirmed NOT dead code:** `App.tsx:22` imports `runCadAgent`,
`runCadVerifier`, `runCadCorrector` from `agent.ts`, and calls all three from
an active user-triggered flow (`App.tsx` ~line 159-170). This is a live,
reachable feature path, not legacy/unused code — strengthens the case for
actually removing it rather than just rotating the key and leaving the
pattern in place.

**Recommend:** rotate this key regardless (it's been in 2 plaintext files,
can't fully rule out other exposure I haven't checked — e.g. IDE
auto-sync, backup tools, other local clones), and decide whether
`ai.ts`/`agent.ts`'s direct-from-browser OpenAI calls are still used by
anything live or can be deleted outright.


## 2026-06-29 (continued audit) — Claude (Sonnet 4.6) — Qdrant similarity search: data side is genuinely live, no UI entry point

**Status:** DOCUMENTED. Not a bug — a missing frontend feature.

Different shape from the other findings above: `generate_and_index_embedding()`
genuinely runs automatically (non-fatal try/except at `routes.py` ~line 1075)
after every successful digitize that goes through `_dispatch_furniture()`,
indexing the generated DXF's geometry into Qdrant for future similarity
search. **Verified live data accumulating**: `GET
http://104.248.225.250:16333/collections/cad_geometry` → `points_count: 9`
right now, from real digitize calls this session.

The retrieval side (`GET /products/search/similar`, `GET
/products/search/semantic` → `app/backend/product_search.py` →
`embedding_service.search_similar()`) is also fully implemented and would
work if called. **Nothing in the frontend calls either endpoint** — grepped
all of `frontend/` for `products/search`, zero hits. So: real accumulating
data, real working search code, zero way for an actual user to trigger a
"find similar furniture" search through the app. Lowest-effort genuinely
useful feature to surface in this whole audit, if someone wants to wire up
a UI for it — the hard part (indexing pipeline) already works.

Also noted in passing: `indexed_vectors_count: 0` despite `points_count: 9` —
expected at this scale (HNSW indexing has a minimum threshold before it
kicks in; full-scan search works fine for low point counts), not a bug.


## 2026-06-29 (continued audit) — Claude (Sonnet 4.6) — reference-ratio solver also never activated; recurring pattern identified

**Status:** DOCUMENTED. Not fixed (investigation-only pass per user instruction).

`app/backend/reference_ratio_solver.py` (`solve_missing_dimensions`/
`get_reference_ratios`, genuinely called from live routes — confirmed via
grep, unlike `match_detected_to_reference` in the same file, which is
imported at routes.py:27 but **never called anywhere** — dead import) uses
`DEFAULT_RATIOS`, a hardcoded dict of typical furniture proportions, NOT the
live `ProductReference`/`GeometryProfile` Postgres tables the crawler
populates. It optionally merges in `resources/calibration_ledger.json` if
present — **that file does not exist.**

It's supposed to be produced by `scripts/auto_calibrate_from_crawled.py`
("THE GENIUS INSIGHT" — runs digitize on each of 259 cataloged products with
known ground-truth dimensions, computes per-type correction factors, writes
the ledger). The input data is real and substantial:
`resources/product_catalog/_registry.json` genuinely has 259 entries. The
script has clearly **never been run** — its only output file doesn't exist
anywhere in the repo or on the VPS.

### Pattern across this whole audit

Every "learning loop" found so far follows the same shape: real, often
well-designed logic + real input data sitting ready, but the **one
connecting step that would activate it** (a DB table, a cron install, a
one-time batch script run) was never completed:

| Loop | Logic exists? | Data exists? | Activated? |
|---|---|---|---|
| Proportion ledger (`component_proportions`) | Yes, well-designed | N/A (accumulates from use) | **Now yes** (table fixed this session) |
| Comparison scoring (`comparison_results`) | Yes (scoring formula has its own bug, see above) | N/A | **Now yes** (table fixed this session) |
| Auto-calibration (`digitizer_parameters` + cron) | Yes, self-provisioning | Now yes (comparison_results populated) | **No** — cron never installed |
| Reference ratio ledger (`calibration_ledger.json`) | Yes | Yes — 259 real cataloged products | **No** — batch script never run |

Worth treating as one decision rather than four separate ones: is someone
going to run `auto_calibrate_from_crawled.py` once and install the cron, or
should these be re-architected to trigger automatically (e.g. off the queue
worker, after N digitizations) instead of depending on someone remembering
to run a script / install a cron entry by hand?


## 2026-06-29 (continued audit) — Claude (Sonnet 4.6) — auto-calibration loop: well-designed, self-healing, but never actually activated

**Status:** DOCUMENTED. Not a code bug — an operational gap (missing cron
install). Low risk either way since it self-heals once comparison data exists.

Traced the full chain: `app/backend/vision.py` already calls
`get_canny_thresholds()` from `app/services/digitizer_config.py` instead of
hardcoding OpenCV values — genuinely well-architected, designed so adjusted
parameters take effect on the next `/digitize` call without a restart.
`get_param()`/`_load_from_db()` read from a `digitizer_parameters` table that
**doesn't exist** — but unlike the other missing tables in this log,
`training_feedback.py`'s `save_parameter_state()` has its own inline
`CREATE TABLE IF NOT EXISTS digitizer_parameters (...)`, so it self-provisions
on first successful calibration write. It just never fired, because
`comparison_results` (now fixed, see entries above) was empty/non-existent
the whole time — no error data, nothing to calibrate from. `get_param()`'s
read path already fails gracefully (catches the missing-table exception,
falls back to `_DEFAULTS`, never crashes digitize) — this part doesn't need
a code fix.

**What's actually missing:** `scripts/daily-analysis.sh` is a real,
functional script that queries `comparison_results`, computes trends, and
calls `POST /api/calibration/apply` automatically — but only if its
documented cron entry (`0 2 * * * /opt/cad-digitizer/scripts/daily-analysis.sh`)
is actually installed. Checked the VPS: **it isn't.** `crontab -l` shows only
unrelated SuperRoo entries; `/var/log/cad-reports` (the script's own output
dir) doesn't exist, confirming it has never run. So: calibration is
self-correcting in design, but in practice has only ever run if someone
manually hit `/calibration/apply` — never on its own.

**Not fixed yet** — installing a cron job on shared production
infrastructure is exactly the kind of change that should get explicit
sign-off first (same reasoning as the DB schema changes above), not bundled
into a docs-only audit pass. Flagging for a decision: install the cron as
documented, or trigger calibration differently (e.g. from the queue worker
after N comparisons accumulate)?


## 2026-06-29 (later still) — Claude (Sonnet 4.6) — comparison_agent overall_score is misleading + coffee table DXF still missing a view

**Status:** DOCUMENTED, NOT YET FIXED.

### Finding 1: `/compare`'s `overall_score` doesn't reflect actual dimension accuracy

`app/services/comparison_agent.py` does three real checks (edge overlap via
Canny + raster diff, entity count match, dimension deviation vs. page's real
stated dimensions — this last one is correctly computed and stored in
`dimension_comparisons`/`dimension_deviation_pct`). The bug is in the
weighting at ~line 552-557:

```python
dim_reliability = max(0.5, 1.0 - min(result.dimension_deviation_pct, 100) / 100)
dim_score = max(0.99, dim_reliability) if has_entity_match else max(0.8, dim_reliability)
```

Whenever `has_entity_match` (entity_match_score > 0.5, true almost always
once classification works), `dim_score` is **floored at 0.99 regardless of
how large `dimension_deviation_pct` actually is**. Verified live: every
`/crawl-to-dxf` test this session showed `overall_score` ≈ 0.92 even when
`dimension_deviation_pct` was 67% (Tangerie) or 51% (Melina) — actually quite
inaccurate dimensions, masked by a score that looks like a near-pass. The raw
`dimension_deviation_pct` is fine and worth reading directly; just don't
trust `overall_score` as a proxy for it until this weighting is fixed (the
`max(0.99, ...)` / `max(0.8, ...)` should just be `dim_reliability` itself).

### Finding 2: coffee table's downloadable DXF still has only 1 view (Top), SVG preview now has 2

Earlier this session I added a FRONT VIEW to `build_coffee_table_model()` in
`drawing_builders.py` (the SVG *preview* builder) while fixing the Melina
case. I never touched `save_coffee_table()` in `dxf_exporter.py` (the actual
DXF file builder) — it still only emits a TOP VIEW. Confirmed by grepping
every `_add_mtext(msp, '...VIEW'` call against every `save_*` function in
`dxf_exporter.py`:

| Type | DXF views |
|---|---|
| `save_rectangular_table` | Top, Front, Side, Isometric (4) |
| `save_console_table`, `save_office_desk` | Top, Front, Side (3) |
| `save_asymmetric_pedestal_table` | Top, Front Elevation, Side Elevation (3) |
| `save_round_pedestal_table`, `save_oval_pedestal_table`, `save_reception_counter`, `save_armchair`, `save_bar_stool`, `save_bench_chaise`, `save_ottoman` | Top, Front (2) |
| `save_cabinet` (+ `save_sideboard`/`save_tv_console`, which call it directly), `save_sofa`, `save_dining_chair`, `save_wardrobe`, `save_bed_headboard`, `save_lounge_chair` (calls `save_armchair`) | Front only (1) |
| `save_rug`, `save_stone_slab` | Top only (1 — correct, flat items) |
| **`save_coffee_table`** | **Top only (1) — same gap as before my preview-only fix** |

Net effect: what a user downloads for a coffee table still doesn't match
what the in-browser preview now shows. Same fix pattern as the preview side
(see commit `7e4e234`) needs porting to `dxf_exporter.py`.

### Finding 3 (follow-up investigation, same session): "Front only" types never visually dimension depth at all — confirmed real gap, not a design choice

Checked `save_cabinet`, `save_sofa`, `save_dining_chair`, `save_wardrobe`
directly: all four accept `depth_cm` as a real parameter, print it into the
title block text (e.g. "Cabinet 100x50x180"), but **never call
`_add_dimension()` for it** — only Width and Height get drawn dimension
lines. There is no Top or Side view to show depth geometrically either
(that's Finding 2's table above). `save_bed_headboard` is arguably a
legitimate exception — it doesn't even accept `depth_cm` (headboards are
thin flat panels, ~5cm "depth" is really just thickness; a side view of that
wouldn't be very useful) — but cabinet/sofa/dining_chair/wardrobe have
substantial depths (45-90cm) that genuinely matter for manufacturing.

**Confirmed user-facing symptom:** the frontend's `_component_schema()`
(`routes.py` ~line 370+) exposes a working "Depth" slider for cabinet and
sofa (and presumably dining_chair/wardrobe — not individually re-checked,
same code pattern). A user can drag it, the value reaches `save_cabinet()`/
`save_sofa()` as a real argument — **but the rendered drawing looks
identical for any depth value**, since nothing ever visualizes it. Anyone
testing "does the depth slider do anything" would see no.

**Real fix** (not yet done, scoped but not started): add a Top View (for
cabinet/sofa/wardrobe — shows width × depth footprint) or Side View (for
dining_chair — shows depth × height profile) to each `save_*` function in
`dxf_exporter.py`, with a real `_add_dimension()` call for depth. Same
pattern needs to land in the matching `build_*_model()` SVG builders in
`drawing_builders.py` too, given Finding 2 already shows those two files
drift out of sync with each other if only one gets fixed. ~5 functions ×
2 files = up to 10 edits. User has not yet decided whether to do this now,
do a subset, or leave it logged for later — asked, awaiting decision as of
this entry.

---

## 2026-06-29 (later) — Claude (Sonnet 4.6) — Production DB was missing almost its entire custom schema

**Status:** FIXED, applied live to production Postgres (user-approved).

**Finding:** the live `cad_reference_library` Postgres database only had the 3
Prisma-managed tables (`GeometryProfile`, `ProductReference`, `ReferenceAsset`).
**None** of the 10 tables in `scripts/db-init/01-init-schema.sql` existed —
`digitizer_sessions`, `digitizer_results`, `feedback_learnings`,
`proportion_ledger`, `drawing_history`, `validation_results`,
`training_exports`, `product_families`, `chat_sessions`, `comparison_results`.
Postgres only runs `docker-entrypoint-initdb.d` scripts on first volume
creation — this volume predates the schema file (or predates it being
updated), so it never ran.

**Worse:** `app/backend/brain_sync.py` ("Central Brain" cross-photo learning:
`record_proportion`/`get_proportion_estimate`/`record_drawing`/
`record_correction`/`record_material`/`get_material_suggestions` — all
genuinely called from live routes in `routes.py`, confirmed via grep) depends
on a **second, separate, never-applied** schema file:
`backend-python/scripts/create_ml_tables.sql`. That file defines
`component_proportions` (the proportion-ledger table - didn't exist anywhere),
plus `furniture_corrections`, `material_library`, `style_presets`, AND its own
versions of `chat_sessions`/`drawing_history` with **different, incompatible
column names** than `01-init-schema.sql`'s versions of the same table names.

Every single call to `record_proportion()` / `get_proportion_estimate()` etc.
has been silently failing since this feature was built — `brain_sync.py`'s
`_execute()` catches all exceptions and only `print()`s them to container
stdout (line 55-68), never surfaced anywhere a human would see it. The
"cross-photo proportion blending" logic built and tested earlier this session
(`_ledger_blend()` in routes.py, weighted by `sample_count`) has **never**
actually had real prior data to blend with — every call fell through to "no
prior data" silently, every time, indefinitely.

**Fix applied (in this order, both user-approved):**
1. Ran `scripts/db-init/01-init-schema.sql` → created the missing 10 tables.
2. Discovered the `chat_sessions`/`drawing_history` schema conflict (verified
   both tables were still empty — created minutes earlier — before touching
   them). `DROP TABLE chat_sessions, drawing_history;` then ran
   `backend-python/scripts/create_ml_tables.sql`, which recreates both with
   the columns `brain_sync.py` actually expects, plus adds
   `component_proportions`, `furniture_corrections`, `material_library`,
   `style_presets`.
3. Verified live: `get_proportion_estimate()` now returns cleanly (`None`,
   since the table is empty — no error) instead of throwing a swallowed
   `relation does not exist` error.

**Verify before assuming any "Central Brain" feature is dead:** check both
schema files (`scripts/db-init/01-init-schema.sql` at repo root AND
`backend-python/scripts/create_ml_tables.sql`) actually got applied to
whatever Postgres instance you're pointed at — `\dt` in psql, don't trust the
SQL files' existence as proof the tables exist.

**Separate, still-unresolved gap:** `app/backend/style_presets.py` (JSON
files in `memory/user_preferences/presets/`) and `brain_sync.py`'s
`save_preset`/`load_preset`/`list_presets`/`delete_preset` (Postgres
`style_presets` table) are two **completely independent** implementations of
the same feature. Routes.py's `/preset` endpoints use only the file-based one
(`app/backend/style_presets.py`) — `brain_sync.py`'s preset functions are
dead code, never imported into routes.py. Not fixed; just documented so
nobody "fixes" the Postgres path thinking it's the active one.

---


This file exists because multiple agents/sessions are committing to this repo
concurrently (sometimes within minutes of each other), and several fixes have
been silently undone or duplicated as a result. **Read this before touching
`backend-python/app/services/crawl_to_dxf.py`, `backend-python/app/api/routes.py`,
or `backend-python/app/backend/drawing_builders.py`.**

Append new entries at the top. Don't delete old entries — mark them resolved instead.

---

## 2026-06-29 — Claude (Sonnet 4.6) — crawl_to_dxf.py regression + dead code

**Status:** IN PROGRESS — fix not yet committed.

### Finding 1: `real_h`/`real_d` `UnboundLocalError` risk (REGRESSION)

`crawl_and_digitize()` in `crawl_to_dxf.py` references `real_h`/`real_d` outside
the `if page_dims:` block (in the `params = {...}` section ~line 614-619). They
must be initialized to `None` *before* that `if` block, not inside it — if a
product page has no parseable dimensions at all (`page_dims` is falsy), the
variables are never defined and the function crashes with `NameError`.

This was fixed once (commit `7e4e234`, moved init above the `if`), then
**reintroduced** by commit `f1407c6` ("fix: shape-based template dispatch +
real_d bug fix") which moved the init back inside the `if page_dims:` block.
Ironic given the commit's own message claims to fix a `real_d` bug.

**Fix:** keep `real_h = None` / `real_d = None` *before* `if page_dims:`.

### Finding 2: Shape-based dispatch (`f1407c6`) doesn't affect the rendered CAD output (DEAD CODE)

Commit `f1407c6` added URL-slug keyword detection (`round`/`oval`/`square`/
`pedestal`) that reassigns the local `furniture_type` variable inside
`crawl_and_digitize()`. Intent: make a crawled "round dining table" actually
render round instead of rectangular.

**This has no effect on the generated DXF/SVG.** `furniture_type` here is only
read later by `verify_dimensions()` (hallucination check) and the skeleton
preview — it is **never** passed to `/api/digitize/hybrid`'s `params` dict.
That decoupling was intentional (see commit `1ca5074`'s comment block at
~line 602-612): forwarding the crawl category as an override used to bypass
the *real* image classifier entirely, which was a worse bug (every crawled
"table" rendered as unclassified noise). Re-wiring `furniture_type` back into
`params` would reintroduce that regression.

Also: the slug keyword map has no entry for `coffee_table` at all, so it
wouldn't have helped the Melina coffee table case even if it were wired up.

**Verified live (2026-06-29):** crawling `melina-coffee-table` still renders
a `<circle>` top view, not a rectangle. Root cause is `build_coffee_table_model`
/ `save_coffee_table` in `drawing_builders.py` / `dxf_exporter.py` — they have
**no shape parameter at all**, always draw a circle. Real fix needs:
1. A signal for actual top shape (round vs rect vs square) — AI vision's
   `visual_base_estimate` currently returns `{}` for coffee tables, it isn't
   asked about top shape.
2. `build_coffee_table_model(..., shape="round"|"rectangular")` branching on
   that signal, threaded through `_dispatch_furniture`'s `coffee_table` branch.

**Not fixing the shape-detection feature in this pass** — scoping to the two
items above (revert the regression, remove/clarify the dead slug-detection
code) plus documenting the real fix needed for whoever picks it up next.

### Other directory move noted (not a bug, just a heads-up)

`backend-python/resources/furniture_template_graphs/` was relocated to the
top-level `resources/furniture_template_graphs/` (commit range ending
`d373d6f`). This is **safe** — `Dockerfile.python-worker` already has a
separate `COPY resources/ /app/resources/` step, and `template_loader.py`'s
path resolution lands on the same `/app/resources/...` path either way.
Verified live: `/py-api/templates` still returns 18 templates post-deploy.
If you're auditing `template_loader.py`'s `TEMPLATE_DIR` constant and it
looks wrong relative to the *source* tree, it's not — check the Docker build
context, not just the repo layout.

---

## How to avoid stepping on concurrent agents

- Before editing `crawl_to_dxf.py` / `routes.py` dispatch branches /
  `drawing_builders.py`: `git log -5 -- <file>` first, someone may have just
  touched it.
- This repo has had pushes land mid-edit more than once this session (file
  changes appearing between a `Read` and an `Edit` call). If an edit tool
  reports "file modified since read," re-read before retrying — don't assume
  your in-memory understanding is still accurate.
- Production deploys go through `/opt/cad-digitizer` on the VPS
  (`104.248.225.250`), separate from this local working tree. A commit being
  pushed does **not** mean it's live — it needs `git pull` + `docker compose
  build <service>` + `docker compose up -d <service>` on the VPS too. Several
  bugs in this log were sitting fixed-in-source but un-rebuilt for hours.
