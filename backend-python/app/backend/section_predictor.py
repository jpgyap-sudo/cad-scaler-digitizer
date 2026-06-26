"""
Section Predictor — ML-aware shop drawing section prediction from product data.

Uses real product catalog data (from homeu.ph and similar sites) to predict
which shop drawing sections should be generated for each furniture type.

Predicts:
- Which views to include (front, top, side, section, detail)
- Which components belong in each view
- Whether a section is required vs optional (based on dimensions)
- Recommended scale for detail views

The prediction model is rule-based now, but designed to accept ML training
from correction feedback over time.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Literal
from pathlib import Path
import json

ViewType = Literal["front", "top", "side", "section", "detail"]
SectionStatus = Literal["required", "optional", "conditional"]


@dataclass
class DrawingSection:
    """A single section/view in a shop drawing."""
    name: str                       # e.g. "front_view", "detail_view_leg"
    view_type: ViewType             # front, top, side, section, detail
    status: SectionStatus           # required, optional, conditional
    condition: str = ""             # e.g. "depth > 60cm" for conditional
    components: List[str] = field(default_factory=list)
    scale: str = "1:2"              # Drawing scale for this section
    confidence: float = 0.9         # ML prediction confidence

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "view_type": self.view_type,
            "status": self.status,
            "condition": self.condition,
            "components": self.components,
            "scale": self.scale,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class SectionPrediction:
    """Complete section prediction for a furniture piece."""
    furniture_type: str
    parameters: Dict[str, float]     # e.g. {w: 160, d: 90, h: 75}
    sections: List[DrawingSection]
    source: str = "rule_based"      # "rule_based" | "ml_trained"
    confidence: float = 0.85

    def to_dict(self) -> dict:
        return {
            "furniture_type": self.furniture_type,
            "parameters": self.parameters,
            "sections": [s.to_dict() for s in self.sections],
            "source": self.source,
            "confidence": round(self.confidence, 2),
            "summary": self.summary(),
        }

    def summary(self) -> str:
        active = [s for s in self.sections
                  if s.status == "required" or
                  (s.status == "conditional" and not s.condition)]
        return f"{len(active)} active sections: {', '.join(s.name for s in active)}"

    def active_sections(self) -> List[DrawingSection]:
        """Return sections that should be rendered (required + met conditions)."""
        result = []
        for s in self.sections:
            if s.status == "required":
                result.append(s)
            elif s.status == "conditional":
                # Evaluate condition
                if s.condition:
                    try:
                        if eval(s.condition, {"__builtins__": {}}, self.parameters):
                            result.append(s)
                    except: pass
                else:
                    result.append(s)
        return result


# ===== Section Templates by Furniture Type =====
# These are derived from real catalog data and professional shop drawing standards.

SECTION_TEMPLATES: Dict[str, List[Dict]] = {
    "sofa": [
        {
            "name": "front_view", "view_type": "front", "status": "required",
            "components": ["seat", "backrest", "armrest_left", "armrest_right"],
            "scale": "1:5",
        },
        {
            "name": "top_view", "view_type": "top", "status": "required",
            "components": ["seat_platform", "armrest_top"],
            "scale": "1:5",
        },
        {
            "name": "section_view", "view_type": "section", "status": "conditional",
            "condition": "d > 60",
            "components": ["cushion_profile", "frame", "spring_system"],
            "scale": "1:3",
        },
        {
            "name": "detail_view_armrest", "view_type": "detail", "status": "required",
            "components": ["armrest_detail", "joint_detail"],
            "scale": "1:2",
        },
        {
            "name": "side_view", "view_type": "side", "status": "conditional",
            "condition": "w > 150",
            "components": ["backrest_profile", "seat_profile"],
            "scale": "1:5",
        },
    ],
    "rectangular_table": [
        {
            "name": "front_view", "view_type": "front", "status": "required",
            "components": ["tabletop", "legs_front"],
            "scale": "1:5",
        },
        {
            "name": "top_view", "view_type": "top", "status": "required",
            "components": ["tabletop_plan", "leg_footprints"],
            "scale": "1:5",
        },
        {
            "name": "side_view", "view_type": "side", "status": "conditional",
            "condition": "d > 60",
            "components": ["leg_side", "stretcher"],
            "scale": "1:5",
        },
        {
            "name": "detail_view_leg", "view_type": "detail", "status": "required",
            "components": ["leg_detail", "joint_detail"],
            "scale": "1:2",
        },
        {
            "name": "detail_view_edge", "view_type": "detail", "status": "conditional",
            "condition": "thickness > 3",
            "components": ["edge_profile"],
            "scale": "1:1",
        },
    ],
    "round_pedestal_table": [
        {
            "name": "front_view", "view_type": "front", "status": "required",
            "components": ["tabletop", "pedestal_column", "base_foot"],
            "scale": "1:5",
        },
        {
            "name": "top_view", "view_type": "top", "status": "required",
            "components": ["tabletop_plan"],
            "scale": "1:5",
        },
        {
            "name": "detail_view_pedestal", "view_type": "detail", "status": "required",
            "components": ["neck_ring", "collar_plate"],
            "scale": "1:2",
        },
        {
            "name": "detail_view_base", "view_type": "detail", "status": "conditional",
            "condition": "dia > 80",
            "components": ["base_plate", "glide_detail"],
            "scale": "1:2",
        },
    ],
    "dining_chair": [
        {
            "name": "front_view", "view_type": "front", "status": "required",
            "components": ["backrest", "seat", "legs_front", "rung"],
            "scale": "1:3",
        },
        {
            "name": "side_view", "view_type": "side", "status": "required",
            "components": ["backrest_profile", "seat_profile", "leg_side"],
            "scale": "1:3",
        },
        {
            "name": "detail_view_frame", "view_type": "detail", "status": "required",
            "components": ["joint_detail", "corner_block"],
            "scale": "1:1",
        },
    ],
    "bed_headboard": [
        {
            "name": "front_view", "view_type": "front", "status": "required",
            "components": ["headboard_panel", "legs", "top_rail"],
            "scale": "1:5",
        },
        {
            "name": "side_view", "view_type": "side", "status": "required",
            "components": ["headboard_profile", "leg_side"],
            "scale": "1:5",
        },
        {
            "name": "detail_view_carving", "view_type": "detail", "status": "conditional",
            "condition": "h > 80",
            "components": ["carving_detail", "panel_joinery"],
            "scale": "1:1",
        },
    ],
    "cabinet": [
        {
            "name": "front_view", "view_type": "front", "status": "required",
            "components": ["doors", "body", "handles", "divider"],
            "scale": "1:5",
        },
        {
            "name": "section_view", "view_type": "section", "status": "required",
            "components": ["shelves", "back_panel", "drawer_profile"],
            "scale": "1:3",
        },
        {
            "name": "detail_view_hinge", "view_type": "detail", "status": "required",
            "components": ["hinge_detail", "mounting_plate"],
            "scale": "1:1",
        },
        {
            "name": "detail_view_handle", "view_type": "detail", "status": "required",
            "components": ["handle_profile"],
            "scale": "1:1",
        },
    ],
    "coffee_table": [
        {
            "name": "front_view", "view_type": "front", "status": "required",
            "components": ["tabletop", "base"],
            "scale": "1:3",
        },
        {
            "name": "top_view", "view_type": "top", "status": "required",
            "components": ["tabletop_plan"],
            "scale": "1:3",
        },
    ],
}


def predict_sections(
    furniture_type: str,
    parameters: Dict[str, float],
    source: str = "rule_based",
) -> SectionPrediction:
    """
    Predict which shop drawing sections to generate for a furniture piece.

    Uses the section templates derived from real catalog data.
    Supports conditional sections based on dimensions.

    Args:
        furniture_type: Canonical type (e.g. "rectangular_table")
        parameters: Dict with dimension parameters (w, d, h, dia, sh, etc.)
        source: "rule_based" or "ml_trained"

    Returns:
        SectionPrediction with all applicable sections
    """
    templates = SECTION_TEMPLATES.get(furniture_type, [])
    if not templates:
        # Fallback: basic front and top view only
        templates = [
            {"name": "front_view", "view_type": "front", "status": "required",
             "components": ["main_body"], "scale": "1:5"},
            {"name": "top_view", "view_type": "top", "status": "required",
             "components": ["top_plan"], "scale": "1:5"},
        ]

    sections: List[DrawingSection] = []
    for t in templates:
        sections.append(DrawingSection(
            name=t["name"],
            view_type=t["view_type"],
            status=t["status"],
            condition=t.get("condition", ""),
            components=t.get("components", []),
            scale=t.get("scale", "1:2"),
            confidence=0.9 if t["status"] == "required" else 0.65,
        ))

    confidence = 0.85 if source == "rule_based" else 0.92

    return SectionPrediction(
        furniture_type=furniture_type,
        parameters=parameters,
        sections=sections,
        source=source,
        confidence=confidence,
    )


def sections_from_fixture(fixture_path: str) -> Optional[SectionPrediction]:
    """
    Load a fixture spec and generate section predictions.
    """
    path = Path(fixture_path)
    if not path.exists():
        return None

    with open(path) as f:
        spec = json.load(f)

    params = spec.get("parameters", {})
    ftype = spec.get("furniture_type", "generic_2d_furniture")

    return predict_sections(ftype, params)


def generate_shop_drawing_layout(
    sections: SectionPrediction,
    page_width: float = 420.0,
    page_height: float = 297.0,
) -> List[dict]:
    """
    Generate a layout plan for the shop drawing based on predicted sections.

    Arranges sections on the page with:
    - Main views (front, top) at largest scale
    - Side/section views on the right
    - Detail views at bottom or in callout boxes
    - Title block at bottom-right
    """
    active = sections.active_sections()

    layout: List[dict] = []
    x, y = 10.0, page_height - 20.0
    main_width = page_width * 0.55
    side_width = page_width * 0.35
    detail_height = 60.0

    for sec in active:
        if sec.view_type in ("front", "top"):
            layout.append({
                "section": sec.name,
                "position": {"x": round(x, 1), "y": round(y, 1)},
                "size": {"width": round(main_width, 1), "height": round((page_height - 40) / 3, 1)},
                "scale": sec.scale,
                "components": sec.components,
            })
            y -= (page_height - 40) / 3

        elif sec.view_type in ("side", "section"):
            layout.append({
                "section": sec.name,
                "position": {"x": round(x + main_width + 10, 1), "y": round(page_height - 30, 1)},
                "size": {"width": round(side_width, 1), "height": round((page_height - 60) / 2, 1)},
                "scale": sec.scale,
                "components": sec.components,
            })

        elif sec.view_type == "detail":
            layout.append({
                "section": sec.name,
                "position": {"x": round(x + main_width + 10, 1),
                              "y": round(30 + (len([s for s in active if s.view_type == "detail"]) - 1) * detail_height, 1)},
                "size": {"width": round(side_width, 1), "height": round(detail_height, 1)},
                "scale": sec.scale,
                "components": sec.components,
            })

    return layout


# Public API
def predict_drawing_sections(
    furniture_type: str,
    parameters: Dict[str, float],
) -> dict:
    """
    Main entry point: predict shop drawing sections and return layout plan.
    """
    prediction = predict_sections(furniture_type, parameters)
    layout = generate_shop_drawing_layout(prediction)

    return {
        "prediction": prediction.to_dict(),
        "layout": layout,
        "active_section_count": len(prediction.active_sections()),
        "total_sections": len(prediction.sections),
    }
