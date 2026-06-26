# Audit Report: Latest SuperRoo Update (commit 1454f6e)

**Feature**: accuracy core pipeline + correction UI + real product dataset from homeu.ph
**Date**: 2026-06-26
**Files**: 31 changed, +6,308 / −2,153 lines

---

## 🔴 Wiring Gaps (5)

### WG-1: `accuracy_benchmark.py` — Dead module, no API route
- **File**: `backend-python/app/backend/accuracy_benchmark.py` (+428 lines)
- **Issue**: Complete benchmark framework with fixture loading, dimension accuracy scoring, per-fixture result breakdown, and a functional `__main__` entry point. But **no API endpoint exposes it** — not in `routes.py`, not in `main.py`. The only way to run it is `python -m app.backend.accuracy_benchmark` directly.
- **Severity**: MEDIUM — feature exists but unreachable via the UI.

### WG-2: `section_predictor.py` — Dead module, no API route
- **File**: `backend-python/app/backend/section_predictor.py` (+389 lines)
- **Issue**: Full section prediction engine with 7 furniture type templates, conditional logic, and shop drawing layout generation. **Not imported or wired in any route.** No API endpoint to retrieve section predictions.
- **Severity**: HIGH — 389 lines of production code with zero integration surface area.

### WG-3: `anti_hallucination_validator.py` — Broken `@property` on module (not class)
- **File**: `backend-python/app/backend/anti_hallucination_validator.py`, lines 281-284
- **Issue**: Lines 281-284 define `@property def components(self):` at **module level** (outside any class). This is a syntax error at import time in Python — `@property` requires a `self` inside a class. This would crash any importer of this module at runtime.
  ```python
  # Line 281-284 — FATAL:
  @property
  def components(self):
      """Backward-compatible access — maps entity_verdicts to old format."""
      return self.entity_verdicts
  ```
- **Severity**: CRITICAL — module-level `@property` is a Python syntax error. Any code path that imports `anti_hallucination_validator` will fail with `NameError: name 'self' is not defined`.

### WG-4: Frontend `DigitizeResult` type missing `accuracy_pipeline` field
- **File**: `frontend/services/cadEngine.ts`, line 22-44
- **Issue**: The TypeScript `DigitizeResult` interface doesn't include `accuracy_pipeline`, but `App.tsx` accesses it heavily:
  - `cadEngineResult?.accuracy_pipeline?.associations?.associations` (lines 339, 340, 341)
  - `cadEngineResult?.accuracy_pipeline?.associations?.associations?.[i]?.source` (line 339)
  - `cadEngineResult?.accuracy_pipeline?.associations?.associations?.[i]?.confidence` (line 340)
- **Severity**: MEDIUM — TypeScript compiles but with implicit `any` types; no compile-time safety for the accuracy pipeline data contract.

### WG-5: `correction_api.py` `handle_correction_submission` unpacks dicts as `**c` — will fail
- **File**: `backend-python/app/backend/correction_api.py`, lines 170-175
- **Issue**: `handle_correction_submission` receives `List[dict]` from the API route, then does `DimensionCorrection(**c)` which unpacks dict keys into the dataclass constructor. But the frontend sends `{session_id, ocr_text, original_value_cm, corrected_value_cm, is_locked}` — field names match, but the dataclass also has optional fields `assigned_to_entity_id`, `assigned_to_entity_type`, `note` that the frontend never sends. This works because they're optional, but any future field mismatch will silently drop data.
- **Severity**: LOW — works currently but fragile.

---

## 🔴 Sync Gaps (3)

### SG-1: API prefix mismatch — backend registers `/api`, frontend calls `/py-api`
- **Backend** (`main.py` line 33): `app.include_router(router, prefix="/api")`
- **Frontend** (`cadEngine.ts` line 81): `VITE_CAD_ENGINE_URL || '/py-api'`
- **Issue**: Backend exposes routes at `/api/digitize`, `/api/corrections/submit`, etc. Frontend hits `/py-api/digitize`, `/py-api/corrections/submit`. This only works because of a Vite dev proxy (assumed in `vite.config.ts`). In production with no proxy, ALL frontend API calls will fail.
- **Severity**: HIGH — production deployment will break unless nginx/Envoy is configured to rewrite `/py-api/* → /api/*`.

