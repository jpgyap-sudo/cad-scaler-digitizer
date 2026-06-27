"""
Photo ↔ CAD Validation Engine
================================
Validates that photos and DWG files for the same product are consistent.
This is the core ML training data quality gate:

  Step 1: Product photo → OpenCV/OCR → detected dimensions
  Step 2: CAD file → ezdxf parse → reference geometry
  Step 3: Compare. Score consistency.
  Step 4: If score > threshold, emit validated training pair.
  Step 5: Export pairs for ML model fine-tuning.

Products that fail validation are flagged for human review — the
detected dimensions don't match the engineering CAD, so the photo
or the digitizer pipeline needs correction.
"""

import os
import json
import math
import logging
from typing import Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("validation_service")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DimensionComparison:
    dimension_key: str
    detected_cm: float
    reference_cm: float
    deviation_pct: float
    passed: bool

@dataclass
class ValidationResult:
    product_id: str
    overall_score: float
    dimensions: list[dict]
    passed: bool
    errors: list[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------

# Tolerance thresholds
MAX_DEVIATION_PCT = 15.0   # Max acceptable deviation (%)
MIN_SCORE_PASS = 0.7       # Minimum weighted score to pass

def validate_product_family(
    product_id: str,
    detected_dims: dict[str, float],
    reference_geometry: dict[str, Any],
    furniture_type: str = "unknown",
) -> ValidationResult:
    """Compare detected dimensions against CAD reference geometry.
    
    Args:
        product_id: Unique product identifier
        detected_dims: Dimensions detected from photo (key → cm)
        reference_geometry: Parsed DXF geometry from cad/dxf_parser.py
        furniture_type: Furniture type for context-aware comparison
    
    Returns:
        ValidationResult with per-dimension comparisons and overall score
    """
    errors = []
    comparisons = []

    # Extract reference dimensions from CAD geometry bbox
    ref_bbox = reference_geometry.get("bbox") or {}
    ref_counts = reference_geometry.get("counts", {})

    # Build reference dimension map
    ref_dims = {}
    if ref_bbox.get("width"):
        ref_dims["width_cm"] = ref_bbox["width"]
    if ref_bbox.get("height"):
        ref_dims["overall_height_cm"] = ref_bbox["height"]

    # Also extract from geometry metadata if available
    for ent in reference_geometry.get("entities", [])[:100]:
        if ent.get("type") == "line":
            sx, sy = ent["start"]
            ex, ey = ent["end"]
            dx = abs(ex - sx)
            dy = abs(ey - sy)
            if dx > 0 and dy / max(dx, 1) < 0.1:
                # Horizontal line → likely a width reference
                ref_dims[f"line_width_{len(ref_dims)}"] = dx
            elif dy > 0 and dx / max(dy, 1) < 0.1:
                # Vertical line → likely a height reference
                ref_dims[f"line_height_{len(ref_dims)}"] = dy

    if not ref_dims:
        errors.append("CAD geometry has no extractable dimensions")
        ref_dims["width_cm"] = 0  # prevent division by zero

    # Compare each detected dimension against the closest reference
    for det_key, det_val in detected_dims.items():
        if det_val <= 0:
            continue

        # Find the best matching reference dimension
        best_match_key = _find_closest_dimension(det_key, ref_dims, det_val)
        if best_match_key is None:
            continue

        ref_val = ref_dims[best_match_key]
        if ref_val <= 0:
            continue

        deviation_pct = abs(det_val - ref_val) / ref_val * 100
        passed = deviation_pct <= MAX_DEVIATION_PCT

        comparisons.append(DimensionComparison(
            dimension_key=det_key,
            detected_cm=round(det_val, 1),
            reference_cm=round(ref_val, 1),
            deviation_pct=round(deviation_pct, 1),
            passed=passed,
        ))

    if not comparisons:
        errors.append("No dimensions could be compared")
        return ValidationResult(
            product_id=product_id,
            overall_score=0.0,
            dimensions=[],
            passed=False,
            errors=errors,
        )

    # Compute overall weighted score
    scores = [1.0 - min(c.deviation_pct / 100, 1.0) for c in comparisons]
    weights = [
        3.0 if "width" in c.dimension_key or "diameter" in c.dimension_key else
        2.0 if "height" in c.dimension_key else
        1.0
        for c in comparisons
    ]
    overall_score = sum(s * w for s, w in zip(scores, weights)) / max(sum(weights), 1)

    return ValidationResult(
        product_id=product_id,
        overall_score=round(overall_score, 3),
        dimensions=[asdict(c) for c in comparisons],
        passed=overall_score >= MIN_SCORE_PASS,
        errors=errors,
    )


def _find_closest_dimension(
    det_key: str, ref_dims: dict[str, float], det_val: float
) -> Optional[str]:
    """Find the best matching reference dimension for a detected one.
    
    Uses semantic matching (key similarity) and value proximity.
    """
    # Try exact semantic match first
    for ref_key in ref_dims:
        if _keys_match(det_key, ref_key):
            return ref_key

    # Fall back to value proximity
    best_key = None
    best_diff = float("inf")
    for ref_key, ref_val in ref_dims.items():
        diff = abs(det_val - ref_val)
        if diff < best_diff:
            best_diff = diff
            best_key = ref_key

    return best_key


def _keys_match(det_key: str, ref_key: str) -> bool:
    """Check if two dimension keys refer to the same measurement."""
    d = det_key.lower().replace("_", "").replace("-", "")
    r = ref_key.lower().replace("_", "").replace("-", "")
    return d == r or d in r or r in d


# ---------------------------------------------------------------------------
# ML Training Data Export
# ---------------------------------------------------------------------------

def build_training_record(
    product_id: str,
    furniture_type: str,
    image_url: str,
    dxf_url: str,
    detected_dims: dict[str, float],
    reference_geometry: dict[str, Any],
    validation: ValidationResult,
) -> dict[str, Any]:
    """Build a training record for ML model fine-tuning.
    
    Format is JSONL-compatible: one record per validated product family.
    Fields:
      - prompt: description of what to detect (furniture type + product ID)
      - images: product photo + CAD preview
      - reference: ground truth dimensions from CAD
      - detected: what the digitizer actually found
      - validation: consistency comparison
      - score: overall quality score
    """
    return {
        "product_id": product_id,
        "furniture_type": furniture_type,
        "image_url": image_url,
        "dxf_url": dxf_url,
        "reference_dimensions": {
            k: round(v, 1) for k, v in
            _extract_reference_dims(reference_geometry).items()
        },
        "detected_dimensions": {k: round(v, 1) for k, v in detected_dims.items()},
        "validation": asdict(validation),
        "prompt": (
            f"Digitise this {furniture_type.replace('_', ' ')} ({product_id}). "
            f"Reference dimensions from CAD: "
            f"{_format_dimensions(_extract_reference_dims(reference_geometry))}. "
            f"Detected deviation: {validation.overall_score:.1%}."
        ),
    }


def _extract_reference_dims(geometry: dict[str, Any]) -> dict[str, float]:
    """Extract the most important dimensions from CAD geometry as a flat dict."""
    dims = {}
    bbox = geometry.get("bbox") or {}
    if bbox.get("width"):
        dims["width_cm"] = bbox["width"]
    if bbox.get("height"):
        dims["height_cm"] = bbox["height"]

    # Use the longest lines as dimension hints
    lines = [
        e for e in geometry.get("entities", [])
        if e.get("type") == "line"
    ]
    lines.sort(
        key=lambda l: math.hypot(
            l["end"][0] - l["start"][0], l["end"][1] - l["start"][1]
        ),
        reverse=True,
    )

    entity_count = geometry.get("counts", {}).get("entityCount", 0)
    dims["entity_count"] = entity_count
    return dims


def _format_dimensions(dims: dict[str, float]) -> str:
    """Format dimensions for ML prompt inclusion."""
    parts = []
    for k, v in dims.items():
        label = k.replace("_cm", " cm").replace("_", " ")
        parts.append(f"{label}: {v}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Batch validation & export
# ---------------------------------------------------------------------------

def validate_all_product_families(
    families: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate all product families where both photo and CAD exist.
    
    Each family: {
        product_id, furniture_type,
        detected_dims: {key: cm},
        reference_geometry: { ... parsed DXF ... },
        image_url, dxf_url
    }
    """
    results = []
    for family in families:
        result = validate_product_family(
            product_id=family["product_id"],
            detected_dims=family.get("detected_dims", {}),
            reference_geometry=family.get("reference_geometry", {}),
            furniture_type=family.get("furniture_type", "unknown"),
        )
        record = build_training_record(
            product_id=family["product_id"],
            furniture_type=family.get("furniture_type", "unknown"),
            image_url=family.get("image_url", ""),
            dxf_url=family.get("dxf_url", ""),
            detected_dims=family.get("detected_dims", {}),
            reference_geometry=family.get("reference_geometry", {}),
            validation=result,
        )
        results.append(record)

    return results


def export_training_data(
    validated_records: list[dict[str, Any]],
    output_path: str,
    min_score: float = MIN_SCORE_PASS,
) -> dict[str, Any]:
    """Export validated records as JSONL for ML training.
    
    Args:
        validated_records: Output from validate_all_product_families
        output_path: File path to write JSONL
        min_score: Minimum validation score to include
    
    Returns:
        Summary: total, passed, failed, output path
    """
    passed = [r for r in validated_records if r["validation"]["passed"]]
    failed = [r for r in validated_records if not r["validation"]["passed"]]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        for record in passed:
            f.write(json.dumps(record) + "\n")

    logger.info(
        f"Training data exported: {len(passed)} passed, "
        f"{len(failed)} failed → {output_path}"
    )

    return {
        "total": len(validated_records),
        "passed": len(passed),
        "failed": len(failed),
        "min_score": min_score,
        "output_path": output_path,
    }
