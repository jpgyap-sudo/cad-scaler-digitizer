"""
Anti-Hallucination Validator — enforce VISIBLE/ESTIMATED/UNKNOWN rules.

Rules:
  VISIBLE   (confidence >= 0.70) → draw SOLID on OBJECT layer
  ESTIMATED (0.30 <= confidence < 0.70) → draw DASHED/HIDDEN, label as "EST."
  UNKNOWN   (confidence < 0.30) → DO NOT DRAW

Prevents the CAD generator from inventing furniture parts not present
in the source image or reference material.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal

Visibility = Literal["VISIBLE", "ESTIMATED", "UNKNOWN"]


@dataclass
class ComponentVerdict:
    """Rendering decision for one furniture component."""
    name: str
    confidence: float          # 0.0 - 1.0
    visibility: Visibility
    layer: str                 # DXF layer to use
    linetype: str              # CONTINUOUS, HIDDEN, DASHED
    action: str                # "draw_solid", "draw_dashed", "draw_with_note", "skip"
    note: str = ""             # Annotation if estimated


@dataclass
class ValidationResult:
    """Complete validation pass over all components."""
    furniture_type: str
    components: Dict[str, ComponentVerdict]
    rejected: List[str]         # Components skipped (UNKNOWN)
    estimated: List[str]        # Components drawn dashed (ESTIMATED)
    visible: List[str]          # Components drawn solid (VISIBLE)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "furniture_type": self.furniture_type,
            "components": {
                k: {
                    "confidence": v.confidence,
                    "visibility": v.visibility,
                    "layer": v.layer,
                    "linetype": v.linetype,
                    "action": v.action,
                    "note": v.note,
                }
                for k, v in self.components.items()
            },
            "rejected": self.rejected,
            "estimated": self.estimated,
            "visible": self.visible,
            "summary": self.summary,
        }


# ===== Confidence thresholds =====
VISIBLE_THRESHOLD = 0.70    # >= 0.70: draw solid
ESTIMATED_THRESHOLD = 0.30  # >= 0.30: draw dashed/labeled
# < 0.30: UNKNOWN, skip entirely


def classify_visibility(confidence: float) -> Visibility:
    """Map confidence score to visibility class."""
    if confidence >= VISIBLE_THRESHOLD:
        return "VISIBLE"
    elif confidence >= ESTIMATED_THRESHOLD:
        return "ESTIMATED"
    else:
        return "UNKNOWN"


def layer_for_component(component_name: str, visibility: Visibility) -> str:
    """Choose the correct DXF layer based on component type and visibility."""
    if visibility == "UNKNOWN":
        return "HIDDEN"  # won't be drawn anyway

    # Component-specific layer rules
    component_lower = component_name.lower()

    if any(k in component_lower for k in ["dimension", "dia", "width", "height", "depth"]):
        return "DIMENSION"
    if any(k in component_lower for k in ["leader", "material", "callout", "note"]):
        return "LEADER"
    if any(k in component_lower for k in ["center", "axis"]):
        return "CENTER"
    if any(k in component_lower for k in ["hatch", "texture", "fill", "grain"]):
        return "HATCH"
    if any(k in component_lower for k in ["text", "label", "mtext"]):
        return "MTEXT"
    if any(k in component_lower for k in ["title", "border"]):
        return "TITLE"

    # Default: main geometry
    return "OBJECT"


def linetype_for_visibility(visibility: Visibility) -> str:
    """Choose linetype based on visibility class."""
    if visibility == "VISIBLE":
        return "CONTINUOUS"
    elif visibility == "ESTIMATED":
        return "HIDDEN"  # Dashed for estimated/inferred parts
    else:
        return "HIDDEN"


def action_for_visibility(visibility: Visibility) -> str:
    """Determine what action to take for this component."""
    if visibility == "VISIBLE":
        return "draw_solid"
    elif visibility == "ESTIMATED":
        return "draw_dashed"
    else:
        return "skip"


def validate_components(
    furniture_type: str,
    component_confidences: Dict[str, float],
    known_visible_parts: Optional[List[str]] = None,
) -> ValidationResult:
    """
    Validate all components against anti-hallucination rules.

    Args:
        furniture_type: canonical type (e.g. 'round_pedestal_table')
        component_confidences: {component_name: confidence_score}
        known_visible_parts: list of component names confirmed visible by AI/vision

    Returns:
        ValidationResult with rendering decisions for each component
    """
    visible_set = set(known_visible_parts or [])
    components: Dict[str, ComponentVerdict] = {}
    rejected: List[str] = []
    estimated: List[str] = []
    visible_list: List[str] = []

    for name, conf in component_confidences.items():
        # Known visible parts get a confidence boost
        if name in visible_set:
            conf = max(conf, 0.85)

        visibility = classify_visibility(conf)
        layer = layer_for_component(name, visibility)
        ltype = linetype_for_visibility(visibility)
        action = action_for_visibility(visibility)

        note = ""
        if visibility == "ESTIMATED":
            note = f"EST. from proportions — verify against source"
        elif visibility == "UNKNOWN":
            note = f"SKIPPED — not visible in source (confidence {conf:.2f})"

        verdict = ComponentVerdict(
            name=name,
            confidence=conf,
            visibility=visibility,
            layer=layer,
            linetype=ltype,
            action=action,
            note=note,
        )
        components[name] = verdict

        if visibility == "VISIBLE":
            visible_list.append(name)
        elif visibility == "ESTIMATED":
            estimated.append(name)
        else:
            rejected.append(name)

    summary = (
        f"{furniture_type}: {len(visible_list)} visible, "
        f"{len(estimated)} estimated, {len(rejected)} rejected"
    )

    return ValidationResult(
        furniture_type=furniture_type,
        components=components,
        rejected=rejected,
        estimated=estimated,
        visible=visible_list,
        summary=summary,
    )


# ===== Component templates for known furniture types =====
# These define the standard component names and default confidence
# scores for each furniture type. Used when no AI/vision data available.

ROUND_PEDESTAL_COMPONENTS = {
    "tabletop_diameter":       0.98,   # Measured from OCR
    "overall_height":           0.98,
    "top_thickness":            0.60,   # Estimated from ratio
    "pedestal_diameter":        0.72,
    "neck_diameter":            0.65,
    "pedestal_height":          0.55,
    "neck_height":              0.45,
    "base_foot":                0.35,   # Only if visible in source
    "metal_ring":               0.30,   # Only if described
    "wood_grain_texture":       0.85,   # Material note
    "hammered_texture":         0.60,   # Photographic texture
    "top_diameter_dimension":   0.98,
    "base_diameter_dimension":  0.85,
    "height_dimension":         0.98,
    "material_leader_top":      0.85,
    "material_leader_base":     0.75,
    "centerlines":              0.90,
    "title_block":              0.98,
}

RECTANGULAR_TABLE_COMPONENTS = {
    "top_width":                0.98,
    "top_depth":                0.85,
    "overall_height":           0.98,
    "top_thickness":            0.60,
    "leg_thickness":            0.65,
    "leg_count":                0.90,
    "stretcher":                0.40,
    "top_width_dimension":      0.98,
    "top_depth_dimension":      0.85,
    "height_dimension":         0.98,
    "title_block":              0.98,
}


def get_default_components(furniture_type: str) -> Dict[str, float]:
    """Return default component confidence scores for a furniture type."""
    defaults = {
        "round_pedestal_table": ROUND_PEDESTAL_COMPONENTS,
        "rectangular_table": RECTANGULAR_TABLE_COMPONENTS,
    }
    return defaults.get(furniture_type, {})


# Public API
def validate_furniture_drawing(
    furniture_type: str,
    component_confidences: Optional[Dict[str, float]] = None,
    known_visible_parts: Optional[List[str]] = None,
) -> ValidationResult:
    """
    Main entry point: validate all components before CAD generation.

    Merges visual_ratio_scaler confidence scores with default component
    templates, then applies anti-hallucination rules.
    """
    # Start with template defaults
    confidences = dict(get_default_components(furniture_type))

    # Override with actual ratio scaler confidences if provided
    if component_confidences:
        confidences.update(component_confidences)

    return validate_components(furniture_type, confidences, known_visible_parts)
