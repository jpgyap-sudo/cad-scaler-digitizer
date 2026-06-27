"""Reference Ratio Solver — fills missing dimensions from known furniture proportions.

Uses the template graph library to estimate unknown parameters from known ones.
E.g., given top_diameter_cm=100, estimate pedestal_diameter_cm via standard ratio.
"""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple


# Known proportion ratios per furniture type (anchored dimension -> target dimension -> ratio)
# These are derived from the template graph default values
KNOWN_RATIOS: Dict[str, Dict[str, Dict[str, float]]] = {
    "round_pedestal_table": {
        "top_diameter_cm": {
            "pedestal_diameter_cm": 0.333,  # 400mm / 1200mm
            "top_thickness_cm": 0.025,       # 30mm / 1200mm
            "overall_height_cm": 0.625,      # 750mm / 1200mm
        },
        "overall_height_cm": {
            "top_diameter_cm": 1.6,  # 1200mm / 750mm
        },
    },
    "rectangular_table": {
        "width_cm": {
            "depth_cm": 0.5,         # 900mm / 1800mm
            "top_thickness_cm": 0.0167, # 30mm / 1800mm
            "overall_height_cm": 0.417, # 750mm / 1800mm
        },
        "overall_height_cm": {
            "width_cm": 2.4,  # 1800mm / 750mm
        },
    },
    "sofa": {
        "width_cm": {
            "depth_cm": 0.432,       # 950mm / 2200mm
            "overall_height_cm": 0.355, # 780mm / 2200mm
            "seat_height_cm": 0.191,    # 420mm / 2200mm
        },
    },
    "cabinet": {
        "width_cm": {
            "depth_cm": 0.25,  # 450mm / 1800mm
            "overall_height_cm": 0.444, # 800mm / 1800mm
        },
        "overall_height_cm": {
            "width_cm": 2.25,  # 1800mm / 800mm
        },
    },
    "wardrobe": {
        "width_cm": {
            "depth_cm": 0.5,   # 600mm / 1200mm
            "overall_height_cm": 1.667, # 2000mm / 1200mm
        },
        "overall_height_cm": {
            "width_cm": 0.6,   # 1200mm / 2000mm
        },
    },
    "bed": {
        "width_cm": {
            "depth_cm": 1.11,  # 2030mm / 1830mm
            "platform_height_cm": 0.164, # 300mm / 1830mm
        },
    },
    "dining_chair": {
        "width_cm": {
            "depth_cm": 1.077,         # 560mm / 520mm
            "seat_height_cm": 0.865,   # 450mm / 520mm
            "overall_height_cm": 1.577, # 820mm / 520mm
        },
    },
    "asymmetric_pedestal_table": {
        "length_cm": {
            "depth_cm": 0.5,          # 900mm / 1800mm
            "large_pedestal_diameter_cm": 0.222, # 400mm / 1800mm
            "small_pedestal_diameter_cm": 0.122, # 220mm / 1800mm
        },
    },
    "coffee_table": {
        "width_cm": {
            "depth_cm": 0.5,          # 600mm / 1200mm
            "overall_height_cm": 0.317, # 380mm / 1200mm
        },
    },
}


def get_known_ratios(furniture_type: str) -> Dict[str, Dict[str, float]]:
    """Get all known ratios for a furniture type."""
    return KNOWN_RATIOS.get(furniture_type, {})


def solve_missing_dimensions(
    furniture_type: str,
    known_dims_cm: Dict[str, float],
) -> Dict[str, float]:
    """Fill in missing dimensions using known proportion ratios.

    Args:
        furniture_type: e.g. "round_pedestal_table"
        known_dims_cm: dict of known dimension name -> value in cm

    Returns:
        Dict of all dimensions (known + estimated) in cm
    """
    result = dict(known_dims_cm)
    ratios = get_known_ratios(furniture_type)

    if not ratios:
        return result

    # For each known dimension, try to derive missing ones
    for anchor_key, anchor_val in known_dims_cm.items():
        if anchor_val <= 0:
            continue
        derived = ratios.get(anchor_key, {})
        for target_key, ratio in derived.items():
            if target_key not in result and target_key not in known_dims_cm:
                result[target_key] = round(anchor_val * ratio, 1)

    # Second pass: try reverse direction (target -> anchor)
    for target_key in ratios:
        if target_key in result:
            continue  # Already have it
        # Try each anchor dimension to derive this target
        for anchor_key, anchor_val in known_dims_cm.items():
            if anchor_val <= 0:
                continue
            derived = ratios.get(target_key, {})
            if anchor_key in derived:
                ratio = derived[anchor_key]
                if ratio > 0:
                    result[target_key] = round(anchor_val / ratio, 1)
                    break

    return result


def estimate_from_entities(
    furniture_type: str,
    entities_bbox_mm: Dict[str, float],
) -> Dict[str, float]:
    """Estimate furniture dimensions from detected entity bounding boxes.

    Args:
        furniture_type: detected furniture type
        entities_bbox_mm: entity_name -> detected_mm_value

    Returns:
        Estimated full dimension set in cm
    """
    known = {}
    for key, val_mm in entities_bbox_mm.items():
        if val_mm > 0:
            known[key] = round(val_mm / 10.0, 1)  # mm -> cm
    return solve_missing_dimensions(furniture_type, known)
