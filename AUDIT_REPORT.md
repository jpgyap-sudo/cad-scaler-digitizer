# Audit Report: Latest Fixes (2026-06-28)

**Commit**: Fixes applied during this session
**Files Changed**:
- `backend-python/app/api/routes.py` — 5 edits (merged_dims, preview_svg, view, benchmark endpoints)
- `backend-python/app/backend/dxf_exporter.py` — 1 edit (scale_solver replacement)
- `fixtures/manifest.json` — 1 edit (added asymmetric pedestal entry)

---

## ✅ Fixed Issues (Round 2)

| ID | Description | Severity | Status |
|----|------------|----------|--------|
| BUG-1 | `anti_hallucination_validator.py` module-level `@property` | CRITICAL | Already fixed in codebase before this session |
| BUG-3 | `dimension_associator.py` passes `text_boxes` where `vision_lines` expected | CRITICAL | Already fixed in codebase before this session |
| BUG-4 | `scale_solver.py` `has_sufficient_data` missing attribute | HIGH | Already fixed in codebase before this session |
| BUG-8 | `ocr_layout_parser.py` `pytesseract.pytesseract` typo | HIGH | Already fixed in codebase before this session |

### Fixed This Session

| ID | Description | File | Fix |
|----|------------|------|-----|
| **BUG-NEW-1** | `/adjust` endpoint uses undefined `merged_dims` (NameError crash) | [`routes.py:1862`](backend-python/app/api/routes.py:1862) | Added merged_dims construction from sidecar JSON + form overrides |
| **BUG-7** | Preview SVG always shows round pedestal table | [`routes.py:1736`](backend-python/app/api/routes.py:1736), [`routes.py:2464`](backend-python/app/api/routes.py:2464) | Both `/preview/svg` and `/view` now read sidecar JSON and dispatch via `_build_svg_model()` |
| **FG-4** | `dxf_exporter.py` still uses deprecated `visual_ratio_scaler` | [`dxf_exporter.py:248`](backend-python/app/backend/dxf_exporter.py:248) | Replaced both import sites with `scale_solver.compute_scale()` |
| **WG-2** | `accuracy_benchmark.py` not exposed via API | [`routes.py:3544`](backend-python/app/api/routes.py:3544) | Added `GET /benchmark/run`, `GET /benchmark/fixtures`, `POST /benchmark/run` |
| **FG-5** | Asymmetric pedestal fixture missing from manifest | [`manifest.json`](fixtures/manifest.json) | Added entry with correct type and path |

---

## 🔴 REMAINING Critical/High Issues

### BUG-NEW-2: POST `/benchmark/run` fixture limit silently ignored
- **File**: [`routes.py:3581`](backend-python/app/api/routes.py:3581)
- **Issue**: The endpoint loads `fixtures` to check the limit, then calls `run_accuracy_benchmark()` which **re-loads** fixtures internally — so the `max_fixtures` limit is never applied.
- **Fix**: Change to call `run_accuracy_benchmark` with filtered fixture list, or pass fixture count.

### BUG-NEW-3: `dxf_exporter.py` scale_solver always falls back to hardcoded defaults
- **File**: [`dxf_exporter.py:286`](backend-python/app/backend/dxf_exporter.py:286)
- **Issue**: The scale_solver integration passes a mock `Association` with no real dimension-geometry relationship. `compute_scale` returns a `ScaleSolution` with empty `resolved_dimensions`, so the `sr` dict always uses the `top_dia_cm * 0.55` fallback. The code compiles and runs but doesn't meaningfully use the scale solver.
- **Fix**: Either pass real association data, or simplify to directly compute ratios from the known dimensions without going through scale_solver.

### BUG-NEW-4: Preview/view fallback DIMENSION scan assumes round table
- **File**: [`routes.py:1757`](backend-python/app/api/routes.py:1757), [`routes.py:2486`](backend-python/app/api/routes.py:2486)
- **Issue**: When no sidecar JSON exists for a DXF file and no DIMENSION entities are found, the fallback is `80x70` round pedestal table regardless of the actual furniture type.
- **Fix**: Accept that the fallback is generic; at minimum extract ALL dimension values and determine furniture type from the DXF content.