### SG-2: Backend returns `/api/download/xxx` paths, frontend rewrites to `/py-api/download/xxx`
- **Backend** (`routes.py` line 370): `'download': f'/api/download/{dxf_name}'`
- **Frontend** (`cadEngine.ts` line 152): `result.download.replace('/api/', '/py-api/')`
- **Issue**: The path rewriting in `cadEngine.ts` is fragile string replacement. If a filename contains `/api/` (unlikely but possible with UUID-based names), the replacement corrupts the path. More importantly, this strip-and-replace does not handle the `/api/preview/svg/` path which the backend also returns (`routes.py` line 371).
- **Severity**: LOW — works for current UUID filenames, but the `/api/preview/svg/` path in `preview_svg` is NOT rewritten anywhere before display.

### SG-3: Chat state (`CHAT_SESSIONS`) is in-memory only, no persistence
- **File**: `routes.py` line 917: `CHAT_SESSIONS: dict = {}`
- **Issue**: All chat state is stored in a module-level dict. Server restart wipes all sessions. No redis/database backend. Multiple workers would have independent, disconnected session stores.
- **Severity**: MEDIUM — acceptable for dev but will lose user state on every redeploy.

---

## 🔴 Feature Gaps (6)

### FG-1: `section_predictor.py` — not integrated into DXF generation
- The module predicts which shop drawing sections (front, top, side, detail) to generate for each furniture type. But the DXF exporters (`dxf_exporter.py`) never call it. Every DXF is generated from hardcoded templates, not the predicted sections.
- **Impact**: All shop drawings use fixed templates regardless of furniture dimensions.

### FG-2: `accuracy_benchmark.py` — no CI/automated test hook
- Benchmark exists but is manual-only. No `pytest` integration, no pre-commit hook, no `/api/benchmark` endpoint to run from CI.
- **Impact**: Accuracy regressions go undetected.

### FG-3: No line role correction UI
- The `correction_api.py` supports `line_role_corrections` (reclassifying a line as LEADER vs DIMENSION vs OBJECT_EDGE), but the `ConfidencePanel.tsx` and `App.tsx` only support **dimension value corrections**. The frontend always sends `line_role_corrections: '[]'`. There's no UI at all for correcting line roles.
- **Impact**: Half of the correction API is unusable from the UI.

### FG-4: `visual_ratio_scaler.py` — partially refactored but old version still in use
- **File**: `visual_ratio_scaler.py` (344 lines changed). The new `scale_solver.py` was introduced as the "upgraded replacement" per the plan doc, but `routes.py` still imports from `visual_ratio_scaler.estimate_proportions` at line 145, bypassing `scale_solver.compute_scale()` entirely.
- **Impact**: Two competing scale modules exist; the new one is wired into `_run_accuracy_pipeline()` but the actual DXF dispatch uses the old one.

### FG-5: Fixture reference images missing
- **Files**: `fixtures/manifest.json` references `reference.jpg` for all 8 fixtures, but the fixture directories only contain `spec.json` files — no actual images. The `accuracy_benchmark.py` `load_fixtures()` method will find spec.json files but fail to find images (`⚠ No image found for ...`) and silently skip those fixtures.
- **Impact**: Benchmarks run with 0 fixtures. The `manifest.json` has 8 entries pointing to non-existent reference images.

### FG-6: `_component_schema()` hardcoded for only 2 furniture types
- **File**: `routes.py` lines 79-107. Only `round_pedestal_table` and `rectangular_table` have component schemas. The frontend `SliderPanel` uses `componentSchema` but 6 other furniture types (sofa, cabinet, coffee_table, dining_chair, wardrobe, reception_counter, bed_headboard) return `null` from `_component_schema()`, providing no per-component adjustment UI.
- **Impact**: Users adjusting non-table furniture get no section-specific sliders.

---

## 🔴 Bugs (8)

### BUG-1: `anti_hallucination_validator.py` — Module-level `@property` (CRITICAL)
- **Lines 281-284**: `@property` and `def components(self):` outside any class. This is a Python syntax error at module-import time. Any import of this module will crash.
- **Fix**: Remove lines 281-284 (they duplicate the `ValidationResult.components` property defined on line 66-68 inside the class).

### BUG-2: `geometry_reconstructor.py` — `length` used before assignment in `_snap_near_parallel_lines`
- **Line 228**: `min_dist, ki, li = min(dists, key=lambda x: x[0])` — `ki` and `li` are assigned but never used. Not a bug per se but indicates incomplete logic: the code detects the closest endpoint pair but then builds `best_extended` using ALL 4 points regardless of which pair was closest. The extended line always covers the bounding box of all 4 points, not just the closest merge pair.
- **Severity**: LOW — incorrect merge behavior when multiple near lines exist.

