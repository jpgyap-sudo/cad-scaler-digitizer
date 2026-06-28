# Gap Log — AI CAD Drafter → Furniture Engineering OS

This gap log tracks the evolution from an "AI CAD drafter" to a
"Furniture Engineering Operating System." Each gap represents a missing
capability that prevents the system from being more than a photo-to-DXF
converter.

See `docs/architecture-ai-cad-drafter.md` for current AI drafter design.
See `plans/furniture-engineering-os-architecture.md` for the full OS vision.

## Strategic gaps (Furniture Engineering OS)

### S1. No Canonical Furniture Graph (CFG) shared data model
**GAP:** Every module passes data as ad-hoc dicts with no shared schema.
OpenCV outputs dict→classifier outputs dict→template outputs dict→DXF.
Adding a new module requires understanding every intermediate format.

**Why this blocks the OS:** Without CFG, the AI Council (S2), Self-Critic (S3),
Manufacturing Intent (S5), and Continuous Learning (S6) all require custom
integration per module. With CFG, every new module reads/writes the same
data model.

**Fix reference:** `plans/furniture-engineering-os-architecture.md` §1
Build FurnitureGraph dataclass. All existing modules become specialists
that read from and write to CFG.

### S2. No AI Council (multi-specialist consensus)
**GAP:** One LLM call (chat_agent.py or Gemini) produces everything.
If the model is wrong, there's no second opinion. Error modes are not
detectable because there's no disagreement to measure.

**Why this blocks the OS:** The OS needs reliability through consensus.
Vision, dimension, construction, historian, and manufacturing agents should
vote independently. When they disagree, the system knows which fields are
uncertain and can ask the user.

**Fix reference:** `plans/furniture-engineering-os-architecture.md` §3
Build council/engine.py — wraps existing chat_agent, engineering_agent,
reference_retriever, dimension_associator as specialists with weighted voting.

### S3. No furniture grammar (composition rules instead of hardcoded builders)
**GAP:** All 25+ furniture types have hardcoded builders. Adding type #26
requires writing a new build_X_model() and save_X() pair (200+ lines each).
There is no inheritance, no composition, no rule sharing between families.

**Why this blocks the OS:** The OS needs to scale to hundreds of furniture
types. A grammar with 50 reusable parts (top, base, leg, seat, back, apron,
shelf, door, drawer, arm) combined via composition rules can generate 1000+
variants without new code.

**Fix reference:** `plans/furniture-engineering-os-architecture.md` §2
Build grammar/engine.py. 25 templates become grammar instances.
Existing builders delegate to grammar renderer.

### S4. No progressive resolution pipeline
**GAP:** The pipeline attempts to detect everything at once. Category,
family, dimensions, materials are all inferred in parallel. If the furniture
type is wrong, the dimensions are guaranteed wrong but nothing catches this.

**Why this blocks the OS:** The OS needs confidence gating. Stage 1
(furniture category) gates at >70% before Stage 2 (family). Stage 2 gates
before Stage 3 (configuration). Wrong classifications are caught early
before downstream work is wasted.

**Fix reference:** `plans/furniture-engineering-os-architecture.md` §4
Build progressive_pipeline.py — cascading stages with confidence thresholds.
Each stage constrains the next. No existing modules removed.

### S5. No self-critic loop (render → compare → repair)
**GAP:** Single-pass generation. If the DXF misses an edge or misreads a
dimension, there is zero feedback. The user downloads a wrong DXF and
corrects manually.

**Why this blocks the OS:** The OS must verify its own output. Rendering
the reconstruction, comparing it to the original image, classifying gaps,
and repairing them automatically catches >60% of errors before the user
sees them.

**Fix reference:** `plans/furniture-engineering-os-architecture.md` §6
Build self_critic/ — comparator, classifier, planner, loop.
Uses existing svg_exporter.py + accuracy_benchmark.py + anti_hallucination_validator.py.

### S6. No manufacturing intent graph
**GAP:** The output is a DXF drawing. There is no Bill of Materials, no
material specification, no joinery details, no assembly instructions, no
cost estimate, no packaging recommendation. A manufacturer cannot build
from a DXF alone.

**Why this blocks the OS:** The OS targets manufacturing-ready engineering
documentation. DXF is one of many outputs. BOM, costing, assembly guide,
CNC paths are equally important and currently non-existent.

