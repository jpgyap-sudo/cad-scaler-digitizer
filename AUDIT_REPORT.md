# Audit Report: Confirmation Loop Integration (commit 6a62eff)

**Integration of `furniture_intelligence` pack with existing CAD digitizer**
**Date**: 2026-06-28

---

## 🔴 Critical Bugs (2)

### B-1: `LAST_PROPOSAL` — Shared global state, not thread-safe
- **File**: [`furniture_intelligence/api/routes.py:15`](backend-python/app/furniture_intelligence/api/routes.py:15)
- **Issue**: `LAST_PROPOSAL` is a **module-level global variable**. In a multi-user server (Uvicorn with workers or async), if User A calls `/analyze` and then User B calls `/analyze`, B's proposal overwrites A's. Then A calls `/confirm` and gets B's template, or vice versa. Data corruption between users.
- **Fix**: Store proposals per-session (e.g., using a `session_id` query param + dict), or store in Redis, or generate a proposal_id and pass it to `/confirm`.

### B-2: `apply_corrections()` fragile `__class__` reference
- **File**: [`correction_engine.py:27`](backend-python/app/furniture_intelligence/services/correction_engine.py:27)
- **Issue**: `proposal.analysis.__class__.model_validate(data)` assumes `analysis` is exactly a `FurnitureAnalysis` instance. If a subclass or different type is used, `model_validate()` may fail or lose fields.
- **Fix**: `from app.furniture_intelligence.schemas.furniture_analysis import FurnitureAnalysis` and call `FurnitureAnalysis.model_validate(data)` directly.

---

## 🟡 High Issues (2)

### B-3: `default_parameters_for()` returns empty for 32 of 34 templates
- **File**: [`correction_engine.py:16`](backend-python/app/furniture_intelligence/services/correction_engine.py:16)
- **Issue**: Only 2 pack templates have `default_parameters_mm`. The 32 HomeU templates have `required_dimensions` and `parts` but **no `default_parameters_mm`** field. So for most furniture types, `parameters_mm` is empty and the DXF/SVG generators use hardcoded defaults (1200x700x360mm oval coffee table) regardless of actual furniture type.
- **Impact**: A wardrobe classified via HomeU templates will generate an oval coffee table DXF from the confirmation generators.
- **Fix**: Add `default_parameters_mm` mapping to all 32 HomeU templates, or derive default parameters from `required_dimensions` in the correction engine.

### B-4: Category matching fails between AI output and HomeU template categories
- **File**: [`template_matcher.py:35`](backend-python/app/furniture_intelligence/services/template_matcher.py:35) and line 62
- **Issue**: The score function does `analysis.category == template.get('category')`. But AI returns categories like `"coffee_table"` while HomeU templates use `"center_table"`. AI returns `"sofa"` (matching). AI returns `"dining_table"` (matching). But `"round_pedestal_table"` → template has no category field matching that. The category match is **case-sensitive** and uses exact string comparison without normalization.
- **Impact**: Category match (worth 0.15 score) fails for mismatched category names, reducing template score for HomeU templates.
- **Fix**: Normalize both sides: `analysis.category.replace('-','_').lower().strip()` and normalize template category. Also build a category map from template filenames (e.g., any template starting with `coffee_table_` should match `coffee_table` or `center_table`).

---

## 🟡 Medium Issues (2)

### B-5: `build_questions()` only handles 3 specific uncertainty fields
- **File**: [`template_matcher.py:114`](backend-python/app/furniture_intelligence/services/template_matcher.py:114)
- **Issue**: Hardcoded for oval-coffee-table-with-bowl scenario (`top_shape`, `base_type`, `bowl_offset`). For other furniture types (sofa: arm_height, cushion_count; cabinet: door_count, drawer_count; wardrobe: shelf_count), no uncertainty questions are generated.
- **Fix**: Generate questions dynamically from template `required_dimensions` + `parts` where values are missing or estimated.

### B-6: FIX: `SmartConfirmations.tsx` handles `uncertaintyQuestions` from `cadEngineResult` but the `/digitize/hybrid` response wraps them inside `template_proposal.questions`
- **File**: [`routes.py:1520`](backend-python/app/api/routes.py:1520)
- **Current code**: `uncertainty_questions = template_proposal_result.get('questions', [])` — correctly extracts from `template_proposal` and puts at top-level. ✅ Working.
- But `/digitize/hybrid` only runs the analysis if `ai_result` exists. If OpenAI is not configured (no API key), `ai_result` is empty and no questions are generated.

---

## 🟢 Low Issues (3)

### B-7: Pack requirements not in `requirements.txt`
- **Files**: `requirements.txt` in pack vs `backend-python/requirements.txt`
- **Issue**: The pack uses `openai` and `google-generativeai` which aren't in the main `requirements.txt`. If `pip install` from the main file, these won't be installed.

### B-8: `load_templates()` silently drops malformed JSON
- **File**: [`template_matcher.py:10`](backend-python/app/furniture_intelligence/services/template_matcher.py:10)
- **Issue**: If a .json file has a syntax error, it's silently skipped. No warning is printed.

### B-9: `_registry.json` loaded as template
- **File**: [`template_matcher.py:12`](backend-python/app/furniture_intelligence/services/template_matcher.py:12)
- **Issue**: The `load_templates()` in `template_matcher.py` **does not skip `_registry.json`** unlike the one in `template_selector.py` which has `if p.name.startswith("_registry"): continue`. So `_registry.json` (which just lists template names) gets loaded as a template and scored.

---

## Summary

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| Bugs | 9 | 2 | 2 | 2 | 3 |

### Priority Actions:
1. **CRITICAL**: Fix `LAST_PROPOSAL` global state — add session_id support
2. **CRITICAL**: Fix `fragile __class__` in `apply_corrections()`
3. **HIGH**: Add `default_parameters_mm` to 32 HomeU templates
4. **HIGH**: Fix category matching normalization in template_matcher.py
5. **MEDIUM**: Make `build_questions()` dynamic from template schema
6. **LOW**: Skip `_registry.json` in template_matcher.py load_templates()
