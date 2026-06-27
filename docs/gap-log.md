# Gap Log — AI CAD Drafter

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