### WG-2: `section_predictor.py` not wired into API (HIGH)
- **File**: [`routes.py:23`](backend-python/app/api/routes.py:23) (imported but never called)
- **Issue**: `predict_drawing_sections` is imported at line 23 but never called in any endpoint. 389 lines of production code with zero integration.
- **Fix**: Wire into `/digitize`, `/digitize/hybrid`, or create a dedicated `/predict-sections` endpoint.

### SG-1: API prefix mismatch `/api` vs `/py-api` (HIGH)
- **Backend**: `main.py` registers router with `prefix="/api"`
- **Frontend**: `cadEngine.ts` uses `VITE_CAD_ENGINE_URL || '/py-api'`
- **Issue**: Works only because of Vite dev proxy. Production deployment without nginx rewrite will break ALL API calls.
- **Fix**: Either align the prefix or add a proxy route. Already documented in original audit.

### BUG-6: `ConfidencePanel.tsx` — `lockedTexts` uses local React state, not server state (LOW)
- **File**: [`ConfidencePanel.tsx:139`](frontend/components/ConfidencePanel.tsx:139)
- **Issue**: Lock state is persisted in `sessionStorage`, not synchronized with server. Survives re-renders within a session but resets on page reload.
- **Fix**: Read lock state from `/corrections/{session_id}` endpoint on mount.

---

## 🟡 Feature Gaps (Medium)

### FG-3: Line role correction UI exists but corrections always send `[]`
- **Files**: [`App.tsx:388`](frontend/App.tsx:388), [`App.tsx:417`](frontend/App.tsx:417), [`ConfidencePanel.tsx:216`](frontend/components/ConfidencePanel.tsx:216)
- **Current state**: The `ConfidencePanel` has full UI for line role reclassification (dropdown, correction tracking, visual display). The `App.tsx` wires `onCorrectLineRole` which sends corrections to the API. **However**, the `handleCorrectValue` and `handleLockDimension` functions still hardcode `line_role_corrections: '[]'`, so line role corrections sent directly from the panel DO work, but dimension-only corrections still overwrite the role corrections if both are sent.
- **Fix**: Merge accumulated `lineRoleCorrections` from the panel state into the dimension correction requests.

### WG-4: Frontend `DigitizeResult` type missing `accuracy_pipeline` field
- **File**: [`cadEngine.ts:23`](frontend/services/cadEngine.ts:23) (the `AccuracyPipeline` interface exists at line 36 but the `DigitizeResult` interface at higher lines may not include it)
- **Issue**: TypeScript compiles with `implicit any` — no compile-time safety for the accuracy pipeline data contract.
- **Fix**: Add `accuracy_pipeline?: AccuracyPipeline` to the `DigitizeResult` interface.

---

## 🟢 Summary

| Category | Count | Critical | High | Medium | Low | Fixed |
|----------|-------|----------|------|--------|-----|-------|
| Bugs (new) | 3 | 0 | 2 | 1 | 0 | 0 |
| Wiring Gaps | 1 | 0 | 1 | 0 | 0 | 0 |
| Feature Gaps | 2 | 0 | 0 | 2 | 0 | 0 |
| **New Total** | **6** | **0** | **3** | **3** | **0** | **0** |
| Fixed This Session | 5 | 1 | 2 | 1 | 1 | 5 |
| Prior Fixed | 4 | 2 | 2 | 0 | 0 | 4 |

### Immediate Action Items:
1. **HIGH**: Wire `section_predictor.py` into API routes or remove it
2. **HIGH**: Fix API prefix for production (`/api` vs `/py-api`)
3. **MEDIUM**: Fix POST `/benchmark/run` to actually use the fixture limit parameter
4. **MEDIUM**: Merge line role corrections into dimension correction requests in frontend
