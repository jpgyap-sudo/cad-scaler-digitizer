"""Resource Wiring Audit — Finds ALL resource files never referenced in code."""
import pathlib

root = pathlib.Path(".")
exclude_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", "image_pool", "outputs"}
code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".json", ".yaml", ".yml", ".toml", ".html"}

def is_excluded(p):
    for part in p.parts:
        if part in exclude_dirs or part.startswith("."):
            return True
    return False

# Find all resource JSON files (under resources/)
resources = list(root.rglob("resources/**/*.json"))
resources = [r for r in resources if not is_excluded(r)]
print(f"\n=== Resource JSON files: {len(resources)} ===")

# Find all code files
code_files = []
for ext in code_exts:
    for f in root.rglob(f"*{ext}"):
        if not is_excluded(f) and "resources/product_catalog/templates" not in str(f):
            code_files.append(f)
print(f"Code files to search: {len(code_files)}")

# Check each resource
loaded = 0
not_loaded = []
for res in resources:
    basename = res.name
    found = False
    for cf in code_files:
        try:
            content = cf.read_text(encoding="utf-8", errors="ignore")
            if basename in content:
                found = True
                break
        except:
            pass
    if found:
        loaded += 1
    else:
        not_loaded.append(str(res))

print(f"\nLoaded by code: {loaded}")
print(f"NOT loaded by any code: {len(not_loaded)}")
for nl in not_loaded:
    print(f"  ORPHAN: {nl}")

# Also check specific directories
for subdir in ["geometry", "supports", "joinery", "materials", "construction_rules", "dimension_styles"]:
    dir_res = [r for r in resources if f"/{subdir}/" in str(r) or f"\\{subdir}\\" in str(r)]
    dir_orphans = [r for r in dir_res if str(r) in not_loaded]
    if dir_orphans:
        print(f"\n  === {subdir}/: {len(dir_orphans)}/{len(dir_res)} orphaned ===")
        for o in dir_orphans:
            print(f"    {o}")
