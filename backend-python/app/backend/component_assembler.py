"""Component Assembler — LEGO-like furniture assembly from product DNA.

Takes a product DNA entry and assembles it from reusable components
defined in component_library.json. Components are positioned relative
to each other (top above pedestal, backrest behind seat, etc.)

Usage:
    result = assemble_from_dna("melina-coffee-table")
    result = assemble_from_handle("oval-pedestal-coffee-table", dna_entry)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("component_assembler")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CATALOG_DIR = Path(__file__).resolve().parents[2] / "resources" / "product_catalog"
COMPONENT_LIB_PATH = CATALOG_DIR / "component_library.json"
DNA_PATH = CATALOG_DIR / "product_dna.json"

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------
_COMPONENT_CACHE: Dict[str, Any] | None = None
_DNA_CACHE: Dict[str, Any] | None = None


def _load_component_library() -> Dict[str, Any]:
    """Lazy-load component library JSON."""
    global _COMPONENT_CACHE
    if _COMPONENT_CACHE is not None:
        return _COMPONENT_CACHE
    if COMPONENT_LIB_PATH.exists():
        try:
            _COMPONENT_CACHE = json.loads(COMPONENT_LIB_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load component library: {e}")
            _COMPONENT_CACHE = {"_meta": {"version": "error", "error": str(e)}}
    else:
        logger.warning(f"Component library not found: {COMPONENT_LIB_PATH}")
        _COMPONENT_CACHE = {}
    return _COMPONENT_CACHE


def _load_product_dna() -> Dict[str, Any]:
    """Lazy-load per-product DNA."""
    global _DNA_CACHE
    if _DNA_CACHE is not None:
        return _DNA_CACHE
    if DNA_PATH.exists():
        try:
            _DNA_CACHE = json.loads(DNA_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load product DNA: {e}")
            _DNA_CACHE = {}
    else:
        logger.warning(f"Product DNA not found: {DNA_PATH}")
        _DNA_CACHE = {}
    return _DNA_CACHE


# ---------------------------------------------------------------------------
# Component mapping: product DNA component names → library categories
# ---------------------------------------------------------------------------

COMPONENT_MAP: Dict[str, str] = {
    # Table components
    "tabletop": "tops",
    "top": "tops",
    "base_support_or_legs": "bases_pedestals",
    "legs_or_frame": "legs",
    "legs_or_plinth": "legs",
    # Sofa/seating components
    "seat_base": "seats",
    "seat_cushions": "seats",
    "seat": "seats",
    "cushion": "seats",
    "cushions": "seats",
    "backrest": "backrests",
    "armrests": "arms",
    "arm": "arms",
    "padded_arm": "arms",
    # Open/fallback when component name matches a category key
    "main_body": "seats",
    "surface": "tops",
    "support": "bases_pedestals",
    "base": "bases_pedestals",
    "fabric_shell": "seats",
    "filling": "seats",
    "canopy_or_mount": "bases_pedestals",
    "body": "bases_pedestals",
    "diffuser_or_shade": "tops",
    "light_source": "tops",
    "support_rods_or_blades": "legs",
    "panel_body": "tops",
    "decorative_face": "tops",
    "door_or_drawer": "tops",
    "door_or_drawer_2": "tops",
    "base_or_plinth": "bases_pedestals",
    "headboard": "backrests",
    "mattress_or_bed": "seats",
}

# Position mapping: determines relative Y offset of each category
CATEGORY_Y_ORDER: List[Tuple[str, float]] = [
    ("backrests", 0.0),       # Top → backrest
    ("arms", 0.1),            # Arms
    ("tops", 0.2),            # Tabletop / surface
    ("seats", 0.35),          # Seat cushion
    ("bases_pedestals", 0.5), # Base/pedestal
    ("legs", 0.55),           # Legs
]


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def _select_component(
    comp_name: str,
    family: str,
    dna_entry: Dict[str, Any],
    lib: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Select the best component from the library for a given component name.

    Uses the product family and DNA fields to choose the right variant.
    """
    comp_lower = comp_name.lower().strip()

    # Determine which library category to use
    category_key = COMPONENT_MAP.get(comp_lower)

    # If not in map, try to match directly against library keys
    if not category_key:
        for cat_name in ["tops", "seats", "backrests", "arms", "legs", "bases_pedestals"]:
            if cat_name in lib:
                for sub_key, sub_val in lib[cat_name].items():
                    if comp_lower in sub_key or sub_key in comp_lower:
                        result = dict(sub_val)
                        result["_selected_key"] = sub_key
                        result["_category"] = cat_name
                        result["_component_name"] = comp_name
                        return result

    if not category_key or category_key not in lib:
        logger.debug(f"No library match for component '{comp_name}' → category '{category_key}'")
        return None

    category = lib[category_key]

    # Score each component in the category to find the best match
    family_lower = family.lower()
    best_score = 0.0
    best_key = None

    for key in category:
        score = 0.0
        key_lower = key.lower()

        # Direct name match
        if comp_lower in key_lower or key_lower in comp_lower:
            score += 0.8

        # Family-based heuristics
        if category_key == "tops":
            if any(s in family_lower for s in ["round", "pedestal", "circular"]):
                if "round" in key_lower:
                    score += 0.3
            elif any(s in family_lower for s in ["oval", "elliptical"]):
                if "oval" in key_lower:
                    score += 0.3
            elif any(s in family_lower for s in ["rect", "square", "console"]):
                if "rect" in key_lower:
                    score += 0.3
            elif any(s in family_lower for s in ["organic", "freeform"]):
                if "organic" in key_lower:
                    score += 0.3
        elif category_key == "legs":
            if any(s in family_lower for s in ["metal", "chrome"]):
                if "metal" in key_lower:
                    score += 0.3
            elif any(s in family_lower for s in ["wood", "tapered"]):
                if "wood" in key_lower:
                    score += 0.3
            elif any(s in family_lower for s in ["sled"]):
                if "sled" in key_lower:
                    score += 0.3
        elif category_key == "backrests":
            if any(s in family_lower for s in ["upholster", "padded", "plush"]):
                if "upholster" in key_lower:
                    score += 0.3
            elif any(s in family_lower for s in ["slatted", "slat"]):
                if "slatted" in key_lower:
                    score += 0.3
            elif any(s in family_lower for s in ["curved", "ergonomic"]):
                if "curved" in key_lower:
                    score += 0.3

        if score > best_score:
            best_score = score
            best_key = key

    # Default: pick first option if no good match
    if best_key is None:
        best_key = list(category.keys())[0] if category else None

    if best_key is None:
        return None

    result = dict(category[best_key])
    result["_selected_key"] = best_key
    result["_category"] = category_key
    result["_component_name"] = comp_name
    return result


