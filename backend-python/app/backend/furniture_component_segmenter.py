"""
Furniture Component Segmenter — identify sub-components of a furniture piece.

For round pedestal tables, identifies:
  - Tabletop (wood disc)
  - Neck / metal ring (narrow connector)
  - Pedestal body (textured column)
  - Base / foot (wider bottom cylinder)
  - Top view (plan view circle)
  - Front view (elevation)
  - Dimension lines
  - Leader annotations
  - Material callouts
  - Centerlines
  - Title block

Output: Dict of component → {present, confidence, layer, linetype}
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ComponentInfo:
    """Information about one detected/estimated component."""
    name: str
    present: bool            # Detected in source
    confidence: float        # 0.0 - 1.0
    source: str              # "ocr", "ai_vision", "ratio_estimate", "template"
    layer: str               # DXF layer
    visible: bool = True     # Should be drawn


@dataclass
class SegmentationResult:
    """Complete component breakdown of a furniture piece."""
    furniture_type: str
    components: Dict[str, ComponentInfo]
    ocr_text: List[str] = field(default_factory=list)
    ai_notes: List[str] = field(default_factory=list)

    def present_components(self) -> List[str]:
        return [k for k, v in self.components.items() if v.present]

    def estimated_components(self) -> List[str]:
        return [k for k, v in self.components.items()
                if v.present and v.source == "ratio_estimate"]

    def to_dict(self) -> dict:
        return {
            "furniture_type": self.furniture_type,
            "components": {
                k: {
                    "present": v.present,
                    "confidence": v.confidence,
                    "source": v.source,
                    "layer": v.layer,
                    "visible": v.visible,
                }
                for k, v in self.components.items()
            },
            "ocr_text": self.ocr_text,
            "ai_notes": self.ai_notes,
        }


# ===== Component definitions per furniture type =====

ROUND_PEDESTAL_SEGMENTS = {
    # (name, default_present, default_confidence, layer, detection_keywords)
    "tabletop":            (True,  0.98, "OBJECT",  ["table", "top", "disc", "wood top"]),
    "neck_ring":           (True,  0.70, "OBJECT",  ["neck", "ring", "metal", "black"]),
    "pedestal_body":       (True,  0.85, "OBJECT",  ["pedestal", "column", "body", "hammered"]),
    "base_foot":           (True,  0.50, "OBJECT",  ["base", "foot", "cylinder"]),
    "top_view":            (True,  0.98, "OBJECT",  ["top view", "plan"]),
    "front_view":          (True,  0.98, "OBJECT",  ["front view", "elevation"]),
    "top_diameter_dim":    (True,  0.98, "DIMENSION", ["dia", "diameter", "80"]),
    "base_diameter_dim":   (True,  0.85, "DIMENSION", ["dia", "44"]),
    "height_dim":          (True,  0.98, "DIMENSION", ["height", "h=", "70"]),
    "material_leader_top": (True,  0.85, "LEADER",   ["wood", "material"]),
    "material_leader_base":(True,  0.75, "LEADER",   ["textured", "pedestal", "hammered"]),
    "centerlines":         (True,  0.90, "CENTER",   ["center", "axis"]),
    "wood_grain_hatch":    (True,  0.75, "HATCH",    ["wood", "grain", "veneer"]),
    "texture_hatch":       (True,  0.60, "HATCH",    ["hammered", "texture"]),
    "title_block":         (True,  0.98, "TITLE",    ["title", "drawing"]),
}


def segment_round_pedestal_table(
    ocr_lines: List[str],
    ai_result: Optional[dict] = None,
    known_dims: Optional[Dict[str, float]] = None,
) -> SegmentationResult:
    """
    Segment a round pedestal table into its components.

    Uses OCR text + AI vision result to determine which components
    are visible in the source vs which are estimated from proportions.
    """
    text = " ".join(ocr_lines).lower()
    known = known_dims or {}
    ai_notes = ai_result.get("notes", []) if ai_result else []

    components: Dict[str, ComponentInfo] = {}

    for name, (default_present, default_conf, layer, keywords) in ROUND_PEDESTAL_SEGMENTS.items():
        # Check if this component is mentioned in OCR or AI notes
        mentioned_in_ocr = any(kw in text for kw in keywords)
        mentioned_in_ai = any(kw in " ".join(ai_notes).lower() for kw in keywords)

        if mentioned_in_ocr or mentioned_in_ai:
            # Confirmed visible by text reference
            conf = max(default_conf, 0.85)
            source = "ocr" if mentioned_in_ocr else "ai_vision"
            present = True
        elif default_present and default_conf >= 0.70:
            # High-confidence template component — draw solid
            conf = default_conf
            source = "template"
            present = True
        elif default_present and default_conf >= 0.30:
            # Estimated component — draw dashed/labeled
            conf = default_conf
            source = "ratio_estimate"
            present = True
        else:
            # Unknown/not visible — skip
            conf = default_conf
            source = "template"
            present = False

        components[name] = ComponentInfo(
            name=name,
            present=present,
            confidence=conf,
            source=source,
            layer=layer,
            visible=(conf >= 0.30),
        )

    # Boost confidence for components with known dimensions
    if "top_diameter_cm" in known:
        components["tabletop"].confidence = 0.98
        components["top_diameter_dim"].confidence = 0.98
    if "overall_height_cm" in known:
        components["height_dim"].confidence = 0.98
    if "pedestal_diameter_cm" in known:
        components["base_foot"].confidence = max(components["base_foot"].confidence, 0.80)

    return SegmentationResult(
        furniture_type="round_pedestal_table",
        components=components,
        ocr_text=ocr_lines,
        ai_notes=ai_notes,
    )


# Public API
def segment_furniture(
    furniture_type: str,
    ocr_lines: List[str],
    ai_result: Optional[dict] = None,
    known_dims: Optional[Dict[str, float]] = None,
) -> SegmentationResult:
    """
    Main entry point: segment a furniture piece into components.

    Args:
        furniture_type: canonical type (e.g. 'round_pedestal_table')
        ocr_lines: OCR text lines from the source image
        ai_result: optional AI vision analysis result
        known_dims: known anchor dimensions

    Returns:
        SegmentationResult with per-component presence/confidence/layer
    """
    if furniture_type == "round_pedestal_table":
        return segment_round_pedestal_table(ocr_lines, ai_result, known_dims)

    # Generic fallback for unsupported types
    return SegmentationResult(
        furniture_type=furniture_type,
        components={
            "geometry": ComponentInfo("geometry", True, 0.80, "ai_vision", "OBJECT"),
            "dimensions": ComponentInfo("dimensions", True, 0.80, "ai_vision", "DIMENSION"),
            "title_block": ComponentInfo("title_block", True, 0.98, "template", "TITLE"),
        },
        ocr_text=ocr_lines,
        ai_notes=ai_result.get("notes", []) if ai_result else [],
    )
