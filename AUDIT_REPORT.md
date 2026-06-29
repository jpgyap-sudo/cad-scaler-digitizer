# Senior Auditor Report — Codebase Wiring & Orphan Detection

**Date:** 2026-06-29
**Scope:** Full codebase audit following 7-phase methodology
**Thoroughness:** Very thorough

---

## Phase 1: Resource → Code Wiring

### Summary: 27 JSON resource files — 27 reported as ORPHAN by basename check

**Severity: Low (false positive)**

The SKILL.md check searches for each filename being opened/read by exact basename string. Every resource file's name never appears literally in Python/JS/TS code. However, this is a **false positive** because code loads them by **directory iteration** (`glob("*.json")`):

| Loader File | Directory Loaded | Mechanism |
|---|---|---|
| `backend-python/app/backend/template_selector.py:17` | `resources/furniture_templates/` | `TEMPLATE_DIR.glob("*.json")` |
| `backend-python/app/resource_engine/template_loader.py:8` | `resources/furniture_template_graphs/` | `self._root.glob("*.json")` |
| `backend-python/app/resource_engine/template_graph/template_library.py:10` | `resources/furniture_template_graphs/` | `self.root.glob("*.json")` |
| `backend-python/app/furniture_intelligence/services/template_matcher.py:8` | `resources/furniture_templates/` | Path reference |
| `backend-python/scripts/generate_template_graphs.py:9` | `resources/furniture_template_graphs/` | Path reference |

**All 27 files ARE loaded at runtime.** The SKILL.md's basename-matching heuristic is too narrow for directory-iteration patterns. No action needed.

---

## Phase 2: Module → Import Wiring

### Summary: 62 ZOMBIE modules defined but never imported

**Severity: Medium to High**

The following Python modules exist in the filesystem but are never imported by any other module. They are either dead code, entry points (scripts), or unconnected library code:

#### `backend-python/app/` — Core app modules (CRITICAL):
| Module | File | Risk |
|---|---|---|
| `app.productionization.models` | `backend-python/app/productionization/models.py` | High — core data model, not imported |
| `app.productionization.storage` | `backend-python/app/productionization/storage.py` | High — storage layer, not imported |
| `app.productionization.registry` | `backend-python/app/productionization/registry.py` | High — registry, not imported |
| `app.productionization.config` | `backend-python/app/productionization/config.py` | High — config, not imported |
| `app.productionization.jobs` | `backend-python/app/productionization/jobs.py` | High — jobs, not imported |
| `app.productionization.main` | `backend-python/app/productionization/main.py` | Medium — entry point |
| `app.productionization.pipeline.orchestrator` | `backend-python/app/productionization/pipeline/orchestrator.py` | High — pipeline orchestrator |
| `app.productionization.pipeline.adapters` | `backend-python/app/productionization/pipeline/adapters.py` | High — pipeline adapters |
| `app.productionization.review.review_service` | `backend-python/app/productionization/review/review_service.py` | High — review service |
| `app.queue_worker` | `backend-python/app/queue_worker.py` | Medium — entry point for queue worker |
| `app.main` | `backend-python/app/main.py` | Medium — FastAPI entry point |

#### `backend-python/app/services/` — Service modules (ZOMBIE):
| Module | File | Risk |
|---|---|---|
| `app.services.comparison_agent` | `backend-python/app/services/comparison_agent.py` | Medium |
| `app.services.crawl_processor` | `backend-python/app/services/crawl_processor.py` | High |
| `app.services.crawl_to_dxf` | `backend-python/app/services/crawl_to_dxf.py` | High |
| `app.services.digitizer_config` | `backend-python/app/services/digitizer_config.py` | High |
| `app.services.embedding_service` | `backend-python/app/services/embedding_service.py` | Medium (maybe imported dynamically) |
| `app.services.engineering_agent` | `backend-python/app/services/engineering_agent.py` | Medium |
| `app.services.freecad_exporter` | `backend-python/app/services/freecad_exporter.py` | Medium |
| `app.services.hallucination_verifier` | `backend-python/app/services/hallucination_verifier.py` | Medium |
| `app.services.ml_engine` | `backend-python/app/services/ml_engine.py` | Medium |
| `app.services.pdf_exporter` | `backend-python/app/services/pdf_exporter.py` | Medium (try/except import in routes.py) |
| `app.services.pipeline_service` | `backend-python/app/services/pipeline_service.py` | Medium |
| `app.services.training_feedback` | `backend-python/app/services/training_feedback.py` | Medium |
| `app.services.validation_service` | `backend-python/app/services/validation_service.py` | Medium |

