# Audit Log — Multi-Agent Coordination

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