### BUG-3: `dimension_associator.py` — `text_boxes` passed where `vision_lines` expected in `_find_nearby_object_lines`
- **Line 378**: `_find_nearby_object_lines(label, best_dim_line, text_boxes, flat_lines)` — the 3rd parameter should be `all_lines` (a list of lines), but `text_boxes` is passed (List of TextBox objects). The function signature is:
  ```python
  def _find_nearby_object_lines(text_box, dim_line, all_lines, vision_lines, search_radius=60.0)
  ```
  The function then iterates over `all_lines` (which is now TextBox objects) treating them as tuples — this will crash at runtime with `TypeError: cannot unpack non-iterable TextBox object`.
- **Severity**: CRITICAL — runtime crash when a dimension label has a matched dimension line without extension lines.

### BUG-4: `scale_solver.py` — `has_sufficient_data` checked but doesn't exist on `ScaleFactor`
- **Line 312**: `combined.has_sufficient_data` — `ScaleFactor` has no `has_sufficient_data` attribute. This is checked in `apply_scale_to_model()` which would raise `AttributeError` at runtime.
- **Severity**: HIGH — `apply_scale_to_model()` will always crash if called.

### BUG-5: `routes.py` — `_save_drawing_model` only handles `round_pedestal_table`
- **Lines 37-50**: The `_save_drawing_model` function has a guard `if f_type != 'round_pedestal_table': return` at the very top. This means NO DrawingModel JSON is saved for rectangular tables, cabinets, sofas, chairs, or any other furniture type. The function is only called for `round_pedestal_table`.
- **Severity**: MEDIUM — DrawingModel JSON (used for SVG preview and parametric adjustment) is missing for all non-round-table furniture.

### BUG-6: `ConfidencePanel.tsx` — `lockedTexts` uses local React state, not server state
- **Lines 98, 131-142**: When a user locks a dimension, `lockedTexts` is a local `useState<Set>`. On re-render (e.g., after a correction submission), the locked state resets. The server-side corrections are persisted (`correction_api.py` saves to disk), but the UI lock state is ephemeral.
- **Severity**: LOW — cosmetic: lock icons disappear after any re-render that remounts the component.

### BUG-7: `routes.py` — SVG preview always assumes `round_pedestal_table`
- **Lines 350-363 and 483-496**: Both `/digitize` and `/digitize/hybrid` endpoints hardcode `build_round_pedestal_model()` for SVG generation. If the furniture is a rectangular table, sofa, or cabinet, the SVG preview will show a round pedestal table regardless. The `svg_exporter.py` drawing_to_svg should handle multiple model types but only `build_round_pedestal_model` is called.
- **Severity**: HIGH — SVG preview is always a round pedestal table for ALL furniture types.

### BUG-8: `ocr_layout_parser.py` — `pytesseract` as module attribute typo
- **Line 26**: `pytesseract.pytesseract.tesseract_cmd = tp` — should be `pytesseract.pytesseract.tesseract_cmd` (double `pytesseract`). The correct attribute is `pytesseract.tesseract_cmd`.
- **Severity**: HIGH — Tesseract path configuration never applies. On Windows without tesseract in PATH, OCR will fail silently or use a system-installed tesseract if one exists.

---

## Summary

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| Wiring Gaps | 5 | 1 | 1 | 2 | 1 |
| Sync Gaps | 3 | 0 | 1 | 1 | 1 |
| Feature Gaps | 6 | 0 | 2 | 3 | 1 |
| Bugs | 8 | 2 | 4 | 1 | 1 |
| **Total** | **22** | **3** | **8** | **7** | **4** |

### Immediate Action Items (Blocking / Crash-Causing):
1. **BUG-1**: Remove module-level `@property` in `anti_hallucination_validator.py` (line 281-284)
2. **BUG-3**: Fix `_find_nearby_object_lines()` call — pass `flat_lines` instead of `text_boxes` (line 378)
3. **BUG-8**: Fix `pytesseract.pytesseract.tesseract_cmd` → `pytesseract.tesseract_cmd` (line 26)

### High Priority (Functional Failures):
4. **BUG-4**: Add `has_sufficient_data` property or fix `apply_scale_to_model()` (line 312)
5. **BUG-7**: Make SVG preview generation type-aware (not always round_pedestal_table)
6. **WG-3**: Wire `section_predictor.py` into API routes or remove it
7. **SG-1**: Document/verify proxy configuration for production `/py-api` → `/api` path rewrite
8. **WG-2**: Wire `accuracy_benchmark.py` into API routes or CI
