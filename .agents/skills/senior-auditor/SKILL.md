# 🕵️ Senior Auditor — Codebase Wiring & Orphan Detection Skill

**Description:** Thorough codebase audit that checks every resource, module, function, and frontend component is actually wired to something. Finds features that were built but never connected, templates that are never loaded, and data that's produced but never consumed.

**Invoke:** Reference this skill when asked to "audit the codebase", "check for orphans", "find dead code", or "verify wiring".

---

## What This Skill Does

Acts as a senior engineer reviewing junior engineer work. The single biggest class of bugs is NOT syntax errors — it's **features that were built but never wired**. A beautiful `save_coffee_table()` function that's never in the dispatch table. A 400-line template system that's never loaded. An AI vision pipeline that silently fails because the import is wrapped in `try/except: pass`.

This skill finds ALL of those.

---

## Phase 1: Resource → Code Wiring

### Every resource file must be loaded by some code.

```bash
# List all JSON resource files
find resources -name "*.json" -not -path "./.git/*" | sort > /tmp/all_resources.txt
```

For each resource file, check if any Python/JS/TS code reads it:
```bash
echo "=== UNLOADED RESOURCES ==="
while IFS= read -r file; do
  basename=$(basename "$file")
  # Search for the filename being opened/read
  matches=$(grep -rl "$basename" --include="*.py" --include="*.js" --include="*.ts" \
    --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=__pycache__ . 2>/dev/null | wc -l)
  if [ "$matches" -eq 0 ]; then
    echo "ORPHAN: $file (never read by any code)"
  fi
done < /tmp/all_resources.txt
```

**Key targets:** `resources/geometry/`, `resources/supports/`, `resources/joinery/`, `resources/furniture_templates/`, `resources/materials/`

---

## Phase 2: Module → Import Wiring

### Every Python module must be imported by something.

```bash
# List all non-test, non-init Python files
find backend-python -name "*.py" -not -path "*/tests/*" -not -name "__init__.py" -not -path "./.git/*" \
  -not -path "*/__pycache__/*" | sort > /tmp/all_modules.txt
```

For each module, check it's imported elsewhere:
```bash
echo "=== ZOMBIE MODULES (defined but never imported) ==="
while IFS= read -r file; do
  # Convert filesystem path to Python import path
  rel=$(echo "$file" | sed 's|backend-python/||;s|/|.|g;s|\.py$||')
  # Count non-self imports
  imports=$(grep -rl "$rel" --include="*.py" --exclude-dir=.git --exclude-dir=__pycache__ . 2>/dev/null | \
    grep -v "$file" | wc -l)
  if [ "$imports" -eq 0 ]; then
    echo "ZOMBIE: $rel ($file)"
  fi
done < /tmp/all_modules.txt
```

---

## Phase 3: Function → Caller Wiring

### Every public function must be called from somewhere.

```bash
echo "=== UNUSED BUILDER FUNCTIONS ==="
for func in $(grep -rn "^def build_\|^def save_" backend-python/app/backend/ --include="*.py" | \
  sed 's/.*def \([^(]*\).*/\1/'); do
  calls=$(grep -rl "$func" --include="*.py" --exclude-dir=.git --exclude-dir=__pycache__ \
    --exclude-dir=tests . 2>/dev/null | grep -v "$(grep -rl "def $func" --include="*.py")" | wc -l)
  if [ "$calls" -eq 0 ]; then
    echo "DEAD: $func"
  fi
done
```

**Special check:** Even if a function IS called, check if it's in the DISPATCH TABLE:
```bash
grep -n "FURNITURE_ADJUST_DISPATCH\|_dispatch_furniture\|_get_adjust_fn" backend-python/app/api/routes.py
```

A beautiful `save_coffee_table()` is useless if `FURNITURE_ADJUST_DISPATCH` maps "coffee_table" to something else.

---

## Phase 4: Frontend Component → Render Wiring

### Every component must be rendered somewhere.