#### `backend-python/app/resource_engine/` — Almost everything is ZOMBIE:
| Module | File | Risk |
|---|---|---|
| `app.resource_engine.cloud_vision` | `backend-python/app/resource_engine/cloud_vision.py` | High — cloud vision feature |
| `app.resource_engine.constraint_solver` | `backend-python/app/resource_engine/constraint_solver.py` | High — constraint solver |
| `app.resource_engine.db_persistence` | `backend-python/app/resource_engine/db_persistence.py` | High — DB persistence |
| `app.resource_engine.estimator` | `backend-python/app/resource_engine/estimator.py` | High — estimator |
| `app.resource_engine.feedback` | `backend-python/app/resource_engine/feedback.py` | Medium |
| `app.resource_engine.library` | `backend-python/app/resource_engine/library.py` | High — ResourceLibrary |
| `app.resource_engine.matcher` | `backend-python/app/resource_engine/matcher.py` | High — matcher |
| `app.resource_engine.ontology` | `backend-python/app/resource_engine/ontology.py` | Medium |
| `app.resource_engine.pipeline_orchestrator` | `backend-python/app/resource_engine/pipeline_orchestrator.py` | High |
| `app.resource_engine.quality` | `backend-python/app/resource_engine/quality.py` | Medium |
| `app.resource_engine.retrieval` | `backend-python/app/resource_engine/retrieval.py` | High — retrieval module |
| `app.resource_engine.retrieval_index` | `backend-python/app/resource_engine/retrieval_index.py` | High |
| `app.resource_engine.schema` | `backend-python/app/resource_engine/schema.py` | High |
| `app.resource_engine.template_loader` | `backend-python/app/resource_engine/template_loader.py` | High — template loader not loaded |
| `app.resource_engine.template_resolver` | `backend-python/app/resource_engine/template_resolver.py` | High |
| `app.resource_engine.validation_gate` | `backend-python/app/resource_engine/validation_gate.py` | High |

#### `backend-python/app/resource_engine/` subpackages (ZOMBIE):
All modules in: `closed_loop/`, `fusion/`, `handoff/`, `manufacturing/`, `param_pack/`, `reasoning/`, `template_graph/`, `validation/`, `production/` — 30+ modules that are defined but never imported by any external module. These constitute a large parallel architecture that appears to be **built but not wired**.

#### `backend-python/scripts/` (expected zombies — these are standalone entry points):
`appends_products.py`, `append_product_routes.py`, `e2e_pipeline.py`, `generate_batch_fixtures.py`, `generate_template_graphs.py`, `scrape_furniture.py`, `test_cad_intel_fixture.py`, `test_product_catalog.py`, `test_templates.py`, `train_classifier.py`, `productionization/demo_direct_pipeline.py`, `productionization/demo_generate.py`

---

## Phase 3: Function → Caller Wiring

### DISPATCH TABLE vs SAVE FUNCTIONS

**FURNITURE_ADJUST_DISPATCH** (routes.py:2612-2627) has **14 entries** covering 13 unique `save_*()` functions.

**Notable: 13 `save_*()` functions in dxf_exporter.py are NOT in the dispatch table** but ARE called directly from routes.py:

| Function | Defined At | Called At | Dispatch Coverage |
|---|---|---|---|
| `save_sectional` | dxf_exporter.py:1694 | routes.py:1158 | NOT IN DISPATCH |
| `save_armchair` | dxf_exporter.py:1992 | routes.py:1048 | NOT IN DISPATCH |
| `save_bar_stool` | dxf_exporter.py:2053 | routes.py:1058 | NOT IN DISPATCH |
| `save_bench_chaise` | dxf_exporter.py:2101 | routes.py:1069 | NOT IN DISPATCH |
| `save_ottoman` | dxf_exporter.py:2153 | routes.py:1079 | NOT IN DISPATCH |
| `save_rug` | dxf_exporter.py:2201 | routes.py:1089 | NOT IN DISPATCH |
| `save_stone_slab` | dxf_exporter.py:2242 | routes.py:1098 | NOT IN DISPATCH |
| `save_wall_panel` | dxf_exporter.py:2283 | routes.py:1108 | NOT IN DISPATCH |
| `save_lounge_chair` | dxf_exporter.py:2326 | routes.py:1117 | NOT IN DISPATCH |
| `save_sideboard` | dxf_exporter.py:2333 | routes.py:1123 | NOT IN DISPATCH |
| `save_tv_console` | dxf_exporter.py:2340 | routes.py:1129 | NOT IN DISPATCH |
| `save_hero_view` | dxf_exporter.py:1924 | crawl_to_dxf.py:871 | NOT IN DISPATCH |
| `save_generic` | dxf_exporter.py:1667 | routes.py (32 call sites) | NOT IN DISPATCH |

**Impact:** These types bypass the dispatch mechanism. The `/adjust` endpoint uses `_get_adjust_fn()` which only returns functions from the dispatch table. Any type not in the dispatch table will return `(None, None)` from `_get_adjust_fn()`, meaning **adjust operations will silently fail** for: sectional, armchair, bar_stool, bench_chaise, ottoman, rug, stone_slab, wall_panel, lounge_chair, sideboard, tv_console, hero_view.

### CRITICAL BUG: Dispatch import failure kills ALL types

At routes.py:2628:
```python
except ImportError as e:
    print(f"[Adjust] Import failed: {e}")
```

If **any single** import of the 13 save_ functions or 13 build_ functions fails, the entire `FURNITURE_ADJUST_DISPATCH.update({...})` is skipped, and **ALL 14 dispatch entries are unavailable**. This is a fragile pattern — one missing function disables every type.

---

## Phase 4: Frontend Component → Render Wiring

### Summary: All 24 components are connected. No orphans.

| Component | File | Imported By |
|---|---|---|
| AnalyticsPage | `frontend/components/AnalyticsPage.tsx` | App.tsx |
| BrainStats | `frontend/components/BrainStats.tsx` | e2e.spec.ts |
| CadCanvas | `frontend/components/CadCanvas.tsx` | App.tsx |
| CadConfidenceLegend | `frontend/components/CadConfidenceLegend.tsx` | ReviewPanel.tsx, confidenceHeatmap.ts |
| CalibrationPage | `frontend/components/CalibrationPage.tsx` | App.tsx |
| Canvas | `frontend/components/Canvas.tsx` | CadCanvas.tsx |
| ChatBox | `frontend/components/ChatBox.tsx` | e2e.spec.ts |
| ConfidencePanel | `frontend/components/ConfidencePanel.tsx` | App.tsx, confidenceHeatmap.ts |
| CrawlInput | `frontend/components/CrawlInput.tsx` | App.tsx |
| DXFPreview | `frontend/components/DXFPreview.tsx` | App.tsx |
| EngineeringPage | `frontend/components/EngineeringPage.tsx` | App.tsx |
| HistoryPage | `frontend/components/HistoryPage.tsx` | App.tsx |
| ImprovementsPage | `frontend/components/ImprovementsPage.tsx` | App.tsx |
| InteractiveSvgPreview | `frontend/components/InteractiveSvgPreview.tsx` | App.tsx |
| NavBar | `frontend/components/NavBar.tsx` | App.tsx |
| PipelineProgress | `frontend/components/PipelineProgress.tsx` | App.tsx, ReviewPanel.tsx |
| PipelineUpload | `frontend/components/PipelineUpload.tsx` | PipelineProgress.tsx, ReviewPanel.tsx, App.tsx |
| ResourcesPage | `frontend/components/ResourcesPage.tsx` | App.tsx |
| ReviewPanel | `frontend/components/ReviewPanel.tsx` | App.tsx |
| SliderPanel | `frontend/components/SliderPanel.tsx` | App.tsx |
| SmartConfirmations | `frontend/components/SmartConfirmations.tsx` | App.tsx |
| TechStackModal | `frontend/components/TechStackModal.tsx` | App.tsx |
| TemplatesPage | `frontend/components/TemplatesPage.tsx` | App.tsx |
| WorkflowGuide | `frontend/components/WorkflowGuide.tsx` | App.tsx |

