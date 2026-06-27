"""
Reference Geometry Matcher
============================
Matches detected geometry from user uploads against reference
geometry profiles from the library. Used to:
  - Identify which parts of a reference CAD match the user's sketch
  - Suggest template parameters based on matched reference sections
  - Fill in undetected geometry from reference matches
"""

import math
import logging
from typing import Any, Optional

logger = logging.getLogger("reference_geometry_matcher")


def match_detected_to_reference(
    detected_primitives: list[dict[str, Any]],
    reference_geometry: dict[str, Any],
) -> dict[str, Any]:
    """Match detected primitives against a reference geometry profile.
    
    Args:
        detected_primitives: List of primitives from user upload
        reference_geometry: Parsed reference DXF geometry (from parse_dxf)
    
    Returns:
        Dict with match scores, matched sections, and confidence
    """
    ref_entities = reference_geometry.get("entities", [])
    ref_counts = reference_geometry.get("counts", {})

    if not ref_entities or not detected_primitives:
        return {"match_score": 0.0, "matched_sections": [], "confidence": 0.0}

    # Compare entity type distributions
    detected_types: dict[str, int] = {}
    for p in detected_primitives:
        t = p.get("type", "unknown")
        detected_types[t] = detected_types.get(t, 0) + 1

    ref_types: dict[str, int] = {}
    for e in ref_entities:
        t = e.get("type", "unknown")
        ref_types[t] = ref_types.get(t, 0) + 1

    # Compute type distribution similarity
    all_types = set(list(detected_types.keys()) + list(ref_types.keys()))
    type_scores = []
    for t in all_types:
        d_count = detected_types.get(t, 0)
        r_count = ref_types.get(t, 0)
        if d_count > 0 or r_count > 0:
            type_scores.append(
                1.0 - abs(d_count - r_count) / max(d_count, r_count, 1)
            )

    type_similarity = sum(type_scores) / len(type_scores) if type_scores else 0.0

    # Compute bounding box aspect ratio similarity
    detected_bbox = _compute_bbox(detected_primitives)
    ref_bbox = reference_geometry.get("bbox") or {}

    aspect_similarity = 0.0
    if detected_bbox and ref_bbox:
        d_aspect = detected_bbox.get("width", 1) / max(detected_bbox.get("height", 1), 1)
        r_aspect = ref_bbox.get("width", 1) / max(ref_bbox.get("height", 1), 1)
        aspect_similarity = 1.0 - min(abs(d_aspect - r_aspect) / max(d_aspect, r_aspect, 1), 1.0)

    # Overall match score
    match_score = type_similarity * 0.6 + aspect_similarity * 0.4

    # Identify matched sections (entity type overlap)
    matched_sections = []
    for t in detected_types:
        if t in ref_types and ref_types[t] > 0:
            matched_sections.append({
                "type": t,
                "detected_count": detected_types[t],
                "reference_count": ref_types[t],
                "coverage": min(detected_types[t] / ref_types[t], 1.0),
            })

    return {
        "match_score": round(match_score, 3),
        "matched_sections": matched_sections,
        "confidence": round(match_score, 3),
        "type_similarity": round(type_similarity, 3),
        "aspect_similarity": round(aspect_similarity, 3),
    }


def _compute_bbox(primitives: list[dict[str, Any]]) -> Optional[dict[str, float]]:
    """Compute bounding box from a list of primitives."""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for p in primitives:
        pts = p.get("points") or []
        if isinstance(pts, list):
            for pt in pts:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    x, y = float(pt[0]), float(pt[1])
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

        if "start" in p:
            x, y = p["start"][0], p["start"][1]
            min_x = min(min_x, x)
            min_y = min(min_y, y)
        if "end" in p:
            x, y = p["end"][0], p["end"][1]
            max_x = max(max_x, x)
            max_y = max(max_y, y)
        if "center" in p:
            r = p.get("radius", 0)
            cx, cy = p["center"][0], p["center"][1]
            min_x = min(min_x, cx - r)
            min_y = min(min_y, cy - r)
            max_x = max(max_x, cx + r)
            max_y = max(max_y, cy + r)

    if min_x == float("inf"):
        return None

    return {
        "minX": min_x,
        "minY": min_y,
        "width": max_x - min_x,
        "height": max_y - min_y,
    }


def find_reference_template(
    furniture_type: str,
    dimensions: dict[str, float],
    references: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Find the best reference template for generating a DXF.
    
    Selects the reference whose dimensions are closest to the detected ones.
    Returns template parameters that can be used by the DXF exporter.
    """
    if not references:
        return None

    best_match = None
    best_score = float("inf")

    for ref in references:
        ref_geo = ref.get("geometryProfile") or {}
        ref_bbox = ref_geo.get("bbox") or {}

        score = 0.0
        n = 0

        for key, val in dimensions.items():
            if "width" in key or "diameter" in key:
                rw = ref_bbox.get("width", 0)
                if rw:
                    score += abs(val - rw) / rw
                    n += 1
            elif "height" in key:
                rh = ref_bbox.get("height", 0)
                if rh:
                    score += abs(val - rh) / rh
                    n += 1

        if n > 0:
            avg_score = score / n
            if avg_score < best_score:
                best_score = avg_score
                best_match = {
                    "reference": ref,
                    "score": round(avg_score, 3),
                    "template_name": f"{ref.get('manufacturer', '')} - {ref.get('productName', '')}",
                }

    return best_match
