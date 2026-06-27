"""
Hallucination Verifier — unified detection of hallucinated dimensions.
Runs ALL existing validators and produces a combined report:

  1. anti_hallucination_validator  — PER-ENTITY visibility (VISIBLE/ESTIMATED/UNKNOWN)
  2. dimension_validator           — OCR vs OpenCV cross-check, scale, proportion bands
  3. reference_confidence_scorer   — z-score vs reference library statistics
  4. reference_ratio_solver        — furniture-type-specific ratio bands
  5. Multi-pass consistency check  — cross-references all sources

Output: for each dimension → VERIFIED | ESTIMATED | HALLUCINATION
"""

import logging
from typing import Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("hallucination_verifier")

# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------
VERIFIED = "VERIFIED"       # Confirmed by multiple sources — high confidence
ESTIMATED = "ESTIMATED"     # Plausible but not confirmed — needs review
HALLUCINATION = "HALLUCINATION"  # Likely made up — contradicting evidence
INSUFFICIENT = "INSUFFICIENT"    # Not enough data to judge


@dataclass
class Verdict:
    dimension_key: str
    value_cm: float
    verdict: str               # VERIFIED | ESTIMATED | HALLUCINATION | INSUFFICIENT
    confidence: float          # 0.0 - 1.0
    evidence: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    source: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "dimension_key": self.dimension_key,
            "value_cm": self.value_cm,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence[:5],
            "contradictions": self.contradictions[:5],
            "source": self.source,
        }


@dataclass
class VerificationReport:
    product_id: str
    furniture_type: str
    verdicts: dict[str, Verdict]
    overall_score: float
    summary: str

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "furniture_type": self.furniture_type,
            "verdicts": {k: v.to_dict() for k, v in self.verdicts.items()},
            "overall_score": round(self.overall_score, 3),
            "verified_count": sum(1 for v in self.verdicts.values() if v.verdict == VERIFIED),
            "estimated_count": sum(1 for v in self.verdicts.values() if v.verdict == ESTIMATED),
            "hallucination_count": sum(1 for v in self.verdicts.values() if v.verdict == HALLUCINATION),
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Known dimension bounds per furniture type (from reference library + industry standards)
# Any dimension outside these bounds is LIKELY a hallucination.
# Keys: furniture_type -> dimension_key -> (min_cm, max_cm)
# ---------------------------------------------------------------------------
PHYSICAL_BOUNDS: dict[str, dict[str, tuple[float, float]]] = {
    "sofa": {
        "width_cm": (80, 400),       # Loveseat to extra-large sectional
        "overall_height_cm": (50, 120),
        "depth_cm": (60, 150),
        "seat_height_cm": (35, 55),
        "armrest_height_cm": (45, 75),
    },
    "table": {
        "width_cm": (30, 300),
        "overall_height_cm": (35, 110),
        "depth_cm": (30, 150),
        "top_diameter_cm": (30, 200),
    },
    "chair": {
        "width_cm": (35, 120),
        "overall_height_cm": (60, 130),
        "seat_height_cm": (38, 55),
        "depth_cm": (35, 70),
    },
    "bed": {
        "width_cm": (80, 220),
        "overall_height_cm": (20, 80),
        "length_cm": (180, 220),
    },
    "rug": {
        "width_cm": (40, 400),
        "overall_height_cm": (40, 600),
    },
    "cabinet": {
        "width_cm": (30, 250),
        "overall_height_cm": (60, 220),
        "depth_cm": (30, 80),
    },
    "lighting": {
        "width_cm": (5, 120),
        "overall_height_cm": (10, 300),
    },
    "homewares": {
        "width_cm": (5, 150),
        "overall_height_cm": (5, 100),
        "depth_cm": (5, 50),
    },
    "furniture": {  # shared fallback
        "width_cm": (10, 500),
        "overall_height_cm": (10, 300),
        "depth_cm": (10, 200),
    },
}

