"""
Reference Ratio Solver
========================
Uses reference geometry profiles to estimate missing dimensions
when processing user-uploaded drawings. When OCR can't detect all
dimensions, reference products of the same type provide reliable
proportion ratios.

For example, if a round pedestal table has a detected top diameter
of 80cm but the base diameter is missing, the ratio solver finds
similar references where base_diameter/top_diameter ≈ 0.55 and
estimates the missing base diameter as 80 × 0.55 = 44cm.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("reference_ratio_solver")

# Default ratio fallbacks per furniture type (from accumulated reference data)
DEFAULT_RATIOS: dict[str, dict[str, float]] = {
    "round_pedestal_table": {
        "base_dia_to_top": 0.55,
        "neck_dia_to_top": 0.28,
        "collar_dia_to_top": 0.625,
        "height_to_top": 0.875,
    },
    "rectangular_table": {
        "depth_to_width": 0.67,
        "height_to_width": 0.58,
        "leg_thickness_to_width": 0.05,
    },
    "sofa": {
        "depth_to_width": 0.40,
        "height_to_width": 0.42,
        "seat_height_to_height": 0.45,
        "armrest_height_to_height": 0.35,
    },
    "cabinet": {
        "depth_to_width": 0.50,
        "height_to_width": 1.80,
        "door_thickness": 1.8,
    },
    "dining_chair": {
        "seat_height_to_height": 0.55,
        "backrest_height_to_height": 0.50,
        "width_to_height": 0.50,
    },
    "coffee_table": {
        "depth_to_width": 0.60,
        "height_to_width": 0.45,
        "top_thickness_to_height": 0.10,
    },
    "wardrobe": {
        "depth_to_width": 0.50,
        "height_to_width": 1.67,
    },
    "bed_headboard": {
        "height_to_width": 0.38,
        "post_width_to_width": 0.05,
    },
    "reception_counter": {
        "depth_to_width": 0.25,
        "height_to_width": 0.61,
    },
}


def solve_missing_dimensions(
    furniture_type: str,
    detected_dims: dict[str, float],
    references: Optional[list[dict[str, Any]]] = None,
) -> dict[str, float]:
    """Estimate missing dimensions using reference ratios.
    
    Args:
        furniture_type: Normalized furniture type string
        detected_dims: Dict of detected dimension key → value in cm
        references: Optional list of reference product profiles
    
    Returns:
        Dict of estimated dimension key → value in cm (includes detected ones too)
    """
    result = dict(detected_dims)
    ratios = dict(DEFAULT_RATIOS.get(furniture_type, {}))

    # Try to compute better ratios from references
    if references:
        ref_ratios = _extract_ratios_from_references(furniture_type, references)
        ratios.update(ref_ratios)

    if furniture_type == "round_pedestal_table":
        top = detected_dims.get("top_diameter_cm") or detected_dims.get("width_cm")
        if top:
            if "base_diameter_cm" not in result:
                result["base_diameter_cm"] = round(top * ratios.get("base_dia_to_top", 0.55), 1)
            if "neck_diameter_cm" not in result:
                result["neck_diameter_cm"] = round(top * ratios.get("neck_dia_to_top", 0.28), 1)
            if "collar_diameter_cm" not in result:
                result["collar_diameter_cm"] = round(top * ratios.get("collar_dia_to_top", 0.625), 1)
            if "overall_height_cm" not in result:
                result["overall_height_cm"] = round(top * ratios.get("height_to_top", 0.875), 1)

    elif furniture_type == "rectangular_table":
        w = detected_dims.get("width_cm")
        if w:
            if "depth_cm" not in result:
                result["depth_cm"] = round(w * ratios.get("depth_to_width", 0.67), 1)
            if "overall_height_cm" not in result:
                result["overall_height_cm"] = round(w * ratios.get("height_to_width", 0.58), 1)
            if "leg_thickness_cm" not in result:
                result["leg_thickness_cm"] = round(max(w * ratios.get("leg_thickness_to_width", 0.05), 4.0), 1)

    elif furniture_type in ("cabinet", "wardrobe"):
        w = detected_dims.get("width_cm")
        if w:
            if "depth_cm" not in result:
                result["depth_cm"] = round(w * ratios.get("depth_to_width", 0.50), 1)
            if "overall_height_cm" not in result:
                h_ratio = ratios.get("height_to_width", 1.80)
                result["overall_height_cm"] = round(w * h_ratio, 1)

    elif furniture_type in ("dining_chair", "chair"):
        h = detected_dims.get("overall_height_cm")
        if h:
            if "seat_height_cm" not in result:
                result["seat_height_cm"] = round(h * ratios.get("seat_height_to_height", 0.55), 1)
            if "width_cm" not in result:
                result["width_cm"] = round(h * ratios.get("width_to_height", 0.50), 1)
        else:
            w = detected_dims.get("width_cm")
            if w and "overall_height_cm" not in result:
                result["overall_height_cm"] = round(w / ratios.get("width_to_height", 0.50), 1)

    elif furniture_type == "sofa":
        w = detected_dims.get("width_cm")
        if w:
            if "depth_cm" not in result:
                result["depth_cm"] = round(w * ratios.get("depth_to_width", 0.40), 1)
            if "overall_height_cm" not in result:
                result["overall_height_cm"] = round(w * ratios.get("height_to_width", 0.42), 1)

    elif furniture_type == "coffee_table":
        w = detected_dims.get("width_cm")
        if w:
            if "depth_cm" not in result:
                result["depth_cm"] = round(w * ratios.get("depth_to_width", 0.60), 1)
            if "overall_height_cm" not in result:
                result["overall_height_cm"] = round(w * ratios.get("height_to_width", 0.45), 1)

    elif furniture_type == "bed_headboard":
        w = detected_dims.get("width_cm")
        if w:
            if "overall_height_cm" not in result:
                result["overall_height_cm"] = round(w * ratios.get("height_to_width", 0.38), 1)

    elif furniture_type == "reception_counter":
        w = detected_dims.get("width_cm")
        if w:
            if "depth_cm" not in result:
                result["depth_cm"] = round(w * ratios.get("depth_to_width", 0.25), 1)
            if "overall_height_cm" not in result:
                result["overall_height_cm"] = round(w * ratios.get("height_to_width", 0.61), 1)

    return result


def _extract_ratios_from_references(
    furniture_type: str,
    references: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute average ratios from a set of reference geometry profiles."""
    ratios: dict[str, list[float]] = {}

    for ref in references:
        geo = ref.get("geometryProfile") or {}
        bbox = geo.get("bbox") or {}
        w = bbox.get("width")
        h = bbox.get("height")

        if not w or not h:
            continue

        # Store dimension ratios per furniture type using keys
        # that the solve_missing_dimensions function actually reads.
        if furniture_type == "round_pedestal_table":
            # height_to_top = overall_height / top_diameter
            key = "height_to_top"
            if key not in ratios:
                ratios[key] = []
            ratios[key].append(h / w)

        # Collect any other known ratios from the geometry profile
        counts = geo.get("counts") or {}
        if counts.get("entityCount", 0) > 0:
            # Store entity count as ratio of lines to total
            line_ratio = counts.get("lineCount", 0) / max(counts.get("entityCount", 1), 1)
            if "line_ratio" not in ratios:
                ratios["line_ratio"] = []
            ratios["line_ratio"].append(line_ratio)

    result = {}
    for key, values in ratios.items():
        if values:
            result[key] = round(sum(values) / len(values), 3)

    return result


def get_reference_ratios(furniture_type: str) -> dict[str, float]:
    """Get the best available dimension ratios for a furniture type.
    
    Returns a dict of ratio_name → float value used by the digitizer.
    """
    return dict(DEFAULT_RATIOS.get(furniture_type, {}))
