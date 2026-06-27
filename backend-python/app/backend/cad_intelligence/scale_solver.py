from __future__ import annotations
import statistics
from .models import DimensionAssociation, ScaleSolution

def solve_scale(associations: list[DimensionAssociation], min_confidence: float = 0.45) -> ScaleSolution:
    samples = []
    rejected = []

    for assoc in associations:
        if not assoc.measured_px or assoc.measured_px <= 0:
            rejected.append({"text": assoc.dimension.raw_text, "reason": "missing measured pixel length"})
            continue
        if assoc.confidence < min_confidence:
            rejected.append({"text": assoc.dimension.raw_text, "reason": f"low confidence {assoc.confidence:.2f}"})
            continue
        mm_per_px = assoc.dimension.value_mm / assoc.measured_px
        if mm_per_px <= 0 or mm_per_px > 100:
            rejected.append({"text": assoc.dimension.raw_text, "reason": f"implausible scale {mm_per_px:.4f}"})
            continue
        samples.append({
            "text": assoc.dimension.raw_text,
            "value_mm": assoc.dimension.value_mm,
            "measured_px": assoc.measured_px,
            "mm_per_px": mm_per_px,
            "confidence": assoc.confidence,
            "target_id": assoc.target_id,
            "target_type": assoc.target_type,
        })

    if not samples:
        return ScaleSolution(None, 0.0, [], rejected, "No valid scale samples")

    values = [s["mm_per_px"] for s in samples]
    median = statistics.median(values)
    kept = []
    outliers = []

    for s in samples:
        deviation = abs(s["mm_per_px"] - median) / median if median else 999
        if deviation <= 0.25:
            kept.append(s)
        else:
            outliers.append({**s, "reason": f"outlier deviation {deviation:.2%}"})

    if not kept:
        return ScaleSolution(median, 0.25, samples, rejected + outliers, "Only outlier-like samples available")

    weighted_sum = sum(s["mm_per_px"] * s["confidence"] for s in kept)
    weight = sum(s["confidence"] for s in kept)
    mm_per_px = weighted_sum / weight if weight else statistics.mean([s["mm_per_px"] for s in kept])
    confidence = min(0.95, 0.45 + 0.1 * len(kept) + statistics.mean([s["confidence"] for s in kept]) * 0.35)

    return ScaleSolution(mm_per_px, confidence, kept, rejected + outliers, f"Solved from {len(kept)} accepted sample(s)")