**Fix reference:** `plans/furniture-engineering-os-architecture.md` §5
Build manufacturing/ — mig_builder, cost_estimator, assembly_planner.
Leverages existing resources/joinery/, resources/supports/, cad_kernel/annotation_engine/bom.py.

### S7. No continuous learning from user corrections
**GAP:** feedback_learner.py records corrections per-user but only adjusts
dimension multipliers. It doesn't update furniture grammar proportions,
template rankings, or the visual DNA index. Each user's learning is
isolated and doesn't benefit other users.

**Why this blocks the OS:** The OS should get smarter with every DXF download.
5000 user corrections = a proprietary dataset. Grammar proportions should
converge toward real furniture dimensions. Template rankings should reflect
user preferences.

**Fix reference:** `plans/furniture-engineering-os-architecture.md` §7
Wire feedback_learner to CFG corrections. closed_loop/delta_engine detects
grammar drift. template_ranking adjusts by user acceptance.

### S8. No confidence heatmap
**GAP:** EntityMetadata stores confidence per entity, but the frontend
doesn't visualize it on the CAD preview. Users can't see which parts of
the drawing are trusted vs estimated vs guessed.

**Why this blocks the OS:** The OS needs transparent confidence. A user
should see "top dimension: 95% trusted (from OCR)" vs "joinery: 42%
estimated (from template default)". This builds trust and tells users
exactly what to verify.

**Fix reference:** `plans/furniture-engineering-os-architecture.md` §7
Extend CadCanvas.tsx with heatmap overlay. Color components green/yellow/red
per confidence. Click shows evidence.

### S9. No furniture DNA similarity search
**GAP:** visual_dna_index.json exists with 101 families, but it's a static
file. There is no runtime similarity search that says "this upload matches
Product X with 94% confidence, use its known dimensions."

**Why this blocks the OS:** The OS should recognize products. When a user
uploads a dining chair that matches 91% with "Adriano Modern Dining Chair"
in the DNA database, the system should pre-fill all known dimensions with
high confidence.

**Fix reference:** `plans/furniture-engineering-os-architecture.md` §3
Historian Agent already searches reference_retriever. Add vector embedding
of visual signatures for similarity search at runtime.

### S10. No image preprocessing stage
**GAP:** Images go directly to OpenCV + AI without cleanup. No adaptive
thresholding, contour cleanup, skeletonization, corner refinement, or line
merging. Noisy images (low light, shadow, paper texture, perspective warp)
produce bad geometry.

**Why this blocks the OS:** The OS should extract maximum signal before
any AI sees the image. A 100ms preprocessing pipeline can reduce downstream
errors by 30%.

**Fix reference:** Image2CAD preprocessing pattern. Build preprocessor
pipeline: adaptive threshold → contour cleanup → skeletonization →
corner detection → line merging. Runs before anything else.

### S11. No BOM/assembly/cost outputs
**GAP:** DXF is the only output. No Bill of Materials, assembly instructions,
estimated cost, packaging advice. Furniture manufacturers need all of these.

**Fix reference:** Manufacturing Intent Graph (S6) produces these.

### S12. No exploded view generation
**GAP:** Only top/front/side views exist. No exploded view showing
component separation and assembly sequence.

**Fix reference:** cad_kernel/view_generator/exploded_view.py exists but
is stubbed (`hidden_line_stub.py`). Complete the implementation.

## Existing gaps (AI CAD Drafter)

Running list of known gaps between "what the chat agent can talk about"
and "what actually changes in the drawing." Add to this list as new gaps
are found; check items off (with commit hash) as they're closed.

See `docs/architecture-ai-cad-drafter.md` for the design that closes the
items below.

## Open gaps

### 3. "Merge sections" doesn't exist as a concept anywhere
No code path treats two adjacent named components (e.g. `neck_ring` +
`pedestal_body`) as a single continuous shape. Each furniture builder
(`build_round_pedestal_model`, `save_round_pedestal_table`, etc.) draws a
fixed sequence of independent polygons with hardcoded boundaries between
them. There's nothing to "merge" — this needs new geometry support, not
just a new chat intent.

