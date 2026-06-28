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
    "oval_pedestal_table": {
        "depth_to_length": 0.56,
        "height_to_length": 0.42,
        "pedestal_dia_to_length": 0.22,
        "top_thickness_to_height": 0.04,
    },
    "console_table": {
        "depth_to_length": 0.33,
        "height_to_length": 0.62,
        "leg_thick_to_length": 0.033,
        "leg_inset_to_length": 0.017,
    },
    "office_desk": {
        "depth_to_length": 0.43,
        "height_to_length": 0.54,
        "leg_thick_to_length": 0.029,
        "modesty_panel_h_to_height": 0.20,
    },
    "asymmetric_pedestal_table": {
        "depth_to_length": 0.50,
        "height_to_length": 0.42,
        "large_ped_to_length": 0.22,
        "small_ped_to_length": 0.12,
        "large_ped_offset_to_length": 0.17,
        "small_ped_offset_to_length": 0.14,
        "top_thickness_to_height": 0.04,
        "overhang_to_length": 0.10,
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

    elif furniture_type == "oval_pedestal_table":
        l = detected_dims.get("length_cm")
        if l:
            if "depth_cm" not in result: result["depth_cm"] = round(l * ratios.get("depth_to_length", 0.56), 1)
            if "overall_height_cm" not in result: result["overall_height_cm"] = round(l * ratios.get("height_to_length", 0.42), 1)
            if "pedestal_dia_cm" not in result: result["pedestal_dia_cm"] = round(l * ratios.get("pedestal_dia_to_length", 0.22), 1)
        else:
            h = detected_dims.get("overall_height_cm")
            if h and "length_cm" not in result:
                result["length_cm"] = round(h / ratios.get("height_to_length", 0.42), 1)

    elif furniture_type == "console_table":
        l = detected_dims.get("length_cm")
        if l:
            if "depth_cm" not in result: result["depth_cm"] = round(l * ratios.get("depth_to_length", 0.33), 1)
            if "overall_height_cm" not in result: result["overall_height_cm"] = round(l * ratios.get("height_to_length", 0.62), 1)
            if "leg_thick_cm" not in result: result["leg_thick_cm"] = round(max(l * ratios.get("leg_thick_to_length", 0.033), 3.0), 1)

    elif furniture_type == "office_desk":
        l = detected_dims.get("length_cm")
        if l:
            if "depth_cm" not in result: result["depth_cm"] = round(l * ratios.get("depth_to_length", 0.43), 1)
            if "overall_height_cm" not in result: result["overall_height_cm"] = round(l * ratios.get("height_to_length", 0.54), 1)
            if "leg_thick_cm" not in result: result["leg_thick_cm"] = round(max(l * ratios.get("leg_thick_to_length", 0.029), 3.0), 1)
        else:
            h = detected_dims.get("overall_height_cm")
            if h and "length_cm" not in result:
                result["length_cm"] = round(h / ratios.get("height_to_length", 0.54), 1)
        if "modesty_panel_h_cm" not in result:
            h = result.get("overall_height_cm", detected_dims.get("overall_height_cm", 75))
            result["modesty_panel_h_cm"] = round(h * ratios.get("modesty_panel_h_to_height", 0.20), 1)

    elif furniture_type == "asymmetric_pedestal_table":
        l = detected_dims.get("length_cm")
        if l:
            if "depth_cm" not in result:
                result["depth_cm"] = round(l * ratios.get("depth_to_length", 0.50), 1)
            if "overall_height_cm" not in result:
                result["overall_height_cm"] = round(l * ratios.get("height_to_length", 0.42), 1)
            if "large_ped_dia_cm" not in result:
                result["large_ped_dia_cm"] = round(l * ratios.get("large_ped_to_length", 0.22), 1)
            if "small_ped_dia_cm" not in result:
                result["small_ped_dia_cm"] = round(l * ratios.get("small_ped_to_length", 0.12), 1)
            if "left_ped_x_cm" not in result:
                result["left_ped_x_cm"] = round(l * ratios.get("large_ped_offset_to_length", 0.17), 1)
            if "right_ped_x_cm" not in result:
                result["right_ped_x_cm"] = round(-l * ratios.get("small_ped_offset_to_length", 0.14), 1)
            if "top_thickness_cm" not in result:
                h = result.get("overall_height_cm", 75.0)
                result["top_thickness_cm"] = round(h * ratios.get("top_thickness_to_height", 0.04), 1)
        else:
            h = detected_dims.get("overall_height_cm")
            if h and "length_cm" not in result:
                result["length_cm"] = round(h / ratios.get("height_to_length", 0.42), 1)

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
    Merges DEFAULT_RATIOS with any auto-calibrated averages from
    the calibration ledger.
    """
    ratios = dict(DEFAULT_RATIOS.get(furniture_type, {}))

    # Merge in auto-calibrated averages from calibration_ledger if available
    try:
        import json, os
        from pathlib import Path
        ledger_path = Path(__file__).resolve().parents[3] / 'resources' / 'calibration_ledger.json'
        if ledger_path.exists():
            ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
            type_avgs = ledger.get('type_averages', {}).get(furniture_type, {})
            if type_avgs:
                # Map catalog dimension keys to ratio keys
                calib_map = {
                    'width_cm': 'width_from_catalog',
                    'depth_cm': 'depth_from_catalog',
                    'overall_height_cm': 'height_from_catalog',
                    'diameter_cm': 'diameter_from_catalog',
                    'seat_height_cm': 'seat_height_from_catalog',
                }
                for cat_key, avg_val in type_avgs.items():
                    mapped = calib_map.get(cat_key)
                    if mapped:
                        ratios[mapped] = float(avg_val)
    except Exception:
        pass  # Non-fatal: fall back to default ratios

    return ratios
