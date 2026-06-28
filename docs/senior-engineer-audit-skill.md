# 🕵️ Senior Engineer Audit Skill — Wiring & Feature Verification

**Purpose:** Thoroughly audit a codebase as a senior engineer reviewing junior engineer work.  
**Focus:** Find features/resources that were built but NEVER USED. Find disconnected wires.  
**Output:** Clear list of orphans, zombies, and missing connections with fix instructions.

---

## Phase 1: Resource Inventory

**Goal:** Catalog every resource file and module, then check if it's actually referenced anywhere.

### 1.1 Scan All Resource Files
```bash
# List all resource files (JSON data, configs, templates)
find . -path ./node_modules -prune -o -path ./.git -prune -o -name "*.json" -print | sort
find . -path ./node_modules -prune -o -path ./.git -prune -o -name "*.yaml" -print | sort
```

### 1.2 Check Each Resource Is Imported/Referenced
For each resource file found, search the codebase for any reference to it:
```bash
# Example: check if a resource file is ever imported or read
grep -r "resources/supports/four_leg.json" --include="*.py" --include="*.js" --include="*.ts"
```

**Pass:** Resource appears in at least one `open()`, `read_text()`, `import`, or `require()` call.  
**FAIL:** Resource exists but is never read by any code → **ORPHAN**.

### 1.3 Check Configuration Resources
For config-like JSON files (templates, schemas, defaults):
```bash
# Check if the file contents are referenced by key
grep -r "template_id" --include="*.py" | grep "<value>"
# Check if the filename matches any string in code
grep -r "basename_of_file" --include="*.py" --include="*.js" --include="*.ts"
```

---

## Phase 2: Module Import Analysis

**Goal:** Find modules that are defined but never imported.

### 2.1 List All Python Modules
```bash
find . -name "*.py" -not -path "./.git/*" -not -path "./node_modules/*" -not -path "./__pycache__/*"
```

### 2.2 Check Each Module Is Imported
For each `.py` file, search for its import path across the whole codebase:
```bash
# Module at app/backend/foo/bar.py → search for "from app.backend.foo.bar" or "foo.bar"
grep -r "app.backend.foo.bar" --include="*.py"
grep -r "from.*foo.bar" --include="*.py" 
```

**Pass:** Module is imported in at least one other file.  
**FAIL:** Module exists but no other code imports it → **ZOMBIE MODULE**.

### 2.3 Check API Route Files
For every route registered in the API:
```bash
# List all @router.* decorators
grep -rn "@router\." --include="*.py" | grep -v "__pycache__"
# Check if referenced by frontend
grep -r "/api/endpoint_name" --include="*.ts" --include="*.tsx" --include="*.js"
```

**Pass:** Backend route + frontend client call both exist.  
**FAIL:** Backend route exists but no frontend calls it → **UNWIRED ENDPOINT**.

---

## Phase 3: Function & Class Usage Analysis

**Goal:** Find functions/classes that are defined but never called.

### 3.1 Check Builder Functions
For each `build_*_model()` or `save_*()` function:
```bash
grep -rn "def build_" --include="*.py"
# Check each is in a dispatch table or called directly
grep -rn "build_round_pedestal_model" --include="*.py"
```

**Pass:** Function appears in a dispatch dict OR is called directly.  
**FAIL:** Function exists but nothing calls it → **DEAD CODE**.

### 3.2 Check Utility Functions
```bash
grep -rn "def " --include="*.py" | grep -v "__" | grep -v "test_" | sort
```

For each utility, search for callers:
```bash
grep -rn "function_name" --include="*.py" | grep -v "def "
```

### 3.3 Check Class Definitions
```bash
grep -rn "^class " --include="*.py" | sort
```

For each class, check it's instantiated or subclassed somewhere.

---

## Phase 4: Feature Existence vs Usage

**Goal:** Find features that were implemented but never reached by users.

### 4.1 Frontend Component Audit
```bash
# List all frontend components
find frontend/components -name "*.tsx" | sort
# Check each is imported in App.tsx or another component
grep -r "import.*ComponentName" frontend/ --include="*.tsx"
```

**Pass:** Component is imported and rendered.  
**FAIL:** Component file exists but never imported → **ORPHAN UI**.

### 4.2 Frontend Service Audit
```bash
find frontend/services -name "*.ts" | sort
# Check each service is imported somewhere
grep -r "from.*services/" frontend/ --include="*.tsx" --include="*.ts"
```

### 4.3 Check Feature Flags
If the project uses feature flags or environment variables for gating:
```bash
grep -rn "os.environ.get\|os.getenv" --include="*.py"
# For each env var, check if it actually changes behavior
# Example: if OPENAI_API_KEY gates AI features, check what breaks without it
```

---

## Phase 5: Data Flow Tracing

**Goal:** Trace data from input → through pipeline → to output. Find breaks.