### 7. No intermediate editable representation (IER) exists (2026-06-28)
**GAP:** `DrawingModel` exists but is view-oriented (CircleComponent, PolygonComponent
per view) — there is no furniture-agnostic component tree that unifies all 18+
furniture types into a single data structure. Each `build_X_model()` produces
ad-hoc coordinate math. A human designer cannot edit "the seat height" directly
because seat height is embedded in hardcoded polygon coordinates.

**Fix reference:** Phase A in `plans/cross-pollination-architecture.md` — define
`ComponentTree` with `ComponentNode[]` + `ComponentRelation[]`, refactor all 18+
builders to output it, convert `DrawingModel` to a consumer of ComponentTree.

### 8. No geometric relationship tracking between components (2026-06-28)
**GAP:** The system knows components exist (from template schema) but doesn't
explicitly track relationships between them. Are the legs symmetric? Is the
tabletop centered on the pedestal? Are the armrests aligned? These relationships
must be detectable from pixel geometry BEFORE scale solving (measurement-agnostic)
to catch detection errors early.

**Fix reference:** Phase B in `plans/cross-pollination-architecture.md` — 
`RelationVerifier` + `ConstraintSolver` + per-type relation templates.

### 9. No self-correction loop exists (2026-06-28)
**GAP:** The entire pipeline is single-pass. If the first pass misses an edge
or misreads a dimension, there is no mechanism to detect or correct it. The
anti-hallucination validator filters by confidence but does not compare the
reconstruction back to the original image.

**Fix reference:** Phase C in `plans/cross-pollination-architecture.md` —
`SVGComparator` + `GapAnalyzer` + `RepairPlanner` + `RepairLoop`.

### 10. No separation of "what parts exist" from "what are their dimensions" (2026-06-28)
**GAP:** Detection and estimation are mixed in a single pass. The system tries
to detect edges AND estimate their dimensions simultaneously. This conflates
the discrete classification problem (which parts?) with the continuous regression
problem (how big?). When a dimension is wrong, we can't tell if it's because
the part was mis-identified (discrete error) or the pixel-to-mm conversion was
off (continuous error).

**Fix reference:** Phase D in `plans/cross-pollination-architecture.md` —
`StructureVerifier` checks discrete completeness first, then `DimensionRegressor`
handles continuous estimation per component.

### 11. No symmetry detection or enforcement (2026-06-28)
**GAP:** Furniture is highly symmetric by nature, but the pipeline never checks
or enforces symmetry. If the left leg detects at 50px and the right leg at 53px,
the output DXF will have asymmetric legs. A human designer would never produce
this — they'd average the two measurements.

**Fix reference:** Phase E in `plans/cross-pollination-architecture.md` —
`SymmetryDetector` + `SymmetryEnforcer`.

### 12. No way to verify output matches input (2026-06-28)
**GAP:** A user uploads a drawing and gets back a DXF. There is no automated
way to verify that the DXF actually represents the input drawing. The only
verification is human visual inspection of the SVG preview. This means:
- OCR dimension misread → user downloads wrong DXF unless they catch it
- Missing component → user must manually compare original to SVG
- Hallucinated geometry → user must notice extra lines

**Fix reference:** Phase C (SVGComparator) provides the missing comparison.
This closes the loop that every production CAD tool needs: input → reconstruction
→ verification → correction → output.

### 13. ComponentTree IER must be built before any phase can start (2026-06-28)
**GAP:** All five fusion phases depend on a common IER. Until Phase A
(ComponentTree refactor) is complete, none of the other phases can produce
meaningful results. This is the critical path item.

**Fix reference:** Phase A in `plans/cross-pollination-architecture.md`.

## Closed gaps

### 1. Materials now applied to ALL furniture types (2026-06-27)
**CLOSED**: All 13 `save_*()` functions in `dxf_exporter.py` and all 13
`build_*_model()` functions in `drawing_builders.py` now accept a
`materials: Optional[Dict[str, str]] = None` parameter. `POST /api/material/edit`
handles ALL furniture types via the `_get_adjust_fn()` dispatch table.
Hatch-pattern-by-material-keyword remains unimplemented (only leader/title-block
text changes).

### 1b. `/adjust` now dispatches correctly for all types (2026-06-27)
**CLOSED**: `POST /adjust` rewritten with `_get_adjust_fn(furniture_type)`
dispatch table (`FURNITURE_ADJUST_DISPATCH`) mapping all 14 furniture types
to their `(save_*, build_*_model)` function pairs. No more hardcoded
if/elif for just round_pedestal_table and rectangular_table.

