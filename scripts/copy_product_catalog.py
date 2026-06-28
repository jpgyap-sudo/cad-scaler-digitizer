"""Copy all 259+ Shopify templates from temp_batch* to resources/product_catalog/templates/
and build _registry.json."""
import json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "resources" / "product_catalog"
TEMPLATES_DIR = CATALOG_DIR / "templates"

BATCH_MAP = {
    "temp_batch1": {"dir": "templates", "schema": "homeu-template-v1", "batch": 1},
    "temp_batch2": {"dir": "templates", "schema": "homeu-template-v1", "batch": 2},
    "temp_batch3": {"dir": "templates", "schema": "homeu-template-v1", "batch": 3},
    "temp_batch4/homeu_shopify_templates_batch4_regenerated": {"dir": "templates", "schema": "homeu-product-template-v1", "batch": 4},
    "temp_batch5/homeu_shopify_templates_batch5": {"dir": "templates", "schema": "homeu-template-v1", "batch": 5},
    "temp_batch6/homeu_shopify_templates_batch6": {"dir": "templates", "schema": "homeu-template-v1", "batch": 6},
}

def ensure_dir():
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

def copy_all():
    registry = []
    for rel, config in BATCH_MAP.items():
        src_dir = ROOT / rel / config["dir"]
        if not src_dir.exists():
            print(f"WARN: {src_dir} not found, skipping")
            continue
        batch_num = config["batch"]
        for f in sorted(src_dir.glob("*.json")):
            # Copy file
            dest = TEMPLATES_DIR / f.name
            shutil.copy2(str(f), str(dest))
            # Load to extract metadata
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"WARN: failed to parse {f.name}: {e}")
                data = {}
            title = data.get("product_title") or data.get("title") or f.stem.replace("_", " ").replace("-", " ").title()
            handle = data.get("handle") or f.stem
            family = data.get("template_family") or "unknown"
            tags = data.get("tags", [])
            product_type = data.get("product_type", "")
            schema_ver = data.get("schema_version", config["schema"])
            components = data.get("components", [])
            views = data.get("views_required", [])
            entry = {
                "id": f"homeu_b{batch_num}_{f.stem}",
                "title": title,
                "handle": handle,
                "template_family": family,
                "product_type": product_type,
                "tags": tags,
                "components": components,
                "views_required": views,
                "schema_version": schema_ver,
                "batch": batch_num,
                "file": f.name,
                "source_batch_dir": rel,
            }
            registry.append(entry)
            print(f"  [{batch_num}] {f.name} -> {family}")
    # Write registry
    registry_path = CATALOG_DIR / "_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nCopied {len(registry)} templates to {TEMPLATES_DIR}")
    print(f"Registry written to {registry_path}")
    return registry

if __name__ == "__main__":
    ensure_dir()
    registry = copy_all()
    # Quick stats
    families = set(e["template_family"] for e in registry)
    print(f"\nUnique families: {len(families)}")
    for b in sorted(set(e["batch"] for e in registry)):
        cnt = sum(1 for e in registry if e["batch"] == b)
        print(f"  Batch {b}: {cnt} templates")
