"""
Batch Import Templates → Visual DNA Catalog
=============================================
Processes all homeu_shopify_templates_batch*.zip files and
homeu_shopify_live_products_batch*.zip from the downloads directory,
extracts product handles, tags, components, and populates the visual
DNA catalog (product_dna.json + visual_dna_index.json).

Run once after deploying the 3-stage classifier to seed the DNA catalog
with hundreds of entries instead of starting empty.
"""

import json
import logging
import os
import sys
import tarfile
import tempfile
import zipfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend-python"))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("dna_importer")

# Where the batch ZIPs live
DEFAULT_SOURCE = r"C:\Users\user\Downloads\visual dan"

# Where product_dna.json and visual_dna_index.json live
CATALOG_DIR = Path(__file__).resolve().parents[1] / "resources" / "product_catalog"


def _extract_tags(template: dict) -> list:
    """Get tags from a template entry."""
    tags = template.get("tags", [])
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",")]
    return list(tags) if isinstance(tags, list) else []


def _classify_family(template: dict, handle: str, tags: list) -> str:
    """Derive furniture family from template JSON fields."""
    # Check template_family first
    tpl_family = template.get("template_family", "")
    if tpl_family and tpl_family not in ("generic", "unknown"):
        # Map some template families to standard types
        family_map = {
            "sculptural_single_support_console": "console_table",
            "four_leg_rectangular": "rectangular_table",
            "pedestal_round": "round_pedestal_table",
            "pedestal_oval": "oval_pedestal_table",
            "standard_sofa": "sofa",
            "sectional_sofa": "sectional",
            "lounge_chair": "lounge_chair",
            "dining_chair": "dining_chair",
            "counter_stool": "bar_stool",
            "floor_lamp": "floor_lamp",
            "pendant_light": "pendant_light",
            "wall_sconce": "wall_sconce",
            "coffee_table": "coffee_table",
            "side_table": "side_table",
            "nightstand": "nightstand",
            "dresser": "cabinet",
            "wardrobe": "wardrobe",
            "desk": "office_desk",
            "console_table": "console_table",
            "bed_frame": "bed",
            "headboard": "bed_headboard",
            "ottoman": "ottoman_pouf",
            "bench": "bench_chaise",
        }
        for k, v in family_map.items():
            if k in tpl_family.lower():
                return v

    # Fallback: infer from tags
    tag_lower = " ".join(t.lower() for t in tags)

    if "sofa" in tag_lower or "couch" in tag_lower:
        return "sofa"
    if "chair" in tag_lower:
        return "dining_chair"
    if "table" in tag_lower:
        if "console" in tag_lower or "side" in tag_lower:
            return "console_table"
        if "coffee" in tag_lower or "cocktail" in tag_lower:
            return "coffee_table"
        if "night" in tag_lower or "bedside" in tag_lower:
            return "nightstand"
        return "rectangular_table"
    if "lamp" in tag_lower or "light" in tag_lower or "pendant" in tag_lower:
        return "pendant_light"
    if "bed" in tag_lower:
        return "bed"
    if "cabinet" in tag_lower or "storage" in tag_lower or "dresser" in tag_lower:
        return "cabinet"
    if "desk" in tag_lower:
        return "office_desk"
    if "stool" in tag_lower:
        return "bar_stool"
    if "ottoman" in tag_lower or "pouf" in tag_lower:
        return "ottoman_pouf"
    if "bench" in tag_lower:
        return "bench_chaise"
    if "rug" in tag_lower or "carpet" in tag_lower:
        return "rug_rectangular"

    # From handle as last resort
    handle_lower = handle.lower()
    if any(k in handle_lower for k in ["sofa", "couch"]):
        return "sofa"
    if "chair" in handle_lower and "table" not in handle_lower:
        return "dining_chair"
    if "table" in handle_lower:
        return "rectangular_table"
    if "lamp" in handle_lower or "light" in handle_lower:
        return "pendant_light"
    if "bed" in handle_lower:
        return "bed"
    if "cabinet" in handle_lower:
        return "cabinet"
    if "desk" in handle_lower:
        return "office_desk"
    if "stool" in handle_lower:
        return "bar_stool"
    if "ottoman" in handle_lower:
        return "ottoman_pouf"
    if "rug" in handle_lower:
        return "rug_rectangular"

    return "furniture"