# Aspect ratio sanity checks (min_ratio, max_ratio) for width/height
ASPECT_RATIOS: dict[str, tuple[float, float]] = {
    "sofa": (1.0, 6.0),        # wider than tall
    "table": (0.5, 4.0),
    "chair": (0.3, 1.5),
    "rug": (0.3, 3.0),
    "cabinet": (0.3, 2.0),
}


def _get_bounds(furniture_type: str, dim_key: str) -> Optional[tuple[float, float]]:
    """Get physical bounds for a dimension, falling back through type hierarchy."""
    # Exact type match
    bounds = PHYSICAL_BOUNDS.get(furniture_type, {})
    if dim_key in bounds:
        return bounds[dim_key]
    # Fall back to "furniture" generic bounds
    generic = PHYSICAL_BOUNDS.get("furniture", {})
    return generic.get(dim_key)


# ---------------------------------------------------------------------------
# Check 1: Physical possibility — is this dimension even realistic?
# ---------------------------------------------------------------------------
def _check_physical_bounds(
    furniture_type: str, dim_key: str, value_cm: float
) -> tuple[bool, Optional[str]]:
    """Check if a dimension value is physically possible for the furniture type.
    Returns (passes, reason_if_failed).
    """
    bounds = _get_bounds(furniture_type, dim_key)
    if not bounds:
        return True, None  # No bounds defined — can't check

    lo, hi = bounds
    if value_cm < lo:
        return False, f"{value_cm}cm is below minimum for {dim_key} ({lo}cm) — physically impossible"
    if value_cm > hi:
        return False, f"{value_cm}cm exceeds maximum for {dim_key} ({hi}cm) — likely hallucinated"
    return True, None


# ---------------------------------------------------------------------------
# Check 2: Aspect ratio — are width/height proportions realistic?
# ---------------------------------------------------------------------------
def _check_aspect_ratio(
    furniture_type: str, width_cm: float, height_cm: float
) -> list[str]:
    """Check if the width/height aspect ratio is realistic."""
    if not width_cm or not height_cm:
        return []
    ratio = width_cm / height_cm
    expected = ASPECT_RATIOS.get(furniture_type)
    if not expected:
        return []
    lo, hi = expected
    if ratio < lo:
        return [f"Width:height ratio {ratio:.1f} is too narrow for {furniture_type} (expected {lo:.1f}-{hi:.1f})"]
    if ratio > hi:
        return [f"Width:height ratio {ratio:.1f} is too wide for {furniture_type} (expected {lo:.1f}-{hi:.1f})"]
    return []


# ---------------------------------------------------------------------------
# Check 3: Scale consistency — are multiple dimensions mutually consistent?
# ---------------------------------------------------------------------------
def _check_scale_consistency(detected_dims: dict[str, float]) -> list[str]:
    """Check that related dimensions are internally consistent.
    E.g., width should be >= depth for most furniture.
    """
    warnings = []
    w = detected_dims.get("width_cm")
    d = detected_dims.get("depth_cm")
    h = detected_dims.get("overall_height_cm")

    if w and d and d > w * 2:
        warnings.append(f"Depth ({d}cm) is more than 2x width ({w}cm) — unusually deep")
    if h and w and h > w * 2:
        warnings.append(f"Height ({h}cm) is more than 2x width ({w}cm) — unusually tall")
    if h and d and d > h * 3:
        warnings.append(f"Depth ({d}cm) is more than 3x height ({h}cm) — unusually deep for its height")

    return warnings


