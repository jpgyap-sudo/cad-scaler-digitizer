"""
Reference Confidence Scorer
=============================
Scores the confidence of detected dimensions against reference
library data. Higher confidence means the detected dimensions
are consistent with known reference products of the same type.

Used to:
  - Flag outlier dimension values for user review
  - Weight the reliability of OCR-detected values
  - Provide explainable confidence scores in the UI
"""

import math
import logging
from typing import Any, Optional

logger = logging.getLogger("reference_confidence_scorer")


def score_dimension_confidence(
    furniture_type: str,
    detected_dims: dict[str, float],
    references: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Score each detected dimension against reference data.
    
    Args:
        furniture_type: Normalized furniture type
        detected_dims: Detected dimension key → value in cm
        references: Reference products from the library
    
    Returns:
        List of dicts with key, value, confidence, reason for each dimension
    """
    results: list[dict[str, Any]] = []

    # Build reference statistics
    ref_stats = _compute_reference_stats(furniture_type, references or [])

    for key, value in detected_dims.items():
        stat = ref_stats.get(key)
        if not stat or stat["count"] < 2:
            # Not enough reference data → moderate confidence
            results.append({
                "key": key,
                "value_cm": value,
                "confidence": 0.6,
                "reason": "insufficient_reference_data",
                "recommended_range": None,
            })
            continue

        mean = stat["mean"]
        std = stat["std"]
        min_val = stat["min"]
        max_val = stat["max"]

        # Z-score: how many standard deviations from the mean
        z = abs(value - mean) / max(std, 0.001)

        # Confidence based on z-score
        if z <= 1.0:
            confidence = 0.9  # Within 1 std dev — very typical
        elif z <= 2.0:
            confidence = 0.7  # Within 2 std dev — somewhat typical
        elif z <= 3.0:
            confidence = 0.4  # Within 3 std dev — unusual but possible
        else:
            confidence = 0.2  # Beyond 3 std dev — very unusual

        # Check if value is within observed range
        if value < min_val or value > max_val:
            confidence *= 0.5  # Outside observed range — halve confidence
            reason = "outside_reference_range"
        else:
            reason = "within_reference_range"

        results.append({
            "key": key,
            "value_cm": value,
            "confidence": round(confidence, 2),
            "reason": reason,
            "z_score": round(z, 2),
            "recommended_range": {
                "min": round(min_val, 1),
                "max": round(max_val, 1),
                "mean": round(mean, 1),
                "std": round(std, 2),
                "sample_count": stat["count"],
            },
        })

    return results


def _compute_reference_stats(
    furniture_type: str,
    references: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Compute mean/std/min/max for each dimension key from references."""
    from collections import defaultdict

    dim_values: dict[str, list[float]] = defaultdict(list)

    for ref in references:
        geo = ref.get("geometryProfile") or {}
        bbox = geo.get("bbox") or {}

        w = bbox.get("width")
        h = bbox.get("height")

        if w:
            if furniture_type in ("round_pedestal_table",):
                dim_values["top_diameter_cm"].append(float(w))
                dim_values["width_cm"].append(float(w))
            else:
                dim_values["width_cm"].append(float(w))

        if h:
            dim_values["overall_height_cm"].append(float(h))
            dim_values["height_cm"].append(float(h))

        # Extract dimension metadata from the product
        metadata = ref.get("metadata") or {}
        if isinstance(metadata, dict):
            for key, val in metadata.items():
                if isinstance(val, (int, float)) and val > 0:
                    dim_values[key].append(float(val))

        # Also check for stored dimensions in the product data
        for dim_key in ["widthMm", "depthMm", "heightMm"]:
            val = ref.get(dim_key.lower()) or ref.get(dim_key)
            if val:
                dim_key_cm = dim_key.replace("Mm", "_cm").lower()
                dim_values[dim_key_cm].append(float(val) / 10.0)

    stats = {}
    for key, values in dim_values.items():
        if len(values) >= 2:
            n = len(values)
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n
            std = math.sqrt(variance)
            stats[key] = {
                "mean": mean,
                "std": std,
                "min": min(values),
                "max": max(values),
                "count": n,
            }
        elif len(values) == 1:
            v = values[0]
            stats[key] = {
                "mean": v,
                "std": v * 0.1,  # Assume 10% variance for single sample
                "min": v * 0.8,
                "max": v * 1.2,
                "count": 1,
            }

    return stats


def get_dimension_outliers(
    detected_dims: dict[str, float],
    confidence_scores: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify dimensions that are outliers compared to reference data.
    
    Returns dimensions with low confidence scores for user review.
    """
    outliers = []
    for score in confidence_scores:
        if score.get("confidence", 1.0) < 0.5:
            outliers.append({
                "key": score["key"],
                "value_cm": score["value_cm"],
                "confidence": score["confidence"],
                "reason": score.get("reason", "low_confidence"),
                "recommended_range": score.get("recommended_range"),
            })
    return outliers


def get_overall_confidence(
    confidence_scores: list[dict[str, Any]],
) -> float:
    """Compute an overall confidence score for the entire detection."""
    if not confidence_scores:
        return 0.0

    # Weighted average: dimensions with wider ranges get lower weight
    total_weight = 0.0
    weighted_sum = 0.0

    for cs in confidence_scores:
        weight = 1.0
        rng = cs.get("recommended_range")
        if rng and rng.get("std", 0) > 0:
            # Lower weight for dimensions with high variance in reference data
            mean = rng.get("mean", 1)
            cv = rng["std"] / max(mean, 0.001)  # Coefficient of variation
            weight = max(0.3, 1.0 - cv)

        weighted_sum += cs["confidence"] * weight
        total_weight += weight

    return round(weighted_sum / max(total_weight, 0.001), 2)