### 2. Visibility now applied (2026-06-27)
**CLOSED**: All 13 `save_*()` and all 13 `build_*_model()` functions now
accept a `visibility: Optional[Dict[str, bool]] = None` parameter. Uses
`_component_visible(name)` helper — when a component's key is `False`, it
is skipped or drawn on a `HIDDEN` layer. The `/adjust` endpoint now
accepts a `visibility` form parameter.

### 4. Chat agent vocabulary now dynamic (2026-06-27)
**CLOSED**: `chat_agent.py`'s `SYSTEM_PROMPT` dynamically includes the full
list of all 18 furniture types with their editable dimension keys and material
component documentation — generated from `FURNITURE_TYPES_LIST` and
`DIMENSION_KEYS_BY_TYPE`. No longer a hardcoded subset.

### 6. Template system now covers 18 types (2026-06-27)
**CLOSED**: The `_component_schema()` if/elif chain now covers all 18
supported types. The new `TemplateResolver` (`template_loader.py` +
`template_resolver.py`) loads 18 JSON template graphs and resolves detected
dimensions via `PRODUCT_TYPE_MAP` and `DIMENSION_CM_TO_MM_MAP`. The
`/digitize/resolve` endpoint returns parameter schema (min/max/sliders) for
any of the 18 types. Backward compatible — existing if/elif chain remains
as fallback.

### Phase3Pipeline — Cloud Vision to Production (2026-06-27)
**CLOSED**: `Phase3Pipeline` (`pipeline_orchestrator.py`) orchestrates the
full pipeline: Cloud Vision (OpenAI/Gemini) → ResourceIntelligenceEngine
→ TemplateResolver → ValidationPipeline → FusionPipeline → OutputPipeline.
Wired into `/digitize/hybrid` as a parallel analysis track returning
`phase3` in the API response.

---

## Recent Updates (2026-06-29)

### Feature Test — 5 Products at 92.2% avg (2026-06-29)
**CLOSED**: `docs/feature-test-2026-06-29.md` — all 5 products verified:
- Tangerie dining table: 100×200×75cm, score 0.925
- Valenza round table: 120×120×75cm, score 0.922 (2 circles — round DXF ✅)
- Glenn modern sofa: 250×95×82cm, score 0.920 (height 82cm ✅)
- Evon modern bed: 226×230×102cm, score 0.920 (dims extracted ✅)
- Aeris console table: 40×140×78cm, score 0.925 (was 0 dims ✅)
- All 8 containers healthy. All 9 frontend tabs loading.
- Docker Desktop crash issue: occurs during heavy builds on Windows. Resolved by restart.

### 14. MCP server for ChatGPT integration (2026-06-29, commit `ad8d1ef`)
**CLOSED**: `mcp-server/server.js` with 13 tools exposed via SSE (port 3003) 
and stdio (ChatGPT Desktop). Tools: crawl_product_url, batch_crawl, 
list_templates, suggest_template, validate_dimensions, compare_digitization,
get_calibration_report, apply_corrections, update_parameter,
get_current_parameters, get_comparison_results, get_analytics,
cleanup_old_comparisons. Docker healthcheck + resolver-based dynamic DNS.

### 15. Template graph path resolution fixed (2026-06-29, commit `36191f6`)
**CLOSED**: `template_loader.py` TEMPLATE_DIR used wrong parent count 
(4→3 parents). Same bug existed in `product_search.py`, `svg_skeleton.py`, 
`template_selector.py`, `component_assembler.py`, `product_classifier.py` — 
all fixed from `parents[3]` to `parents[2]`. Root `resources/` now mounted 
in Dockerfile via `COPY resources/ /app/resources/`. 18 template graphs 
load correctly.

### 16. Furniture Engineering Agent (2026-06-29, commit `b58f4ef`)
**CLOSED**: `engineering_agent.py` — complete engineering analysis with 
BOM, materials database, joinery standards, ergonomic references, 
component templates, structural analysis, and CAD layer recommendations. 
Web endpoint `POST /engineer/analyze`. MCP tools: `engineering_analyze`, 
`list_engineering_families`. DB table `engineering_analyses` with full schema.