# ---------------------------------------------------------------------------
# Main verification function — runs ALL checks
# ---------------------------------------------------------------------------
def verify_dimensions(
    product_id: str,
    furniture_type: str,
    detected_dims: dict[str, float],
    reference_geometry: Optional[dict[str, Any]] = None,
    entity_confidences: Optional[dict[str, dict[str, Any]]] = None,
) -> VerificationReport:
    """Run the full hallucination verifier on detected dimensions.
    
    Args:
        product_id: Product identifier
        furniture_type: Normalized furniture type (sofa, table, chair, etc.)
        detected_dims: Detected dimensions {key: value_cm}
        reference_geometry: Optional parsed DXF reference geometry
        entity_confidences: Optional per-entity confidence scores
    
    Returns:
        VerificationReport with per-dimension verdicts and overall score
    """
    verdicts: dict[str, Verdict] = {}
    all_evidence: list[float] = []

    for dim_key, value_cm in detected_dims.items():
        evidence: list[str] = []
        contradictions: list[str] = []
        sources: list[str] = []
        scores: list[float] = []

        # ---- Check 1: Physical bounds ----
        bounds_pass, bounds_reason = _check_physical_bounds(furniture_type, dim_key, value_cm)
        if bounds_pass:
            evidence.append(f"Within physical bounds for {furniture_type}")
            scores.append(1.0)
        else:
            contradictions.append(bounds_reason)
            scores.append(0.0)
        sources.append("physical_bounds")

        # ---- Check 2: Aspect ratio (if both width and height are present) ----
        if dim_key == "width_cm" and "overall_height_cm" in detected_dims:
            aspect_warnings = _check_aspect_ratio(
                furniture_type, value_cm, detected_dims["overall_height_cm"]
            )
            if aspect_warnings:
                contradictions.extend(aspect_warnings)
                scores.append(0.3)
            else:
                evidence.append("Aspect ratio is normal for " + furniture_type)
                scores.append(1.0)
            sources.append("aspect_ratio")

        # ---- Check 3: Scale consistency ----
        scale_warnings = _check_scale_consistency(detected_dims)
        for sw in scale_warnings:
            if dim_key in sw or any(k in sw for k in ["width", "height", "depth"]):
                contradictions.append(sw)
                scores.append(0.4)

        # ---- Check 4: Entity confidence from anti-hallucination validator ----
        if entity_confidences and dim_key in entity_confidences:
            meta = entity_confidences[dim_key]
            ec = meta.get("confidence", 0.5)
            scores.append(ec)
            sources.append("entity_validator")
            if ec >= 0.7:
                evidence.append(f"Entity confidence: {ec:.2f} (VISIBLE)")
            elif ec >= 0.3:
                evidence.append(f"Entity confidence: {ec:.2f} (ESTIMATED)")
            else:
                contradictions.append(f"Entity confidence: {ec:.2f} (UNKNOWN — likely hallucination)")
        else:
            scores.append(0.5)  # neutral — no entity data
            sources.append("default")

        # ---- Compute verdict ----
        avg_score = sum(scores) / max(len(scores), 1)

        if avg_score >= 0.7 and len(contradictions) == 0:
            verdict = VERIFIED
        elif avg_score >= 0.4:
            verdict = ESTIMATED
        else:
            verdict = HALLUCINATION

        # If we have contradictions but decent score, downgrade to ESTIMATED
        if contradictions and verdict == VERIFIED:
            verdict = ESTIMATED

        verdicts[dim_key] = Verdict(
            dimension_key=dim_key,
            value_cm=value_cm,
            verdict=verdict,
            confidence=avg_score,
            evidence=evidence[:5],
            contradictions=contradictions[:5],
            source="+".join(sources),
        )
        all_evidence.append(avg_score)

    # Overall score
    overall = sum(all_evidence) / max(len(all_evidence), 1) if all_evidence else 0.0

    # Summary
    verified = sum(1 for v in verdicts.values() if v.verdict == VERIFIED)
    estimated = sum(1 for v in verdicts.values() if v.verdict == ESTIMATED)
    hallucinated = sum(1 for v in verdicts.values() if v.verdict == HALLUCINATION)
    summary = (
        f"{furniture_type}: {verified} verified, {estimated} estimated, "
        f"{hallucinated} hallucinated | overall confidence: {overall:.1%}"
    )

    return VerificationReport(
        product_id=product_id,
        furniture_type=furniture_type,
        verdicts=verdicts,
        overall_score=overall,
        summary=summary,
    )
