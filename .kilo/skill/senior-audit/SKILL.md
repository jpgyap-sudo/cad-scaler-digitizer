# Senior Engineer Audit Skill

## Purpose
Systematically audit the CAD Digitizer codebase for wiring gaps, dead code, orphaned features, and unconnected resources. Designed for a senior engineer reviewing a junior's work — features might look complete but be completely disconnected from the actual pipeline.

## Audit Methodology

For every feature, trace the FULL data flow:
```
User Input → API Route → Service Function → Database / File → Response → Frontend
```

If any step in the chain is missing, the feature is **dead code**.

---

## Phase 1: Import Trace — Find Orphaned Modules

For every Python/TypeScript file in the project, check if it's **actually imported** by another file. A file that exists but is never imported is dead code.

```bash
# Find all .py files in backend-python
find backend-python/app -name "*.py" | sort

# For each file, grep whether it's imported by any OTHER file
grep -r "from app\.backend\.foo import" backend-python/app --include="*.py"
grep -r "from app\.services\.bar import" backend-python/app --include="*.py"

# Find files that are NEVER imported
```

### Checklist

| File | Imported By? | Used In Route? | Status |
|------|-------------|----------------|--------|
| `app/backend/svg_skeleton.py` | Need to check | `/skeleton/{family}` endpoint? | ✅/❌ |
| `app/backend/component_assembler.py` | Who imports it? | Any route uses it? | ✅/❌ |
| `app/backend/anti_hallucination_validator.py` | Imported? | Actually called at runtime? | ✅/❌ |
| `app/services/engineering_agent.py` | Route `/engineer/analyze`? | Frontend calls it? | ✅/❌ |
| `app/services/training_feedback.py` | `apply_calibration` trigger? | Auto-run on comparison? | ✅/❌ |
| `frontend/components/AnalyticsPage.tsx` | Imported in App.tsx? | Tab renders correctly? | ✅/❌ |
| `frontend/services/confidenceHeatmap.ts` | Imported anywhere? | Used in frontend? | ✅/❌ |

---

## Phase 2: API Route Audit — Every Endpoint Must Have a Caller

List EVERY `@router.get/post/put/delete` in `routes.py`. For each one, verify:

1. **Does a frontend component call it?** (grep the fetch URL)
2. **Does an MCP tool call it?** (grep mcp-server/server.js)
3. **Does another backend service call it?** (grep for HTTP calls)
4. **If NONE of the above — it's dead code.**

```bash
# List all routes
grep -n "@router\.\(get\|post\|put\|delete\)" backend-python/app/api/routes.py

# For a given route, check callers:
# Frontend
grep -r "templates" frontend/ --include="*.tsx" --include="*.ts"
# MCP
grep -r "templates" mcp-server/server.js
# Other services
grep -r "templates" backend-python/ --include="*.py"
```

### Common Dead Route Patterns

- Routes that return sample/placeholder data
- Routes that were built for a frontend component that was never created
- Routes that require authentication but no auth flow exists
- Routes that were moved to a different path but old path remains

---

## Phase 3: Resource File Audit — Files That Exist But Are Never Read

Check every JSON resource file. If it's never loaded by any Python module, it's dead weight.

```bash
# List all resource files
find resources/ -name "*.json" | sort

# For each, check if it's read by any Python file
grep -r "visual_dna_index" backend-python/ --include="*.py"
grep -r "product_dna" backend-python/ --include="*.py"
grep -r "component_library" backend-python/ --include="*.py"
```

### Key Resource Files to Check

| Resource | Loaded By? | Actually Used? |
|----------|-----------|----------------|
| `resources/product_catalog/visual_dna_index.json` | `product_search.py:28` | Called from a route? |
| `resources/product_catalog/product_dna.json` | `product_search.py:29` | Updated by `enrich_product_dna`? |
| `resources/product_catalog/component_library.json` | `component_assembler.py` | Any frontend shows it? |
| `resources/product_catalog/learned_products.jsonl` | `product_search.py:learn_product` | Only 1 entry ever? |
| `resources/furniture_templates/*.json` | Loaded? | Used in template dispatch? |
| `resources/furniture_template_graphs/*.json` | `template_loader.py` | 18 loaded, all dispatched? |

