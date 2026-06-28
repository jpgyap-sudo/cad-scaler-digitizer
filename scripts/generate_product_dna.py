#!/usr/bin/env python3
"""Generate per-product enriched DNA for all 259 products.

Output: resources/product_catalog/product_dna.json

Reads:
  - resources/product_catalog/_registry.json (per-product entries)
  - resources/product_catalog/visual_dna_index.json (per-family visual DNA)
  - resources/product_catalog/templates/*.json (optional per-template overrides)

Enriches each product with: edge_profile, thickness_profile, leg_count,
symmetry, bounding_ratio, component_list, material_primary.

Uses smart heuristics from template_family, tags, title, product_type.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("generate_product_dna")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CATALOG_DIR = REPO_ROOT / "resources" / "product_catalog"
REGISTRY_PATH = CATALOG_DIR / "_registry.json"
DNA_INDEX_PATH = CATALOG_DIR / "visual_dna_index.json"
OUTPUT_PATH = CATALOG_DIR / "product_dna.json"
TEMPLATES_DIR = CATALOG_DIR / "templates"

# ---------------------------------------------------------------------------
# Heuristic tables
# ---------------------------------------------------------------------------

# Edge profile by keyword in family name
EDGE_RULES: List[tuple] = [
    (r"ceiling_fan", "beveled"),
    (r"wall_panel|panel", "square"),
    (r"stone|slab|sintered", "square"),
    (r"rug|carpet", "square"),
    (r"bed|headboard", "square"),
    (r"pillow|throw", "rounded"),
    (r"sofa|bench", "rounded"),
    (r"armchair|lounge_chair", "rounded"),
    (r"ottoman|pouf", "rounded"),
    (r"bar_stool|stool", "rounded"),
    (r"pendant|light|chandelier|lamp|sconce", "rounded"),
    (r"dining_chair|chair", "rounded"),
    (r"dining_table|table", "bullnose"),
    (r"sideboard|console|buffet", "bullnose"),
    (r"side_table|coffee_table", "bullnose"),
    (r"pedestal|drum", "bullnose"),
    (r"wardrobe|cabinet", "square"),
    (r"desk|workstation", "bullnose"),
]

# Thickness by family
THICKNESS_RULES: List[tuple] = [
    (r"stone|slab|sintered", "slim"),
    (r"wall_panel|panel", "slim"),
    (r"rug|carpet", "slim"),
    (r"pillow|throw", "slim"),
    (r"pendant|light|chandelier|lamp|sconce|ceiling_fan", "slim"),
    (r"ottoman|pouf", "thick"),
    (r"sofa|armchair|lounge", "medium"),
    (r"dining_table|table", "medium"),
    (r"dining_chair|chair|stool", "medium"),
    (r"bed|headboard", "medium"),
    (r"sideboard|console|buffet", "medium"),
    (r"side_table|coffee_table", "medium"),
    (r"wardrobe|cabinet|desk", "medium"),
]

# Leg count by family
LEG_COUNT_RULES: List[tuple] = [
    (r"wall_panel|panel", 0),
    (r"stone|slab|sintered", 0),
    (r"ceiling_fan|fan", 0),
    (r"pendant|light|chandelier|lamp|sconce", 0),
    (r"rug|carpet", 0),
    (r"pillow|throw", 0),
    (r"bed|headboard", 0),
    (r"single_pedestal|drum|cone", 1),
    (r"dual_pedestal|twin_pedestal", 2),
    (r"sectional|l_shaped", 5),
    (r"sofa|bench|ottoman|pouf|stool", 4),
    (r"dining_table|table", 4),
    (r"dining_chair|chair|armchair|lounge", 4),
    (r"sideboard|console|buffet", 4),
    (r"coffee_table|side_table", 4),
    (r"wardrobe|cabinet|desk", 0),  # plinth or wall
]

# Symmetry by family
SYMMETRY_RULES: List[tuple] = [
    (r"asymmetric|organic|l_shape|sectional|offset", "asymmetric"),
    (r"ceiling_fan|fan", "radial"),
    (r"pendant|light|chandelier|lamp|sconce", "radial"),
    (r"round_drum|drum|cone", "radial"),
    (r"sofa|bench", "bilateral"),
    (r"armchair|lounge_chair|chair", "bilateral"),
    (r"dining_table|table", "bilateral"),
    (r"sideboard|console|buffet|desk", "bilateral"),
    (r"coffee_table|side_table", "bilateral"),
    (r"ottoman|pouf|stool", "bilateral"),
    (r"bed|headboard", "bilateral"),
    (r"wall_panel|panel", "bilateral"),
    (r"rug|carpet", "bilateral"),
    (r"pillow|throw", "bilateral"),
    (r"stone|slab|sintered", "bilateral"),
    (r"wardrobe|cabinet", "bilateral"),
]

# Bounding ratio by family
BOUNDING_RATIO_RULES: List[tuple] = [
    (r"sofa|bench|sofa_bench", "2.5:1:0.8"),
    (r"armchair|lounge_chair", "1:1:1"),
    (r"dining_table", "1.6:1:0.6"),
    (r"coffee_table", "1.6:1:0.35"),
    (r"dining_chair", "0.8:0.8:1.2"),
    (r"bar_stool", "0.5:0.5:1.5"),
    (r"pendant", "0.3:0.3:0.5"),
    (r"ceiling_fan", "1:1:0.15"),
    (r"stone|slab", "1.6:1:0.02"),
    (r"pillow|throw", "1:1:0.2"),
    (r"lamp|sconce", "0.2:0.2:2"),
    (r"console|sideboard", "2:0.5:0.6"),
    (r"wall_panel|panel", "1:1.5:0.05"),
    (r"rug|carpet", "2:1.5:0.01"),
    (r"stool|ottoman|pouf", "0.6:0.6:0.8"),
    (r"bed|headboard", "1.8:1:0.08"),
    (r"wardrobe|cabinet", "1:0.6:2"),
    (r"desk|workstation", "2:0.6:0.7"),
    (r"side_table|end_table", "0.5:0.5:0.6"),
]

# Material primary by tags / product_type / title
MATERIAL_RULES: List[tuple] = [
    (r"sintered|granite|marble|quartz", "stone"),
    (r"stone_slab|stone", "stone"),
    (r"lighting|lamp|light|pendant|chandelier|sconce|ceiling_fan", "metal"),
    (r"pillow|throw|cushion|fabric|upholstery", "fabric"),
    (r"rug|carpet|textile|mat", "textile"),
    (r"wood|oak|walnut|teak|mahogany|birch", "wood"),
    (r"glass|crystal", "glass"),
    (r"metal|steel|iron|aluminum|brass", "metal"),
    (r"leather", "leather"),
    (r"plastic|acrylic|resin", "plastic"),
    (r"wall_panel|fluted|slat|wpc", "wood"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match_rule(text: str, rules: List[tuple], fallback: Any) -> Any:
    """Return first matching rule value or fallback."""
    for pattern, value in rules:
        if re.search(pattern, text, re.IGNORECASE):
            return value
    return fallback


def _extract_material(title: str, tags: List[str], product_type: str, family: str) -> str:
    """Infer primary material from all available signals."""
    signals = [title.lower(), product_type.lower(), family.lower()] + [t.lower() for t in tags]
    combined = " ".join(signals)
    for pattern, material in MATERIAL_RULES:
        if re.search(pattern, combined, re.IGNORECASE):
            return material
    # Check title for common material words
    title_lower = title.lower()
    for word in ["stone", "metal", "wood", "fabric", "glass", "leather", "marble", "plastic"]:
        if word in title_lower:
            return word
    return "wood"


def _get_family_key(family: str, dna_index: Dict[str, Any]) -> Optional[str]:
    """Find the best matching dna_index key for this family name."""
    if family in dna_index:
        return family
    # Fuzzy: key starts with same words
    family_words = set(family.lower().replace("-", "_").split("_"))
    best_key = None
    best_score = 0
    for key in dna_index:
        key_words = set(key.lower().split("_"))
        overlap = len(family_words & key_words)
        if overlap > best_score:
            best_score = overlap
            best_key = key
    if best_score >= 2:
        return best_key
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_product_dna() -> Dict[str, Any]:
    """Generate per-product enriched DNA."""
    # Load registry
    if not REGISTRY_PATH.exists():
        log.error(f"Registry not found: {REGISTRY_PATH}")
        sys.exit(1)
    registry: List[Dict] = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    log.info(f"Loaded {len(registry)} products from registry")

    # Load DNA index
    dna_index: Dict = {}
    if DNA_INDEX_PATH.exists():
        dna_index = json.loads(DNA_INDEX_PATH.read_text(encoding="utf-8"))
    log.info(f"Loaded {len(dna_index)} families from DNA index")

    # Build output
    output: Dict[str, Any] = {}
    skipped = 0

    for entry in registry:
        handle = entry.get("handle", "")
        if not handle:
            skipped += 1
            continue

        title = entry.get("title", "")
        family = entry.get("template_family", "")
        product_type = entry.get("product_type", "")
        tags = entry.get("tags", [])
        components = entry.get("components", [])
        batch = entry.get("batch", 0)

        # Combined text for matching
        match_text = f"{family} {title} {product_type} {' '.join(tags)}"

        # Enriched fields
        edge = _match_rule(match_text, EDGE_RULES, "square")
        thickness = _match_rule(match_text, THICKNESS_RULES, "medium")
        leg_count = _match_rule(match_text, LEG_COUNT_RULES, 4)
        symmetry = _match_rule(match_text, SYMMETRY_RULES, "bilateral")
        bounding = _match_rule(match_text, BOUNDING_RATIO_RULES, "1.65:1:0.42")
        material = _extract_material(title, tags, product_type, family)

        # Look up DNA family
        dna_key = _get_family_key(family, dna_index)
        dna_family_data = dna_index.get(dna_key, {}) if dna_key else {}

        # Build product entry
        product_dna = {
            "handle": handle,
            "title": title,
            "template_family": family,
            "product_type": product_type,
            "tags": tags,
            "edge_profile": edge,
            "thickness_profile": thickness,
            "leg_count": leg_count,
            "symmetry": symmetry,
            "bounding_ratio": bounding,
            "component_list": components,
            "material_primary": material,
            "category_hint": dna_family_data.get("category_hint", product_type.lower()),
            "batch": batch,
            "visual_dna_family": dna_key,
            # Copy enriched visual fields from family
            "top_shape": dna_family_data.get("top_shape", ""),
            "base_type": dna_family_data.get("base_type", ""),
            "leg_type": dna_family_data.get("leg_type", ""),
            "materials": dna_family_data.get("materials", []),
            "archetype_score": dna_family_data.get("archetype_score", 0.5),
        }
        output[handle] = product_dna

    log.info(f"Generated DNA for {len(output)} products ({skipped} skipped)")
    return output


if __name__ == "__main__":
    log.info("=== Generating Product DNA ===")
    dna = generate_product_dna()

    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(dna, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info(f"Written to {OUTPUT_PATH}")
    log.info(f"Total products: {len(dna)}")

    # Quick stats
    edge_counts: Dict[str, int] = {}
    sym_counts: Dict[str, int] = {}
    mat_counts: Dict[str, int] = {}
    for v in dna.values():
        e = v["edge_profile"]
        edge_counts[e] = edge_counts.get(e, 0) + 1
        s = v["symmetry"]
        sym_counts[s] = sym_counts.get(s, 0) + 1
        m = v["material_primary"]
        mat_counts[m] = mat_counts.get(m, 0) + 1
    log.info(f"Edge profiles: {dict(sorted(edge_counts.items()))}")
    log.info(f"Symmetry: {dict(sorted(sym_counts.items()))}")
    log.info(f"Materials: {dict(sorted(mat_counts.items()))}")
