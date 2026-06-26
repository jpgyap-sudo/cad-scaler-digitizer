"""
Visual Ratio Scaler — estimate component proportions from anchor dimensions.

RESOLVED PRIORITY ORDER (was: ratio-first):
1. MEASURED: pixel geometry × confirmed scale factor → cm
2. OCR_CONFIRMED: dimension label text from image
3. USER_CONFIRMED: user-provided or chat-corrected values
4. INFERRED: pixel measurement with estimated/weak scale
5. RATIO: standard furniture proportion ratios (fallback)
6. TEMPLATE_DEFAULT: hardcoded default (last resort)

Anti-hallucination:
- Every component tracks its source and confidence
- Components with confidence < 0.3 are excluded
- Ratios never override visible geometry
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple


@dataclass
class ComponentEstimate:
    """Estimated dimension for one furniture component."""
    value_cm: float
    confidence: float  # 0.0-1.0
    source: str  # "measured", "ocr_confirmed", "user_confirmed", "inferred", "ratio", "template_default"

    def to_dict(self) -> dict:
        return {
            "value_cm": round(self.value_cm, 2),
            "confidence": round(self.confidence, 2),
            "source": self.source,
        }


@dataclass
class ScaleResult:
    """Complete set of estimated dimensions for a furniture piece."""
    furniture_type: str
    known_dimensions: Dict[str, float]
    estimated_components: Dict[str, ComponentEstimate]
    confidence: Dict[str, float] = field(default_factory=dict)
    scale_solution_ref: Optional[dict] = None

    def get(self, key: str, default: float = 0.0) -> float:
        """Get estimated value with fallback."""
        if key in self.known_dimensions:
            return self.known_dimensions[key]
        if key in self.estimated_components:
            return self.estimated_components[key].value_cm
        return default

    def to_dict(self) -> dict:
        return {
            "furniture_type": self.furniture_type,
            "known_dimensions": self.known_dimensions,
            "estimated_components": {
                k: v.to_dict() for k, v in self.estimated_components.items()
            },
            "confidence": {
                k: v.confidence for k, v in self.estimated_components.items()
            },
            "scale_solution": self.scale_solution_ref,
        }


# ===== Standard Furniture Proportion Ratios =====
# Used ONLY as fallback when no pixel measurement or OCR is available.

ROUND_PEDESTAL_RATIOS = {
    "pedestal_diameter_cm":   (0.55, 0.45, "ratio"),
    "neck_diameter_cm":       (0.28, 0.35, "ratio"),
    "top_thickness_cm":       (0.05, 0.35, "ratio"),
    "pedestal_height_ratio":  (0.75, 0.30, "ratio"),
    "neck_height_ratio":      (0.15, 0.25, "ratio"),
    "base_height_ratio":      (0.10, 0.25, "ratio"),
}

RECTANGULAR_TABLE_RATIOS = {
    "leg_thickness_cm":       (0.05, 0.35, "ratio"),
    "top_thickness_cm":       (0.05, 0.35, "ratio"),
    "stretcher_height_ratio": (0.15, 0.25, "ratio"),
}


def _compute_from_scale_solution(
    scale_solution: Optional[dict],
    component_key: str,
    pixel_value: Optional[float] = None,
) -> Optional[ComponentEstimate]:
    """
    Try to compute a component value from a resolved scale solution.

    If a pixel measurement is available and we have a scale factor,
    this is the most accurate source.
    """
    if not scale_solution or pixel_value is None:
        return None

    px_per_cm = None
    confidence = 0.5
    source = "inferred"

    # Extract best available scale factor
    combined = scale_solution.get("combined_scale")
    if combined and combined.get("confidence", 0) > 0.3:
        px_per_cm = combined["px_per_cm"]
        confidence = combined["confidence"] * 0.9  # Discount slightly
        source = "inferred"

    if px_per_cm and px_per_cm > 0:
        value_cm = pixel_value / px_per_cm
        return ComponentEstimate(
            value_cm=round(value_cm, 1),
            confidence=confidence,
            source=source,
        )

    return None


def estimate_round_pedestal(
    top_diameter_cm: float,
    overall_height_cm: float,
    ocr_components: Optional[Dict[str, float]] = None,
    scale_solution: Optional[dict] = None,
    pixel_measurements: Optional[Dict[str, float]] = None,
) -> ScaleResult:
    """
    Estimate round pedestal table component dimensions.

    PRIORITY:
    1. Pixel measurement × scale factor (most accurate)
    2. OCR-detected component dimensions
    3. Scale solution derived from other dimensions
    4. Ratio-based estimate (fallback)

    Args:
        top_diameter_cm: Tabletop diameter from OCR/user
        overall_height_cm: Total height from OCR/user
        ocr_components: Optional OCR-detected sub-component dimensions
        scale_solution: Optional resolved scale solution from scale_solver
        pixel_measurements: Optional pixel measurements (e.g., pedestal_diameter_px)

    Returns:
        ScaleResult with estimated components and confidence scores
    """
    ocr = ocr_components or {}
    pixel = pixel_measurements or {}
    known: Dict[str, float] = {
        "top_diameter_cm": top_diameter_cm,
        "overall_height_cm": overall_height_cm,
    }
    for k, v in ocr.items():
        if v and v > 0:
            known[k] = v

    components: Dict[str, ComponentEstimate] = {}
    top_dia = known["top_diameter_cm"]
    total_h = known["overall_height_cm"]

    def _resolve(key: str, ratio_key: str, pixel_key: str,
                 default_ratio: float, default_conf: float,
                 ocr_key: str = None) -> ComponentEstimate:
        """
        Resolve a single component using priority chain:
        pixel × scale → OCR → ratio → default
        """
        ocr_k = ocr_key or key

        # Priority 1: Pixel measurement × scale
        if scale_solution and pixel_key in pixel:
            px_val = pixel[pixel_key]
            est = _compute_from_scale_solution(scale_solution, key, px_val)
            if est and est.confidence >= 0.5:
                return est

        # Priority 2: OCR-confirmed value
        if ocr_k in ocr and ocr[ocr_k] > 0:
            return ComponentEstimate(
                value_cm=round(ocr[ocr_k], 1),
                confidence=0.85,
                source="ocr_confirmed",
            )

        # Priority 3: Scale solution from other dimensions
        if scale_solution:
            resolved = scale_solution.get("resolved_dimensions", {})
            if key in resolved and resolved[key].get("confidence", 0) > 0.5:
                return ComponentEstimate(
                    value_cm=round(resolved[key]["value_cm"], 1),
                    confidence=resolved[key]["confidence"],
                    source="inferred",
                )

        # Priority 4: Ratio estimate (fallback)
        return ComponentEstimate(
            value_cm=round(top_dia * default_ratio, 1),
            confidence=default_conf,
            source="ratio",
        )

    # Pedestal diameter
    ped_ratio, ped_conf, _ = ROUND_PEDESTAL_RATIOS["pedestal_diameter_cm"]
    components["pedestal_diameter_cm"] = _resolve(
        "pedestal_diameter_cm", "pedestal_diameter_cm", "pedestal_diameter_px",
        ped_ratio, ped_conf, "pedestal_diameter_cm")

    # Neck diameter
    neck_ratio, neck_conf, _ = ROUND_PEDESTAL_RATIOS["neck_diameter_cm"]
    components["neck_diameter_cm"] = _resolve(
        "neck_diameter_cm", "neck_diameter_cm", "neck_diameter_px",
        neck_ratio, neck_conf, "neck_diameter_cm")

    # Top thickness
    thick_ratio, thick_conf, _ = ROUND_PEDESTAL_RATIOS["top_thickness_cm"]
    top_thick = _resolve(
        "top_thickness_cm", "top_thickness_cm", "top_thickness_px",
        thick_ratio, thick_conf, "top_thickness_cm")
    components["top_thickness_cm"] = top_thick

    # Pedestal body height
    ped_h_ratio, ped_h_conf, _ = ROUND_PEDESTAL_RATIOS["pedestal_height_ratio"]
    ped_height_val = ocr.get("pedestal_height_cm", total_h * ped_h_ratio)
    ped_src = "ocr_confirmed" if "pedestal_height_cm" in ocr else "ratio"
    components["pedestal_height_cm"] = ComponentEstimate(
        value_cm=round(ped_height_val, 1),
        confidence=0.70 if "pedestal_height_cm" in ocr else ped_h_conf,
        source=ped_src,
    )

    # Neck height
    neck_h_ratio, neck_h_conf, _ = ROUND_PEDESTAL_RATIOS["neck_height_ratio"]
    neck_height_val = ocr.get("neck_height_cm", total_h * neck_h_ratio)
    neck_src = "ocr_confirmed" if "neck_height_cm" in ocr else "ratio"
    components["neck_height_cm"] = ComponentEstimate(
        value_cm=round(neck_height_val, 1),
        confidence=0.60 if "neck_height_cm" in ocr else neck_h_conf,
        source=neck_src,
    )

    # Base foot height
    base_h_ratio, base_h_conf, _ = ROUND_PEDESTAL_RATIOS["base_height_ratio"]
    base_height_val = ocr.get("base_height_cm", total_h * base_h_ratio)
    base_src = "ocr_confirmed" if "base_height_cm" in ocr else "ratio"
    components["base_height_cm"] = ComponentEstimate(
        value_cm=round(base_height_val, 1),
        confidence=0.55 if "base_height_cm" in ocr else base_h_conf,
        source=base_src,
    )

    # === ANTI-HALLUCINATION: Filter low-confidence components ===
    components = {k: v for k, v in components.items() if v.confidence >= 0.3}

    # Build confidence summary
    confidence = {k: v.confidence for k, v in components.items()}
    confidence.update({k: 0.98 for k in known})

    return ScaleResult(
        furniture_type="round_pedestal_table",
        known_dimensions=known,
        estimated_components=components,
        confidence=confidence,
        scale_solution_ref=scale_solution.to_dict() if hasattr(scale_solution, 'to_dict') else scale_solution,
    )


def estimate_rectangular_table(
    top_width_cm: float,
    top_depth_cm: float,
    overall_height_cm: float,
    ocr_components: Optional[Dict[str, float]] = None,
    scale_solution: Optional[dict] = None,
    pixel_measurements: Optional[Dict[str, float]] = None,
) -> ScaleResult:
    """Estimate rectangular table component dimensions."""
    ocr = ocr_components or {}
    pixel = pixel_measurements or {}
    known = {
        "top_width_cm": top_width_cm,
        "top_depth_cm": top_depth_cm,
        "overall_height_cm": overall_height_cm,
    }
    for k, v in ocr.items():
        if v and v > 0:
            known[k] = v

    components: Dict[str, ComponentEstimate] = {}
    top_w = known["top_width_cm"]

    # Leg thickness
    leg_ratio, leg_conf, _ = RECTANGULAR_TABLE_RATIOS["leg_thickness_cm"]

    # Try pixel × scale first
    leg_from_scale = None
    if scale_solution and "leg_thickness_px" in pixel:
        leg_from_scale = _compute_from_scale_solution(
            scale_solution, "leg_thickness_cm", pixel["leg_thickness_px"])

    if leg_from_scale:
        components["leg_thickness_cm"] = leg_from_scale
    elif "leg_thickness_cm" in ocr:
        components["leg_thickness_cm"] = ComponentEstimate(
            value_cm=round(ocr["leg_thickness_cm"], 1),
            confidence=0.75, source="ocr_confirmed")
    else:
        components["leg_thickness_cm"] = ComponentEstimate(
            value_cm=round(top_w * leg_ratio, 1),
            confidence=leg_conf, source="ratio")

    # Top thickness
    thick_ratio, thick_conf, _ = RECTANGULAR_TABLE_RATIOS["top_thickness_cm"]
    if "top_thickness_cm" in ocr:
        components["top_thickness_cm"] = ComponentEstimate(
            value_cm=round(ocr["top_thickness_cm"], 1),
            confidence=0.75, source="ocr_confirmed")
    else:
        components["top_thickness_cm"] = ComponentEstimate(
            value_cm=round(max(3.0, top_w * thick_ratio), 1),
            confidence=thick_conf, source="ratio")

    confidence = {k: v.confidence for k, v in components.items()}
    confidence.update({k: 0.98 for k in known})

    return ScaleResult(
        furniture_type="rectangular_table",
        known_dimensions=known,
        estimated_components=components,
        confidence=confidence,
        scale_solution_ref=scale_solution.to_dict() if hasattr(scale_solution, 'to_dict') else scale_solution,
    )


# Public API
def estimate_proportions(
    furniture_type: str,
    known_dims: Dict[str, float],
    ocr_components: Optional[Dict[str, float]] = None,
    scale_solution: Optional[dict] = None,
    pixel_measurements: Optional[Dict[str, float]] = None,
) -> ScaleResult:
    """
    Main entry point: estimate component proportions for any furniture type.

    PRIORITY:
    1. Pixel measurement × scale factor
    2. OCR/AI dimension labels
    3. Scale solution from other confirmed pairs
    4. Standard furniture ratios
    5. Template defaults

    Args:
        furniture_type: canonical type (e.g. 'round_pedestal_table')
        known_dims: anchor dimensions from OCR/AI
        ocr_components: optional OCR-detected sub-component dimensions
        scale_solution: optional resolved scale solution
        pixel_measurements: optional pixel measurements (e.g., pedestal_base_px)

    Returns:
        ScaleResult with estimated components and confidence scores
    """
    if furniture_type == "round_pedestal_table":
        return estimate_round_pedestal(
            known_dims.get("top_diameter_cm", 80.0),
            known_dims.get("overall_height_cm", 70.0),
            ocr_components,
            scale_solution,
            pixel_measurements,
        )
    elif furniture_type == "rectangular_table":
        return estimate_rectangular_table(
            known_dims.get("top_width_cm", 120.0),
            known_dims.get("top_depth_cm", 80.0),
            known_dims.get("overall_height_cm", 70.0),
            ocr_components,
            scale_solution,
            pixel_measurements,
        )
    else:
        return ScaleResult(
            furniture_type=furniture_type,
            known_dimensions=known_dims,
            estimated_components={},
            confidence={k: 0.98 for k in known_dims},
        )