### 5.1 Pick a Feature, Trace End-to-End
```python
"""
Example: Trace "coffee_table depth dimension"
1. Input: User uploads photo with "D60" text
2. OCR reads "D60" → OCRDimension {text: "D60", value: 60}
3. DimensionAssociator matches to depth_cm key
4. ScaleSolver converts 60px to 60cm
5. dispatch_furniture("coffee_table", ...) passes depth_cm=60
6. save_coffee_table(path, width_cm=100, depth_cm=60, ...)
7. DXF exports (FRONT VIEW width, SIDE VIEW depth)
   OR: SVG preview renders depth visually

BREAK POINTS:
- If depth_cm is never used in save_coffee_table → DXF ignores it
- If depth_cm doesn't appear in _component_schema → slider doesn't exist
- If depth_cm appears in slider but SVG renderer ignores it → preview doesn't match
"""
```

### 5.2 Check Each Pipeline Stage Has a Consumer
For each data field produced by an earlier stage:
```bash
# Example: check that scale_solver output is consumed
grep -rn "scale|mm_per_px" --include="*.py" | grep -v "test_" | grep -v "def "
```

**Pass:** Output of stage N is read by stage N+1 (or final output).  
**FAIL:** Stage N produces a value that no later stage reads → **DEAD DATA**.

---

## Phase 6: Template & Resource Wiring

**Goal:** Find resource files that are beautifully crafted but never loaded.

### 6.1 Check Template Loading
```bash
# Find where templates are loaded
grep -rn "load_template\|read_text\|json.load" --include="*.py" | grep -i "template\|resource"
# Find which directories are scanned
grep -rn "glob\|listdir\|iterdir" --include="*.py" | grep -i "template\|resource\|json"
```

**Check:** Does the directory scanner actually match the resource directory structure?

### 6.2 Check Every Template ID is Referenced
```bash
# Extract all template_id values from JSON files
grep -rh "template_id" resources/ | sort -u
# Search for each in code
for id in $(grep -rh "template_id" resources/ | cut -d'"' -f4); do
  count=$(grep -r "$id" --include="*.py" --include="*.js" --include="*.ts" | wc -l)
  if [ "$count" -eq 0 ]; then echo "ORPHAN: $id"; fi
done
```

---

## Phase 7: The "Junior Engineer" Special

**Goal:** Find things that look perfect but don't work because of ONE missing wire.

### 7.1 Check Init Files
```bash
# List all __init__.py files — do they export what submodules define?
for f in $(find . -name "__init__.py" -not -path "./.git/*"); do
  dir=$(dirname "$f")
  for mod in $(grep -l "^class\|^def" "$dir"/*.py 2>/dev/null); do
    name=$(basename "$mod" .py)
    if ! grep -q "$name" "$f" 2>/dev/null; then
      echo "NOT EXPORTED: $name from $f"
    fi
  done
done
```

### 7.2 Check Try/Except Wrapping
```bash
# Find imports that are wrapped in try/except (may silently fail)
grep -B5 "except.*ImportError\|except.*Exception" --include="*.py" | grep "import "
```

These are often the source of "it works on my machine" bugs. If a dependency is missing, the import silently fails and a feature disappears.

### 7.3 Check for "Built But Never Connected" Patterns
Look for these specific patterns:
- A module with `__all__` defined but nothing imports from it
- A function that takes parameters that are NEVER passed from the caller
- A `**kwargs` that's never populated
- A default parameter that shadows a real value from upstream
- A `try/except: pass` that catches the one error that would tell you a feature is broken

---

## Phase 8: Report Format

For every finding, report:

```markdown
### ORPHAN/ZOMBIE/DEAD/UNWIRED: [name]
- **Type:** Resource / Module / Function / Feature / UI / Data
- **Location:** `path/to/file.ext:line`
- **Built by:** (agent name if known)
- **Symptoms:** What user would notice missing this
- **Wired to:** What SHOULD consume this but doesn't
- **Fix:** One-line description of what to connect
- **Severity:** Critical / High / Medium / Low
```

### Severity Guide:
| Severity | Criteria |
|----------|----------|
| **Critical** | Feature is completely invisible to users. Data loss or wrong output. |
| **High** | Feature partially works but key piece is missing. Wrong dimensions. |
| **Medium** | Feature works but misses niceties. Depth slider exists but DXF ignores it. |
| **Low** | Cosmetic. Dead code, unused imports, orphaned resources. |

---

## Quick Start Command

```bash
# Comprehensive audit in one command
echo "=== RESOURCES ==="
find resources -name "*.json" | wc -l
echo "=== MODULES ==="
find backend-python -name "*.py" -not -path "./.git/*" | wc -l
echo "=== FRONTEND COMPONENTS ==="
find frontend/components -name "*.tsx" | wc -l
echo "=== UI SERVICES ==="
find frontend/services -name "*.ts" | wc -l
echo "=== API ROUTES ==="
grep -rn "@router\." backend-python/app/api/routes.py | wc -l
echo "=== BUILDERS ==="
grep -rn "def build_\|def save_" backend-python/app/backend/ | wc -l
echo "=== DISPATCH ENTRIES ==="
grep -rn "FURNITURE_ADJUST_DISPATCH\|_dispatch_furniture" backend-python/app/api/routes.py | head -5
```

Then run each Phase above in order. Every finding goes into `AUDIT_REPORT.md` with the format above.