def _position_components(
    assembled: List[Dict[str, Any]],
    bounding_ratio: str,
) -> List[Dict[str, Any]]:
    """Add position (x, y) and viewport info to each component.

    Components are stacked vertically by category (backrest top, legs bottom).
    """
    if not assembled:
        return assembled

    # Parse bounding ratio for layout proportions
    try:
        parts = bounding_ratio.split(":")
        w_ratio, d_ratio, h_ratio = float(parts[0]), float(parts[1]), float(parts[2])
    except (ValueError, IndexError):
        w_ratio, d_ratio, h_ratio = 1.65, 1.0, 0.42

    # Group components by category
    cat_groups: Dict[str, List[Dict]] = {}
    for comp in assembled:
        cat = comp.get("_category", "seats")
        if cat not in cat_groups:
            cat_groups[cat] = []
        cat_groups[cat].append(comp)

    # Position each category vertically
    total_height = 400  # SVG viewport height
    top_margin = 50
    bottom_margin = 50
    available = total_height - top_margin - bottom_margin

    # Distribute categories
    active_categories = [c for c, _ in CATEGORY_Y_ORDER if c in cat_groups]
    if not active_categories:
        return assembled

    slot_height = available / max(len(active_categories), 1)

    for idx, cat in enumerate(active_categories):
        y_start = top_margin + idx * slot_height
        for comp in cat_groups[cat]:
            comp["position"] = {
                "x": 50,
                "y": y_start,
                "width": 700,
                "height": slot_height * 0.8,
            }

    return assembled


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assemble_from_dna(
    handle_or_family: str,
    dimensions: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Assemble a product from its DNA — LEGO-like component assembly.

    Args:
        handle_or_family: Product handle (e.g. "melina-coffee-table") or
                          template family name (e.g. "oval_pedestal_coffee_table")
        dimensions: Optional real-world dimensions

    Returns:
        dict with keys:
          - product: base product info
          - components: list of assembled components with SVG + position
          - svg: combined SVG string
          - count: number of components
    """
    dimensions = dimensions or {}
    dna = _load_product_dna()
    lib = _load_component_library()

    # Find the product DNA entry
    dna_entry = dna.get(handle_or_family, {})

    # If not found by handle, search by family name
    if not dna_entry:
        for handle, entry in dna.items():
            if entry.get("template_family", "") == handle_or_family:
                dna_entry = entry
                break

    if not dna_entry:
        logger.warning(f"No DNA found for '{handle_or_family}'")
        return {
            "product": {"handle": handle_or_family, "title": handle_or_family},
            "components": [],
            "svg": "",
            "count": 0,
            "error": f"No DNA found for '{handle_or_family}'",
        }

    handle = dna_entry.get("handle", handle_or_family)
    title = dna_entry.get("title", handle_or_family)
    family = dna_entry.get("template_family", "")
    bounding_ratio = dna_entry.get("bounding_ratio", "1.65:1:0.42")
    component_names = dna_entry.get("component_list", [])

    # Assemble each component
    assembled: List[Dict[str, Any]] = []
    for comp_name in component_names:
        comp = _select_component(comp_name, family, dna_entry, lib)
        if comp:
            assembled.append(comp)
            logger.debug(f"  Assembled: {comp_name} → {comp.get('_selected_key', '?')}")

    if not assembled:
        # Fallback: try to build from family archetype
        logger.info(f"No components assembled from list, using archetype for '{family}'")

        # Determine archetype
        fl = family.lower()
        if any(k in fl for k in ["sofa", "bench"]):
            archetype_components = ["seat_base", "backrest", "armrests", "legs_or_plinth"]
        elif any(k in fl for k in ["table", "desk"]):
            archetype_components = ["tabletop", "base_support_or_legs"]
        elif any(k in fl for k in ["chair", "stool"]):
            archetype_components = ["seat", "backrest", "legs"]
        elif any(k in fl for k in ["cabinet", "wardrobe", "sideboard"]):
            archetype_components = ["main_body", "base_or_plinth"]
        elif any(k in fl for k in ["pendant", "light"]):
            archetype_components = ["canopy_or_mount", "support_rods_or_blades", "body", "diffuser_or_shade"]
        else:
            archetype_components = ["main_body"]

        for comp_name in archetype_components:
            comp = _select_component(comp_name, family, dna_entry, lib)
            if comp:
                assembled.append(comp)

    # Position components
    assembled = _position_components(assembled, bounding_ratio)

    # Build combined SVG
    svg_parts: List[str] = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" '
        f'width="100%" height="100%" style="background:#fff;border:1px solid #eee;">'
    )

    for comp in assembled:
        pos = comp.get("position", {})
        svg_template = comp.get("svg_front", "")
        if svg_template and pos:
            # Wrap SVG in a group with translation
            svg_parts.append(
                f'<g transform="translate({pos.get("x", 0)}, {pos.get("y", 0)}) '
                f'scale({pos.get("width", 300) / 400})">'
            )
            svg_parts.append(svg_template)

            # Add label
            label = comp.get("_component_name", comp.get("_selected_key", "")).replace("_", " ").title()
            svg_parts.append(
                f'<text x="200" y="-5" text-anchor="middle" font-family="sans-serif" '
                f'font-size="11" fill="#666">{label}</text>'
            )
            svg_parts.append("</g>")

    svg_parts.append(
        f'<text x="790" y="490" text-anchor="end" font-family="sans-serif" '
        f'font-size="9" fill="#999">'
        f'Assembled from components | {family} | {len(assembled)} parts</text>'
    )
    svg_parts.append("</svg>")

    return {
        "product": {
            "handle": handle,
            "title": title,
            "template_family": family,
            "bounding_ratio": bounding_ratio,
        },
        "components": assembled,
        "svg": "\n".join(svg_parts),
        "count": len(assembled),
    }


def assemble_from_handle(
    handle: str,
    dimensions: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Convenience: assemble from product handle only.

    Equivalent to assemble_from_dna(handle, dimensions).
    """
    return assemble_from_dna(handle, dimensions)


# ---------------------------------------------------------------------------
# Main / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore

    logging.basicConfig(level=logging.INFO)
    print("=== Component Assembler Demo ===")

    test_handles = [
        "melina-coffee-table",
        "aalto-modern-sofa",
        "42-wood-ceiling-fan",
        "augustin-armchair",
    ]

    for handle in test_handles:
        print(f"\n--- {handle} ---")
        result = assemble_from_dna(handle)
        print(f"  Components: {result['count']}")
        for comp in result.get("components", []):
            name = comp.get("_component_name", comp.get("_selected_key", "?"))
            cat = comp.get("_category", "?")
            print(f"    [{cat}] {name} → {comp.get('_selected_key', '?')}")
        print(f"  SVG: {len(result.get('svg', ''))} bytes")