---

## Phase 4: Wire Tracing — Feature Completeness

For each feature, trace the ENTIRE wire from user to output:

### Feature: crawl-to-dxf
```
User clicks "Crawl & Digitize" button
  → CrawlInput.tsx: fetch(`${ENGINE_BASE}/crawl-to-dxf`)
    → Nginx: `/py-api/crawl-to-dxf` rewrite → `/api/crawl-to-dxf`
      → routes.py: POST /crawl-to-dxf
        → crawl_to_dxf.py: crawl_and_digitize()
          → crawl_for_image() — HTTP fetch page, extract hero image
          → extract_dimensions_from_page() — Shopify API + body_html
          → digitize via HTTP to /api/digitize/hybrid
          → comparison_agent.compare_digitization()
          → log_comparison_to_db()
    ← Response: {status, dxf_file, preview_svg, skeleton_svg, comparison}
  → CrawlInput.tsx renders: image, dimensions, skeleton, DXF download, score
```

**Check every step.** If any step fails silently or returns wrong data, the feature is broken.

### Feature: Templates tab
```
User clicks "Templates" tab
  → App.tsx: currentTab === 'templates' → <TemplatesPage />
    → TemplatesPage.tsx: fetch(`${ENGINE_BASE}/templates`)
      → routes.py: GET /templates
        → TemplateGraphLoader().load() → 18 JSON files
        → TemplateResolver(loader).resolve_all()
    ← Response: {templates, families, count}
  → TemplatesPage.tsx renders: SVG icons, parameter sliders, suggest button
    → Slider change → fetch(`${ENGINE_BASE}/templates/suggest?furniture_type=...`)
      → routes.py: GET /templates/suggest
        → TemplateResolver.resolve(furniture_type, detected_dims)
        → reference_ratio_solver.solve_missing_dimensions()
    ← Suggest response → update UI
```

### Feature: Calibration
```
User clicks "Calibration" tab
  → CalibrationPage.tsx: fetch(`${ENGINE_BASE}/calibration/report`)
    → routes.py: GET /calibration/report
      → training_feedback.aggregate_comparison_errors()
      → training_feedback.generate_correction_hints()
    ← Response: {comparison_stats, biases, hints}
  → Apply button → POST `${ENGINE_BASE}/calibration/apply`
    → routes.py: POST /calibration/apply
      → training_feedback.apply_calibration()
        → apply_correction_hints(hints)
        → save_parameter_state() → Postgres digitizer_parameters
    ← Response: {hints_applied, parameters}

**Auto-calibration**: After each comparison, log_comparison_to_db() checks
if count >=3 and count%3==0 → auto-runs generate_correction_hints() + apply_correction_hints()
```

---

## Phase 5: Database Schema Audit — Tables Created But Never Populated

```bash
# List all tables in Postgres
docker compose exec postgres psql -U postgres -d cad_reference_library -c "\dt"

# Check row counts
docker compose exec postgres psql -U postgres -d cad_reference_library -c "
SELECT schemaname,relname,n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"
```

| Table | Rows | Written By | Read By | Status |
|-------|------|-----------|---------|--------|
| `comparison_results` | 71 | `comparison_agent.py` | `training_feedback.py` | ✅ Active |
| `digitizer_parameters` | 9 | `training_feedback.py` | `digitizer_config.py` | ✅ Active |
| `engineering_analyses` | ? | `engineering_agent.py` | `/engineer/knowledge` | ⚠️ Check |
| `validation_results` | ? | `validation_service.py` | `/validate` routes | ⚠️ Check |
| `product_families` | ? | `/validate/product-units` | Unused | ❌ Dead? |
| `training_exports` | ? | `/validate/batch` | Unused | ❌ Dead? |
| `chat_sessions` | ? | ChatBox component | ChatBox | ⚠️ Check |

---

## Phase 6: Nginx Routing Audit — Every Location Must Reach a Backend

