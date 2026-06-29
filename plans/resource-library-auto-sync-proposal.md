# Resource Library Auto-Sync — Feature Proposal

**Date:** 2026-06-29
**Status:** Proposed — No implementation yet
**Origin:** Findings #14 and #22 in `AUDIT_LOG.md` (orphaned `resource_engine`
subsystem; 7 of 11 `resources/` data categories deleted in commit `ef70fd0`
and never restored; `scene_graph` computed on every digitize call and
discarded)

---

## Problem

`resources/` (`construction_rules/`, `dimension_styles/`, `geometry/`,
`joinery/`, `manufacturers/`, `materials/`, `supports/`, `training/`) is
meant to back `ResourceLibrary`, which feeds a `scene_graph` build step that
runs on every `_dispatch_furniture()` call. Right now:

- 7 of these 8 categories are **completely empty** — deleted by an
  unrelated cleanup commit, never noticed, never restored. Nobody caught
  this for an entire session because `ResourceLibrary.load()` fails
  silently (skips missing/empty directories rather than erroring).
- Even when populated, this data was **hand-authored JSON files sitting in
  a folder** — no validation that they exist, no signal when they go
  missing, no connection to the live product's own accumulating knowledge
  (`component_proportions`, `material_library`, `furniture_corrections` —
  all genuinely populated now, fixed earlier this audit).
- The `scene_graph` this data feeds is computed on every request and **never
  read by anything** — wasted work regardless of whether the data exists.

The root cause isn't "someone deleted some files." It's that hand-maintained
reference JSON with no feedback loop is inherently fragile — it can silently
rot and nothing notices.

## Proposed Idea

Stop treating (part of) `resources/` as hand-authored. Make it a
**derived, auto-regenerating view of data the product already collects**,
so it can't silently go stale, and so accumulated real-world usage
(crawled products + user digitizations) directly improves future output
instead of dead-ending in a database table nobody reads.

A scheduled or queue-triggered job would:
1. Query `component_proportions`, `material_library`, `furniture_corrections`
   (weighted by `sample_count`/confidence, same logic `_ledger_blend()`
   already uses for the proportion ledger).
2. Write the result out as `resources/materials/*.json`,
   `resources/supports/*.json`, `resources/joinery/*.json` — the exact
   schema `ResourceLibrary.load()` already expects.
3. Bootstrap once from the existing 259-product catalog
   (`resources/product_catalog/_registry.json`), then keep enriching from
   live traffic.

## Scope — not all 8 categories qualify

| Category | Auto-sync candidate? | Why |
|---|---|---|
| `materials` | **Yes** | Directly maps to `material_library` (component → material → usage_count) |
| `supports` | **Yes** | Maps to `component_proportions` (leg/base/pedestal ratios by furniture type) |
| `joinery` | **Yes**, lower confidence | Maps to `furniture_corrections` if corrections include joinery-relevant fields; needs checking |
| `geometry` | Maybe | Unclear what currently populates this conceptually — needs scoping before committing |
| `manufacturers` | No | This is catalog/business metadata (who makes what), not a learned signal |
| `construction_rules` | **No** | The deleted files included `office_safety.json`/`residential_safety.json` — regulatory/business rules, not something a photo-derived ratio should ever overwrite |
| `dimension_styles` | **No** | Drafting/presentation convention (e.g. `metric_a3.json`), not usage-derived |
| `training` | No | Unclear purpose; audit separately before deciding |

Auto-sync should cover **materials + supports (+ maybe joinery)** only.
The rest stay hand-authored, or get explicitly retired if nobody can say
what they're for.

## Pros

- **Self-healing.** Can't silently go empty again the way `ef70fd0` caused
  — worst case, a re-run regenerates it from the database in seconds.
- **Closes a loop that's already half-built.** `_ledger_blend()`,
  `record_proportion()`, `record_material()` already exist and are
  correctly wired (verified earlier this audit) — this proposal reuses
  that exact machinery instead of building new ingestion.
- **Makes the discarded `scene_graph` computation worth keeping.** Right
  now it's compute-then-throw-away regardless of data; with real data
  behind it, surfacing it later (a validation panel, a "confidence" badge)
  becomes worth the engineering effort.
- **Compounds over time.** More digitizations → better-calibrated
  `materials`/`supports` data → better defaults for the next digitization,
  same flywheel the proportion ledger already demonstrates for round
  pedestal tables.

## Cons / Risks

- **Schema-mapping effort isn't zero.** Each category needs its own
  transform from raw DB rows to the JSON shape `ResourceLibrary` expects —
  not a generic "dump the table" script.
- **New operational surface.** Whatever triggers the sync (cron, or
  queue-worker-driven after N new samples) is one more job to monitor —
  and this codebase already has one calibration cron that was written but
  never actually installed (see `AUDIT_LOG.md`'s auto-calibration finding).
  Don't repeat that mistake silently.
- **Cold-start quality.** Early on, sample counts are low, so
  auto-generated entries need the same confidence weighting/floor the
  proportion ledger already applies — a brand-new component with 1 sample
  shouldn't overwrite a previously-good hand-authored entry outright.
- **Depends on an existing bug fix.** If the crawler's 259-product catalog
  is meant to be part of the bootstrap, `crawl_processor.py`'s Postgres
  persistence bug (`AUDIT_LOG.md` finding #12/#19 — inserts into tables
  that don't exist) needs fixing first, or the bootstrap runs on
  incomplete data.
- **Auto-generated vs. hand-authored conflicts.** If a category is ever
  partially hand-curated and partially auto-synced, need a clear rule for
  which wins (likely: hand-authored entries are pinned/protected, auto-sync
  only adds/updates entries it itself created).

## Suggested Sequencing

1. Restore the 7 deleted categories from git history (`ef70fd0^`) as a
   baseline — cheap, reversible, immediately unblocks `ResourceLibrary`.
2. Surface `scene_graph`/`scene_warnings` in the digitize response — the
   computation already happens, just needs picking out of `dispatch_extra`.
3. Run `auto_calibrate_from_crawled.py` once against the 259-product
   catalog now that `component_proportions`/`material_library` persist
   correctly — real bootstrap data without building anything new.
4. Build the auto-sync job for `materials`/`supports` (+ `joinery` if it
   scopes cleanly), gated on fixing `crawl_processor.py`'s persistence bug
   if the crawler is meant to feed it too.

Steps 1-3 are low-risk and validate that the underlying data is actually
good before investing in step 4's ongoing automation.