### 17. All 5 architecture phases integrated and verified (2026-06-29)
**CLOSED**: 
- **Phase 1** (per-product DNA): Classifier returns `rectangular_dining_table` 
  (71% confidence) with per-product edge/thickness/ratio fields.
- **Phase 2** (family→subtype→template): `FAMILY_CATEGORIES` super-category 
  fallback added. Family classification cascades from specific→generic.
- **Phase 3** (SVG skeleton): Lightweight skeleton wired into crawl-to-dxf 
  result. `skeleton_svg` field returned alongside DXF.
- **Phase 5** (component library): 18 template graphs loadable. Engineer BOM 
  generation works with 6 furniture families.
- **Phase 7** (self-learning): Auto-calibration triggers every 3rd comparison. 
  Product DNA enrichment from validated results.

### 18. Nginx 502 error fixed with dynamic DNS resolution (2026-06-29, commit `ad8d1ef`)
**CLOSED**: Root cause: Nginx cached upstream IP at startup. When python-worker 
was recreated (IP changed), Nginx tried old IP → "Connection refused" → 502. 
Fix: Added `resolver 127.0.0.11 valid=10s` + replaced upstream blocks with 
`$variable` proxy_pass for dynamic DNS resolution every 10s.

### 19. Visual shape quality comparison endpoint (2026-06-29, commit `db8ea5c`)
**CLOSED**: `POST /visual/compare` — Hu moment shape comparison, HoughCircles 
circle detection with false positive filtering, DXF entity classification 
(round/rectangular/mixed), and visual quality scoring. Shape match score 
between product photo and DXF template.

### 20. Accuracy benchmark: 10/10 products with dimensions (2026-06-29, commit `db8ea5c`)
**CLOSED**: `scripts/accuracy-benchmark.py` tests 10 known HomeU products 
against ground truth. Results: 92.3% avg validation, 10.5% avg dim deviation, 
10/10 with DXF. Supports `--json`, `--csv` for CI/VPS integration.

### 21. Dimension extraction: median height + W/L/H labels (2026-06-29, commit `feafb78`)
**CLOSED**:
- Glenn sofa height 2cm→82cm: When multiple size variants have inconsistent 
  heights, median is selected (was last parsed). Outlier detected when height 
  <30% of median.
- Evon bed: Added `(W)(L)(H)` label matching in Pattern A. Format 
  `1960(W)x2300(L)x1020(H)mm` → 196x230x102cm correctly.
- Vivaldi table: `length_cm` now mapped to `depth_cm`. DXF title: 
  `80x80x75`→`80x140x75`. ✅

### 22. Shape-based template dispatch (2026-06-29, commit `f1407c6`)
**CLOSED**: Round/oval tables with `category=table` now dispatch to 
`round_pedestal_table` via slug-based shape detection. Keywords: 
`round`, `oval`, `square`, `pedestal` in URL slug trigger correct template. 
Round DXF now has 2+ circles (was 0). Rectangular DXF has 0 circles. ✅

### 23. CFG canonical import + self_critic validation fixed (2026-06-29, commit `90be31f`)
**CLOSED**: 
- `cfg/__init__.py`: Added `CanonicalFurnitureGraph` export (caused 
  `ImportError` on worker startup via `cfg.router → self_critic` chain).
- `anti_hallucination_validator.py`: Added `validate_drawing()` alias for 
  `self_critic.loop` (which imports this name). Was `ImportError` crash.

### 24. DXF shape diversification (2026-06-29, commit `db8ea5c` → current)
**CLOSED**:
- Round pedestal table: Added concentric circles for neck ring + pedestal 
  column in top view (was single circle). DXF now has 2+ circles, enabling 
  shape match detection.
- Vivaldi table dispatch: `real_d` (from `real_depth_cm`) used in 
  `rectangular_table` dispatch before falling back to OCR or default 80cm.
- Isometric view added to all rectangular table DXFs (4 views total: 
  top, front, side, isometric). 87 entities.

### 25. Stale code cleanup (2026-06-29, commit `ccc2e52`)
**CLOSED**: Removed 18 duplicate template graph files from 
`backend-python/resources/` (moved to root `resources/`). Removed `skills/` 
directory (superseded by `.agents/skills/`). Removed `scratch/` scripts. 
Removed `cad.abcx124.xyz.conf`. Removed 8 stale `temp_batch*/` directories. 
Added `temp_*/` to `.gitignore`.