```nginx
location /py-api/ { rewrite ... proxy_pass http://python_worker; }
location /api/download/ { proxy_pass http://python_worker; }
location /api/preview/ { proxy_pass http://python_worker; }
location /api/upload { proxy_pass http://node_session_api; }
location /api/brain/ { proxy_pass http://node_session_api; }
location /api/cad-engine/ { proxy_pass http://node_session_api; }
location /api/ { proxy_pass http://node_ref_api; }
location /health { proxy_pass http://node_ref_api/health; }
location /health/py { proxy_pass http://python_worker/health; }
```

**Check**: Every `proxy_pass` destination must resolve and serve the expected content.

```bash
# Test each Nginx location
curl -s http://localhost:8080/py-api/health
curl -s http://localhost:8080/api/health
curl -s http://localhost:8080/py-api/templates
curl -s http://localhost:8080/api/product-references
```

---

## Phase 7: MCP Tool Audit — Every Tool Must Hit a Working Endpoint

```bash
# List all MCP tools
grep -A5 "name:" mcp-server/server.js | grep "name:"

# For each tool, verify:
# 1. The handler URL exists
grep "post\|get" mcp-server/server.js | grep PY_API
# 2. The API endpoint responds
curl -s http://localhost:8001/api/health
```

### MCP Tool → API Endpoint Mapping

| MCP Tool | API Endpoint | Status |
|----------|-------------|--------|
| `crawl_product_url` | `POST /api/crawl-to-dxf` | ✅/❌ |
| `list_templates` | `GET /api/templates` | ✅/❌ |
| `suggest_template` | `GET /api/templates/suggest` | ✅/❌ |
| `validate_dimensions` | `POST /api/verify` | ✅/❌ |
| `compare_digitization` | `POST /api/compare` | ✅/❌ |
| `get_calibration_report` | `GET /api/calibration/report` | ✅/❌ |
| `apply_corrections` | `POST /api/calibration/apply` | ✅/❌ |
| `update_parameter` | `POST /api/calibration/parameters/update` | ✅/❌ |
| `get_current_parameters` | `GET /api/calibration/parameters` | ✅/❌ |
| `get_comparison_results` | `GET /api/compare/results` | ✅/❌ |
| `get_analytics` | `GET /api/calibration/report + /parameters` | ✅/❌ |
| `cleanup_old_comparisons` | `POST /api/calibration/cleanup` | ✅/❌ |
| `engineering_analyze` | `POST /api/engineer/analyze` | ✅/❌ |
| `list_engineering_families` | `GET /api/engineer/families` | ✅/❌ |

---

## Phase 8: Frontend Tab Audit — Every Tab Must Load Without Console Errors

Open `http://localhost:8080` and click through EVERY tab. Check:

1. **Console errors** — any red errors in DevTools console
2. **Network errors** — any 4xx/5xx responses
3. **Blank pages** — tabs that render nothing
4. **Broken interactions** — buttons that do nothing on click
5. **Missing data** — sections that show "loading" forever

### Tab Checklist

| Tab | Loads? | Data Shows? | Interactions Work? | Console Errors? |
|-----|--------|-------------|-------------------|-----------------|
| Upload & Digitize | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| Crawl Product URL | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| Templates (18) | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| Calibration | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| Analytics | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| Resources | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| Improvements | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| Engineering | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| How It Works | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| API Docs (external) | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |

---

## Phase 9: End-to-End Pipeline Test

Run the complete pipeline and verify every output:

```bash
# 1. Crawl a product
curl -X POST http://localhost:8001/api/crawl-to-dxf \
  -H "Content-Type: application/json" \
  -d '{"url":"https://homeu.ph/products/tangerie-dining-table","category":"table"}'

# Verify: status=completed, dxf_file exists, preview_svg exists, 
#         skeleton_svg exists, comparison.overall_score > 0.7

# 2. Download the DXF
curl -o /tmp/test.dxf http://localhost:8001/api/download/{dxf_file}

# Verify: file size > 1000 bytes, valid DXF header

# 3. Run comparison
curl -X POST http://localhost:8001/api/compare \
  -H "Content-Type: application/json" \
  -d '{
    "job_id":"e2e-test","image_url":"{image_url}",
    "dxf_path":"/tmp/cad_digitizer_outputs/{dxf_file}"
  }'

# Verify: overall_score > 0.7, error_count < 5

# 4. Check calibration updated
curl http://localhost:8001/api/calibration/report
# Verify: comparison_stats.total incremented
```

