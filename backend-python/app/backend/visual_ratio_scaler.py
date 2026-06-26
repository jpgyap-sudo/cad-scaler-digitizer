"""
Visual Ratio Scaler — estimate component proportions from anchor dimensions.

Strategy:
1. Accept known anchor dimensions (top diameter, overall height) from OCR/AI
2. Estimate sub-component sizes using standard furniture proportion ratios
3. Apply confidence scoring: VISIBLE=high, INFERRED=medium, UNKNOWN=skip
4. Anti-hallucination: only return components with confidence > 0.3

Future: replace hardcoded ratios with AI/vision-based pixel measurement.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ComponentEstimate:
    """Estimated dimension for one furniture component."""
    value_cm: float
    confidence: float  # 0.0-1.0
    source: str  # "known", "ratio", "template_default", "inferred"


@dataclass
class ScaleResult:
    """Complete set of estimated dimensions for a furniture piece."""
    furniture_type: str
    known_dimensions: Dict[str, float]
    estimated_components: Dict[str, ComponentEstimate]
    confidence: Dict[str, float] = field(default_factory=dict)

    def get(self, key: str, default: float = 0.0) -> float:
        """Get estimated value with fallback."""
        if key in self.known_dimensions:
            return self.known_dimensions[key]
        if key in self.estimated_components:
            return self.estimated_components[key].value_cm
        return default

    def to_dict(self) -> dict:
        """Serialize for API response."""
        return {
            "furniture_type": self.furniture_type,
            "known_dimensions": self.known_dimensions,
            "estimated_components": {
                k: {"value_cm": v.value_cm, "confidence": v.confidence, "source": v.source}
                for k, v in self.estimated_components.items()
            },
            "confidence": {
                k: v.confidence
                for k, v in self.estimated_components.items()
            },
        }


# ===== Standard Furniture Proportion Ratios =====
# These are typical ratios derived from real furniture catalogs.
# Ratios are expressed relative to the TOP DIAMETER (for round tables)
# or TOP WIDTH (for rectangular tables).

ROUND_PEDESTAL_RATIOS = {
    # Component: (ratio_to_top_diameter, confidence, source)
    "pedestal_diameter_cm":   (0.55, 0.72, "ratio"),   # base is ~55% of top
    "neck_diameter_cm":       (0.28, 0.65, "ratio"),   # narrowest neck ~28% of top
    "top_thickness_cm":       (0.05, 0.60, "ratio"),   # top thickness ~4-5cm for 80cm table
    "pedestal_height_ratio":  (0.75, 0.55, "ratio"),   # pedestal body is ~75% of total height
    "neck_height_ratio":      (0.15, 0.45, "ratio"),   # neck is ~15% of total height
    "base_height_ratio":      (0.10, 0.45, "ratio"),   # base foot is ~10% of total height
}

RECTANGULAR_TABLE_RATIOS = {
    "leg_thickness_cm":       (0.05, 0.65, "ratio"),
    "top_thickness_cm":       (0.05, 0.60, "ratio"),
    "stretcher_height_ratio": (0.15, 0.45, "ratio"),
}


def _brain_estimate(furniture_type: str, anchor_dimension: str, anchor_value: float,
                    component: str, min_samples: int = 3, min_confidence: float = 0.3) -> Optional[Dict]:
    """Query Central Brain for a learned proportion, if it has enough real samples.

    Returns None below the sample/confidence floor so a handful of noisy
    early corrections can't outrank the standard furniture-catalog ratios.
    """
    try:
        from app.backend.brain_sync import get_proportion_estimate
        est = get_proportion_estimate(furniture_type, anchor_dimension, anchor_value, component)
        if est and est.get("sample_count", 0) >= min_samples and est.get("confidence", 0) >= min_confidence:
            return est
    except Exception as e:
        print(f"[VisualRatioScaler] Brain query failed: {e}")
    return None


def estimate_round_pedestal(top_diameter_cm: float, overall_height_cm: float,
                            ocr_components: Optional[Dict[str, float]] = None) -> ScaleResult:
    """
    Estimate round pedestal table component dimensions from anchor measurements.

    Uses known dimensions as anchors, then applies standard furniture ratios
    to estimate sub-component sizes. OCR-provided components override ratios.

    Anti-hallucination:
    - Components with confidence < 0.3 are excluded
    - Inferred components are marked with lower confidence
    - Only includes components that are standard for this furniture type
    """
    ocr = ocr_components or {}
    known = {
        "top_diameter_cm": top_diameter_cm,
        "overall_height_cm": overall_height_cm,
    }

    # Override with OCR if available
    for k, v in ocr.items():
        if v and v > 0:
            known[k] = v

    components: Dict[str, ComponentEstimate] = {}
    top_dia = known["top_diameter_cm"]
    total_h = known["overall_height_cm"]

    # ---- Estimate: OCR/visual known > Central Brain learned ratio > static ratio default ----
    # Pedestal diameter: typically 50-60% of top diameter
    ped_ratio, ped_conf, _ = ROUND_PEDESTAL_RATIOS["pedestal_diameter_cm"]
    if "pedestal_diameter_cm" in ocr:
        ped_dia, ped_src, ped_used_conf = ocr["pedestal_diameter_cm"], "known", 0.85
    else:
        brain = _brain_estimate("round_pedestal_table", "top_diameter_cm", top_dia, "pedestal_diameter_cm")
        if brain:
            ped_dia, ped_src = brain["estimated_value"], "brain"
            ped_used_conf = min(0.93, brain["confidence"])
        else:
            ped_dia, ped_src, ped_used_conf = top_dia * ped_ratio, "ratio", ped_conf
    components["pedestal_diameter_cm"] = ComponentEstimate(
        value_cm=round(ped_dia, 1), confidence=ped_used_conf, source=ped_src)

    # Neck diameter: narrowest part of pedestal
    neck_ratio, neck_conf, _ = ROUND_PEDESTAL_RATIOS["neck_diameter_cm"]
    if "neck_diameter_cm" in ocr:
        neck_dia, neck_src, neck_used_conf = ocr["neck_diameter_cm"], "known", 0.80
    else:
        brain = _brain_estimate("round_pedestal_table", "top_diameter_cm", top_dia, "neck_diameter_cm")
        if brain:
            neck_dia, neck_src = brain["estimated_value"], "brain"
            neck_used_conf = min(0.93, brain["confidence"])
        else:
            neck_dia, neck_src, neck_used_conf = top_dia * neck_ratio, "ratio", neck_conf
    components["neck_diameter_cm"] = ComponentEstimate(
        value_cm=round(neck_dia, 1), confidence=neck_used_conf, source=neck_src)

    # Top thickness
    thick_ratio, thick_conf, _ = ROUND_PEDESTAL_RATIOS["top_thickness_cm"]
    if "top_thickness_cm" in ocr:
        top_thick, thick_src, thick_used_conf = ocr["top_thickness_cm"], "known", 0.75
    else:
        brain = _brain_estimate("round_pedestal_table", "top_diameter_cm", top_dia, "top_thickness_cm")
        if brain:
            top_thick, thick_src = brain["estimated_value"], "brain"
            thick_used_conf = min(0.93, brain["confidence"])
        else:
            top_thick, thick_src, thick_used_conf = max(3.0, top_dia * thick_ratio), "ratio", thick_conf
    components["top_thickness_cm"] = ComponentEstimate(
        value_cm=round(top_thick, 1), confidence=thick_used_conf, source=thick_src)

    # Pedestal body height (main column portion)
    ped_h_ratio, ped_h_conf, _ = ROUND_PEDESTAL_RATIOS["pedestal_height_ratio"]
    ped_height = ocr.get("pedestal_height_cm") or (total_h * ped_h_ratio)
    components["pedestal_height_cm"] = ComponentEstimate(
        value_cm=round(ped_height, 1),
        confidence=0.70 if "pedestal_height_cm" in ocr else ped_h_conf,
        source="known" if "pedestal_height_cm" in ocr else "ratio"
    )

    # Neck height
    neck_h_ratio, neck_h_conf, _ = ROUND_PEDESTAL_RATIOS["neck_height_ratio"]
    neck_height = ocr.get("neck_height_cm") or (total_h * neck_h_ratio)
    components["neck_height_cm"] = ComponentEstimate(
        value_cm=round(neck_height, 1),
        confidence=0.60 if "neck_height_cm" in ocr else neck_h_conf,
        source="known" if "neck_height_cm" in ocr else "ratio"
    )

    # Base foot height
    base_h_ratio, base_h_conf, _ = ROUND_PEDESTAL_RATIOS["base_height_ratio"]
    base_height = ocr.get("base_height_cm") or (total_h * base_h_ratio)
    components["base_height_cm"] = ComponentEstimate(
        value_cm=round(base_height, 1),
        confidence=0.55 if "base_height_cm" in ocr else base_h_conf,
        source="known" if "base_height_cm" in ocr else "ratio"
    )

    # === ANTI-HALLUCINATION: Filter low-confidence components ===
    # Remove components that are pure guesses (confidence < 0.3)
    components = {
        k: v for k, v in components.items()
        if v.confidence >= 0.3
    }

    # Build confidence summary
    confidence = {
        k: v.confidence for k, v in components.items()
    }
    confidence.update({k: 0.98 for k in known})

    return ScaleResult(
        furniture_type="round_pedestal_table",
        known_dimensions=known,
        estimated_components=components,
        confidence=confidence,
    )


def estimate_rectangular_table(top_width_cm: float, top_depth_cm: float,
                                overall_height_cm: float,
                                ocr_components: Optional[Dict[str, float]] = None) -> ScaleResult:
    """Estimate rectangular table component dimensions."""
    ocr = ocr_components or {}
    known = {
        "top_width_cm": top_width_cm,
        "top_depth_cm": top_depth_cm,
        "overall_height_cm": overall_height_cm,
    }
    for k, v in ocr.items():
        if v and v > 0:
            known[k] = v

    components: Dict[str, ComponentEstimate] = {}

    # Leg thickness
    leg_ratio, leg_conf, _ = RECTANGULAR_TABLE_RATIOS["leg_thickness_cm"]
    leg = ocr.get("leg_thickness_cm") or (top_width_cm * leg_ratio)
    components["leg_thickness_cm"] = ComponentEstimate(
        value_cm=round(leg, 1),
        confidence=leg_conf,
        source="known" if "leg_thickness_cm" in ocr else "ratio"
    )

    # Top thickness
    thick_ratio, thick_conf, _ = RECTANGULAR_TABLE_RATIOS["top_thickness_cm"]
    top_thick = ocr.get("top_thickness_cm") or max(3.0, top_width_cm * thick_ratio)
    components["top_thickness_cm"] = ComponentEstimate(
        value_cm=round(top_thick, 1),
        confidence=thick_conf,
        source="known" if "top_thickness_cm" in ocr else "ratio"
    )

    confidence = {k: v.confidence for k, v in components.items()}
    confidence.update({k: 0.98 for k in known})

    return ScaleResult(
        furniture_type="rectangular_table",
        known_dimensions=known,
        estimated_components=components,
        confidence=confidence,
    )


# Public API
def estimate_proportions(furniture_type: str, known_dims: Dict[str, float],
                         ocr_components: Optional[Dict[str, float]] = None) -> ScaleResult:
    """
    Main entry point: estimate component proportions for any furniture type.

    Args:
        furniture_type: canonical type (e.g. 'round_pedestal_table')
        known_dims: anchor dimensions from OCR/AI (e.g. top_diameter_cm, overall_height_cm)
        ocr_components: optional OCR-detected sub-component dimensions

    Returns:
        ScaleResult with estimated components and confidence scores
    """
    if furniture_type == "round_pedestal_table":
        return estimate_round_pedestal(
            known_dims.get("top_diameter_cm", 80.0),
            known_dims.get("overall_height_cm", 70.0),
            ocr_components,
        )
    elif furniture_type == "rectangular_table":
        return estimate_rectangular_table(
            known_dims.get("top_width_cm", 120.0),
            known_dims.get("top_depth_cm", 80.0),
            known_dims.get("overall_height_cm", 70.0),
            ocr_components,
        )
    else:
        # Generic fallback: return known dims only, no estimates
        return ScaleResult(
            furniture_type=furniture_type,
            known_dimensions=known_dims,
            estimated_components={},
            confidence={k: 0.98 for k in known_dims},
        )