def _infer_dimensions(handle: str, tags: list) -> dict:
    """Infer plausible dimensions from product context."""
    tag_lower = " ".join(t.lower() for t in tags)
    handle_lower = handle.lower()

    # Sofa dimensions
    if "sofa" in tag_lower or "sofa" in handle_lower:
        if "loveseat" in tag_lower or "loveseat" in handle_lower or "2-seater" in tag_lower:
            return {"width_cm": 140, "depth_cm": 85, "overall_height_cm": 82}
        if "sectional" in tag_lower or "sectional" in handle_lower:
            return {"width_cm": 280, "depth_cm": 95, "overall_height_cm": 82}
        return {"width_cm": 200, "depth_cm": 85, "overall_height_cm": 82}

    # Chair dimensions
    if "chair" in tag_lower or "chair" in handle_lower:
        if "dining" in tag_lower or "dining" in handle_lower:
            return {"width_cm": 45, "depth_cm": 45, "overall_height_cm": 90}
        if "arm" in tag_lower or "lounge" in tag_lower:
            return {"width_cm": 70, "depth_cm": 75, "overall_height_cm": 90}
        if "office" in tag_lower or "task" in tag_lower:
            return {"width_cm": 50, "depth_cm": 48, "overall_height_cm": 120}
        return {"width_cm": 50, "depth_cm": 50, "overall_height_cm": 85}

    # Table dimensions
    if "table" in tag_lower or "table" in handle_lower:
        if "console" in tag_lower or "console" in handle_lower:
            return {"width_cm": 120, "depth_cm": 40, "overall_height_cm": 75}
        if "coffee" in tag_lower or "coffee" in handle_lower:
            return {"width_cm": 100, "depth_cm": 60, "overall_height_cm": 45}
        if "dining" in tag_lower or "dining" in handle_lower:
            return {"width_cm": 160, "depth_cm": 80, "overall_height_cm": 75}
        if "side" in tag_lower or "side" in handle_lower or "night" in tag_lower:
            return {"width_cm": 50, "depth_cm": 40, "overall_height_cm": 60}
        if "desk" in tag_lower or "desk" in handle_lower:
            return {"width_cm": 120, "depth_cm": 60, "overall_height_cm": 75}
        return {"width_cm": 120, "depth_cm": 80, "overall_height_cm": 75}

    # Bed dimensions
    if "bed" in tag_lower or "bed" in handle_lower:
        return {"width_cm": 160, "depth_cm": 200, "overall_height_cm": 100}

    # Cabinet dimensions
    if "cabinet" in tag_lower or "cabinet" in handle_lower or "storage" in tag_lower:
        return {"width_cm": 80, "depth_cm": 40, "overall_height_cm": 180}

    # Lighting
    if "lamp" in tag_lower or "light" in tag_lower or "pendant" in tag_lower:
        return {"width_cm": 40, "depth_cm": 40, "overall_height_cm": 80}

    return {"width_cm": 80, "depth_cm": 60, "overall_height_cm": 100}


def batch_import(source_dir: str = None) -> int:
    """Import all template ZIPs from the source directory into the DNA catalog."""
    source = Path(source_dir or DEFAULT_SOURCE)
    if not source.exists():
        logger.error(f"Source directory not found: {source}")
        return 0

    # Import enrich_dna_from_crawl
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend-python"))
    from app.backend.product_classifier import enrich_dna_from_crawl

    zip_files = sorted(source.glob("*.zip"))
    logger.info(f"Found {len(zip_files)} ZIP files in {source}")

    total_imported = 0
    total_skip = 0
    handled_handles = set()

    # Also load existing product_dna.json to avoid duplicates
    existing_dna = {}
    dna_path = CATALOG_DIR / "product_dna.json"
    if dna_path.exists():
        try:
            existing_dna = json.loads(dna_path.read_text(encoding="utf-8"))
            handled_handles.update(existing_dna.keys())
            logger.info(f"Loaded {len(handled_handles)} existing DNA entries")
        except Exception:
            pass

    for zip_path in zip_files:
        logger.info(f"\nProcessing: {zip_path.name}")
        try:
            if str(zip_path).endswith('.tar.gz') or str(zip_path).endswith('.tgz'):
                # tar.gz extraction
                extract_dir = Path(tempfile.mkdtemp())
                try:
                    with tarfile.open(zip_path, "r:gz") as tar:
                        tar.extractall(path=extract_dir)
                    templates_dir = extract_dir / "templates"
                    if templates_dir.exists():
                        json_files = list(templates_dir.glob("*.json"))
                    else:
                        json_files = list(extract_dir.rglob("*.json"))
                        # Exclude index files
                        json_files = [f for f in json_files if f.name not in ("catalog_index.json", "visual_dna_index.json", "_registry.json")]
                    shutil.rmtree(extract_dir, ignore_errors=True)
                except Exception:
                    json_files = []
            else:
                # Standard ZIP extraction
                extract_dir = Path(tempfile.mkdtemp())
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        zf.extractall(path=extract_dir)
                    templates_dir = extract_dir / "templates"
                    if templates_dir.exists():
                        json_files = list(templates_dir.glob("*.json"))
                    else:
                        json_files = list(extract_dir.rglob("*.json"))
                        json_files = [f for f in json_files if f.name not in ("catalog_index.json", "visual_dna_index.json", "_registry.json")]
                    shutil.rmtree(extract_dir, ignore_errors=True)
                except Exception as e:
                    logger.error(f"  ZIP error: {e}")
                    json_files = []

            logger.info(f"  {len(json_files)} template JSONs")
            batch_count = 0
            for jf in json_files:
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                except Exception:
                    total_skip += 1
                    continue

                handle = data.get("handle", "")
                if not handle or handle in handled_handles:
                    total_skip += 1
                    continue

                tags = _extract_tags(data)
                family = _classify_family(data, handle, tags)
                dims = _infer_dimensions(handle, tags)

                enriched = enrich_dna_from_crawl(
                    handle=handle,
                    furniture_type=family,
                    family=family.split("_")[0] if "_" in family else family,
                    dimensions=dims,
                    skeleton_svg="",
                    hero_view_added=False,
                )
                if enriched:
                    handled_handles.add(handle)
                    total_imported += 1
                    batch_count += 1
                else:
                    total_skip += 1

            logger.info(f"  → {batch_count} imported (cumulative: {total_imported})")
        except Exception as e:
            logger.error(f"  Error processing {zip_path.name}: {e}")

    logger.info(f"\n{'='*60}")
    logger.info(f"Batch import complete: {total_imported} new products, {total_skip} skipped")
    logger.info(f"product_dna.json → {CATALOG_DIR / 'product_dna.json'}")
    logger.info(f"visual_dna_index.json → {CATALOG_DIR / 'visual_dna_index.json'}")
    logger.info(f"{'='*60}")
    return total_imported


if __name__ == "__main__":
    batch_import()