---

## Phase 10: Dead Code Sweep — Patterns That Indicate Orphaned Features

### Pattern A: Module exists → Imported → But NEVER CALLED at runtime

```bash
# Example: check if component_assembler is actually called
grep -r "component_assembler" backend-python/ --include="*.py" | grep -v "__pycache__"
# If only the import exists but no function call → dead code
```

### Pattern B: API route exists → Frontend has fetch → But URL path is WRONG

```bash
# Example: frontend calls /api/xxx but Nginx sends it to wrong backend
grep -r "fetch.*api/" frontend/ --include="*.tsx" --include="*.ts"
# Compare against nginx.conf location blocks
```

### Pattern C: Database table created → INSERT written → But never SELECT'd

```bash
docker compose exec postgres psql -U postgres -d cad_reference_library -c "
SELECT relname, seq_scan, seq_tup_read, n_tup_ins, n_tup_upd, n_tup_del
FROM pg_stat_user_tables ORDER BY n_tup_ins DESC;"
```

### Pattern D: Feature demo exists → But no production integration

- A standalone script (`scripts/` directory) that demonstrates a feature but is never called by the pipeline
- A test file that tests a function that no production code uses
- A JSON resource with detailed data that no code ever loads

---

## Quick Sweep Commands

```bash
# 1. Find all Python imports and trace callers
echo "=== Orphaned Module Check ==="
for f in $(find backend-python/app -name "*.py" ! -name "__init__.py" ! -name "routes.py"); do
    module=$(basename $f .py)
    dir=$(dirname $f | sed 's|backend-python/app/||' | tr '/' '.')
    count=$(grep -r "from app\\.$dir\\.$module import\|from app\\.$dir import $module\|import app\\.$dir\\.$module" backend-python/app --include="*.py" | grep -v "$module.py:" | wc -l)
    if [ "$count" -eq 0 ]; then echo "  ORPHANED: $dir.$module"; fi
done

# 2. Find all API routes and check callers
echo "=== Dead Route Check ==="
grep -n "@router\.\(get\|post\|put\|delete\)" backend-python/app/api/routes.py | while IFS= read -r line; do
    route=$(echo $line | grep -oP '"/[^"]+"' | head -1)
    count_frontend=$(grep -r "$route" frontend/ --include="*.tsx" --include="*.ts" 2>/dev/null | wc -l)
    count_mcp=$(grep -r "$route" mcp-server/ --include="*.js" 2>/dev/null | wc -l)
    if [ "$count_frontend" -eq 0 ] && [ "$count_mcp" -eq 0 ]; then
        echo "  UNUSED ROUTE: $route (line $(echo $line | cut -d: -f1))"
    fi
done

# 3. Check database table usage
echo "=== Table Usage ==="
docker compose exec -T postgres psql -U postgres -d cad_reference_library -t -c "
SELECT relname, seq_scan, n_tup_ins FROM pg_stat_user_tables ORDER BY n_tup_ins DESC;" 2>/dev/null

# 4. Check resource file usage
echo "=== Resource File Usage ==="
for f in $(find resources/ -name "*.json"); do
    basename=$(basename $f .json)
    count=$(grep -r "$basename" backend-python/ --include="*.py" | wc -l)
    if [ "$count" -eq 0 ]; then echo "  UNUSED: $f"; fi
done
```

---

## Report Format

```
────────────────────────────────────────────
SENIOR ENGINEER AUDIT REPORT
────────────────────────────────────────────
Date: YYYY-MM-DD
Auditor: [Name]
Scope: [Feature / Tab / Module]

SUMMARY:
- Orphaned modules: X
- Dead routes: Y
- Unused resources: Z
- Broken wires: W

CRITICAL (data loss / crash risk):
1. [Module X] → [Issue] → [Fix]

HIGH (feature broken):
1. [Route Y] → [Issue] → [Fix]

MEDIUM (dead code):
1. [File Z] → Never imported → Remove

────────────────────────────────────────────
```