```bash
echo "=== ORPHAN FRONTEND COMPONENTS ==="
find frontend/components -name "*.tsx" | while IFS= read -r file; do
  basename=$(basename "$file" .tsx)
  imports=$(grep -rl "$basename" frontend/ --include="*.tsx" --include="*.ts" 2>/dev/null | \
    grep -v "$file" | wc -l)
  if [ "$imports" -eq 0 ]; then
    echo "ORPHAN UI: $file (never imported by any other component)"
  fi
done
```

---

## Phase 5: Data Flow Tracing (The Most Important)

### Trace ONE feature end-to-end. Find the broken link.

```python
"""
For each furniture type (coffee_table, sofa, cabinet, etc.), trace:

1. INPUT → User uploads photo with dimension text
2. OCR reads text → OCRDimension(value, confidence)
3. DimensionAssociator matches text to geometry
4. ScaleSolver converts pixels to mm
5. FurnitureClassifier determines type
6. smart_workflow.py selects route (opencv/hybrid)
7. _dispatch_furniture() maps type → save_*() function
8. save_*() generates DXF with dimension text

CHECK EACH LINK:
- Is the dimension text matched to the right key?
- Is the key in _component_schema() for that type?
- Does save_*() actually USE that key in its geometry math?
- Does the SVG preview reflect the same value?

SPECIAL: Check if a parameter is ACCEPTED but IGNORED.
Example: save_cabinet(width_cm, depth_cm, height_cm) draws
front view with width and height, but depth_cm is NEVER used.
→ User adjusts depth slider → nothing changes visually.
"""
```

### Check dispatch table completeness:
```bash
echo "=== DISPATCH TABLE vs BUILDER FUNCTIONS ==="
# List all builder types from dispatch
grep -oP '"\w+":\s*\(' backend-python/app/api/routes.py | sed 's/":\s*(/:)' | sort > /tmp/dispatch.txt
# List all save_ functions
grep -oP 'def save_\w+' backend-python/app/backend/dxf_exporter.py | sed 's/def save_//' | sort > /tmp/savers.txt
# Compare
diff /tmp/dispatch.txt /tmp/savers.txt || echo "MISMATCH between dispatch table and save functions"
```

---

## Phase 6: The Silent Failure Check

### Find imports that silently fail.

```bash
echo "=== SILENT IMPORT FAILURES ==="
grep -B5 "except.*ImportError\|except.*Exception" --include="*.py" backend-python/app/ \
  | grep "import " | grep -v "test_"
```

Each of these is a feature that DISAPPEARS silently if a dependency is missing.

### Find try/except:pass blocks that hide errors.
```bash
echo "=== SILENT EXCEPT BLOCKS ==="
grep -A1 "except.*:" --include="*.py" backend-python/app/ | grep "^\s*pass\s*$" | head -20
```

---

## Phase 7: Report Template

All findings go into `AUDIT_REPORT.md` with this format:

```markdown
### [TYPE]: [name]
- **Location:** `file.py:line`
- **Severity:** Critical/High/Medium/Low
- **Symptom:** What the user experiences
- **Built:** Module exists and works in isolation
- **Broken:** Never called/imported/rendered
- **Fix:** One specific change to connect it
```

**Severity guide:**
| Severity | What it means |
|----------|---------------|
| **Critical** | Feature is invisible to users. Wrong output or crashes. |
| **High** | Feature partially works but key part missing. |
| **Medium** | Feature works but misses polish. Depth slider does nothing. |
| **Low** | Dead code, unused imports, orphaned resources. |

---

## One-Command Audit

```bash
echo "=== QUICK AUDIT ==="
echo "Resources:"; find resources -name "*.json" | wc -l
echo "Python modules:"; find backend-python -name "*.py" -not -path "*/tests/*" -not -path "*/__pycache__/*" | wc -l
echo "Frontend components:"; find frontend/components -name "*.tsx" | wc -l
echo "API routes:"; grep -rn "@router\." backend-python/app/ | wc -l
echo "Save functions:"; grep -rn "^def save_" backend-python/app/backend/dxf_exporter.py | wc -l
echo "Build functions:"; grep -rn "^def build_" backend-python/app/backend/ | wc -l
echo "=== RUN FULL AUDIT ==="
# Then run Phases 1-6 above
```