**Note:** `BrainStats` and `ChatBox` are only imported in e2e.spec.ts (test file), not by any production component. If these are meant to be rendered in the app, they are effectively unreachable at runtime.

---

## Phase 5: Data Flow Tracing

### _component_schema coverage gaps

**Types in dispatch but with NO hardcoded _component_schema entry** (rely on dynamic `_schema_from_template()` fallback):
- `oval_pedestal_table` — routes.py:2624 dispatch
- `console_table` — routes.py:2625 dispatch
- `office_desk` — routes.py:2626 dispatch

The dynamic fallback (`_schema_from_template`, routes.py:328) loads templates from JSON files and must match `template_id` exactly. If no template is found, `_component_schema()` returns `None`, which means no sliders are shown in the UI for these types.

**Types with _component_schema but NO dispatch entry:**
- `coffee_table_round`, `bar_stool`, `bench_chaise`, `ottoman_pouf`, `wall_panel_fluted`, `bed`, `sectional`, `outdoor_dining_set`, `office_chair`

These can show sliders in the UI but adjustments won't work through the dispatch mechanism.

### Parameter usage verification

Checked `save_cabinet(width_cm, depth_cm, height_cm)` at dxf_exporter.py:683:

| Parameter | Used? | Where |
|---|---|---|
| `width_cm` | YES | Front view (line 695), Top view (line 736), Isometric (line 754) |
| `depth_cm` | YES | Top view (line 737), Side view (line 758), Isometric (line 753) |
| `height_cm` | YES | Front view (line 696), Isometric (line 754) |

All parameters are used. No silent parameter ignore detected for this function.

---

## Phase 6: Silent Failure Check

### SILENT IMPORT FAILURES (25 instances)

Feature-disabling imports inside try/except blocks — if any dependency is missing, the feature silently disappears:

| File:Line | Import | Risk |
|---|---|---|
| `routes.py:309` | `from app.services.ml_engine import get_feedback_count` | ML feedback silently unavailable |
| `routes.py:706` | `from app.backend.brain_sync import record_drawing` | Drawing history silently disabled |
| `routes.py:883` | `from app.backend.scale_solver import compute_scale` | Scale solving silently disabled |
| `routes.py:906` | `from app.backend.dimension_validator import check_round_pedestal_proportions` | Validation silently disabled |
| `routes.py:2570` | `from app.backend.svg_exporter import drawing_to_svg` | SVG export silently disabled |
| `routes.py:2985` | `from app.services.pdf_exporter import export_pdf_shop_drawing` | PDF export silently disabled |
| `routes.py:3449` | `from app.backend.chat_agent import chat_with_agent` | Chat agent silently disabled |
| `routes.py:4682` | `from app.backend.svg_skeleton import generate_skeleton` | SVG skeleton silently disabled |
| `routes.py:2628` | **FULL dispatch table import** | **ALL 14 types silently disabled** |
| `main.py:83` | `from app.services.embedding_service import init_collection` | Embedding service silently disabled |
| `main.py:91` | `from app.resource_engine.db_persistence import init_db` | DB persistence silently disabled |
| `pipeline_service.py:79` | `from app.resource_engine.cloud_vision import CloudVisionFeatureSet` | Cloud vision silently disabled |
| `crawl_to_dxf.py:849` | `from app.backend.product_classifier import enrich_dna_from_crawl` | Product enrichment silently disabled |

### SILENT `except: pass` BLOCKS (47 instances)

Blocks that catch exceptions and silently swallow them with `pass`:

| File | Lines with `except.*: pass` | Risk |
|---|---|---|
| `routes.py` | 380, 2123, 2567, 3011, 3371, 4135 | High — hides failures in critical routes |
| `dxf_exporter.py` | 33, 42, 46, 106, 139, 153, 232, 1680, 1761, 1767, 1774 | Medium — hides DXF generation failures |
| `extents_updater.py` | 13, 19, 25, 33, 120 | Medium — hides extents update failures |
| `layer_manager.py:62` | 62 | Medium — hides layer setup failures |
| `feedback_learner.py` | 142, 217, 320 | Low |
| `fixture_generator.py:47` | 47 | Low |
| `ocr.py:290` | 290 | Low |
| `style_presets.py:92` | 92 | Low |
| `svg_skeleton.py:74` | 74 | Low |
| `chat_agent.py:231` | 231 | Medium |
| `retrieval_index.py:82,88` | 82, 88 (ImportError) | Medium |
| `db_persistence.py:32` | 32 | Medium |
| `assistant_monitor.py:85,544` | 85, 544 | Low |
| `crawl_to_dxf.py:444,449,844,860` | 444, 449, 844, 860 | Medium |
| `queue_worker.py:132` | 132 | Medium |
| `unified_router.py:281` | 281 | Medium |
| `accuracy_benchmark.py:596` | 596 | Low |
| `template_matcher.py:28` | 28 | Medium |

---

## Phase 7: Summary & Recommendations

### CRITICAL Findings

| # | Finding | Location | Fix |
|---|---|---|---|
| C1 | **Dispatch import failure crashes ALL types** | `routes.py:2628-2630` | Wrap each import individually, or move imports to module level |
| C2 | **13 save_ functions not in dispatch table** | `routes.py:1048-1159` | Add all 13 to `FURNITURE_ADJUST_DISPATCH.update({})` |
| C3 | **30+ resource_engine modules never imported** | `backend-python/app/resource_engine/` | Wire to entry point or remove if unused |

### HIGH Findings

| # | Finding | Location | Fix |
|---|---|---|---|
| H1 | `productionization/` package (8 modules) never imported | `backend-python/app/productionization/` | Wire to main.py or remove |
| H2 | `services/` package (13 modules) never directly imported | `backend-python/app/services/` | Verify if intended for deferred import |
| H3 | `_component_schema` missing for oval_pedestal_table, console_table, office_desk | `routes.py:385-580` | Add hardcoded entries or ensure JSON templates match |
| H4 | 25 deferred imports silently fail | `routes.py` multiple lines | Add logging/warnings on import failure |

### MEDIUM Findings

| # | Finding | Location | Fix |
|---|---|---|---|
| M1 | 47 `except Exception: pass` blocks | Various files | Add logging or narrow exception types |
| M2 | `BrainStats` and `ChatBox` only imported in e2e tests | `frontend/tests/e2e.spec.ts` | Import in App.tsx if meant for production |
| M3 | `save_hero_view` called from non-API service | `crawl_to_dxf.py:871` | Consider adding to dispatch table |

### LOW Findings

| # | Finding | Location | Fix |
|---|---|---|---|
| L1 | 12 scripts directory modules never imported | `backend-python/scripts/` | Expected — standalone entry points |
| L2 | 27 JSON resource files not matched by basename | `resources/` | False positive — loaded by directory iteration |
| L3 | 9 `_component_schema` entries without dispatch | `routes.py:385-580` | Add to dispatch or remove unused schemas |

---

## Count Summary

| Phase | Check | Items | Orphans | Severity |
|---|---|---|---|---|
| 1 | Resources loaded | 27 JSON files | 27 (false positive) | Low |
| 2 | Modules imported | ~180 Python files | 62 zombies | Medium/High |
| 3 | Functions called | 26 save_ + 14 build_ | 13 save_ not dispatched | High |
| 4 | Components rendered | 24 TSX files | 0 orphans | None |
| 5 | Data flow trace | 14 dispatch types | 3 missing schema | High |
| 6 | Silent failures | 25 imports + 47 pass blocks | 72 total | High |
