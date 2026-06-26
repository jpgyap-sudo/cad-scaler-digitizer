"""
Intermediate Drawing Model — JSON representation between AI pipeline and CAD output.

Every entity carries confidence metadata:
  {
    "source": "measured_from_pixels | ocr_confirmed | user_confirmed |
               ratio_estimated | default_template",
    "confidence": 0.0-1.0,
    "evidence": ["ocr_box_id:12", "line_id:45", "scale_factor:0.5"]
  }
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Literal
import json
import math


# ===== Entity Metadata =====

@dataclass
class EntityMetadata:
    """Provenance and confidence metadata for every CAD entity."""
    source: str = "unknown"       # "measured", "ocr_confirmed", "user_confirmed", "ratio", "default"
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence[:3],
        }


# ===== Primitive Types =====

@dataclass
class Point:
    x: float
    y: float

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    @classmethod
    def from_tuple(cls, t: Tuple[float, float]) -> "Point":
        return cls(x=t[0], y=t[1])


@dataclass
class CircleComponent:
    """Circle primitive with metadata."""
    type: Literal["circle"] = "circle"
    center: Point = field(default_factory=lambda: Point(0, 0))
    radius: float = 0.0
    layer: str = "OBJECT"
    metadata: EntityMetadata = field(default_factory=EntityMetadata)


@dataclass
class PolygonComponent:
    """Closed polygon (LWPOLYLINE) with metadata."""
    type: Literal["polygon"] = "polygon"
    points: List[Point] = field(default_factory=list)
    layer: str = "OBJECT"
    name: str = ""
    linetype: str = "CONTINUOUS"
    metadata: EntityMetadata = field(default_factory=EntityMetadata)


@dataclass
class LineComponent:
    """Single line segment with metadata."""
    type: Literal["line"] = "line"
    start: Point = field(default_factory=lambda: Point(0, 0))
    end: Point = field(default_factory=lambda: Point(0, 0))
    layer: str = "OBJECT"
    metadata: EntityMetadata = field(default_factory=EntityMetadata)


@dataclass
class TextComponent:
    """Single-line text annotation with metadata."""
    type: Literal["text"] = "text"
    content: str = ""
    position: Point = field(default_factory=lambda: Point(0, 0))
    height: float = 3.0
    layer: str = "MTEXT"
    metadata: EntityMetadata = field(default_factory=EntityMetadata)


@dataclass
class DimensionComponent:
    """Dimension with label and metadata."""
    type: Literal["dimension"] = "dimension"
    p1: Point = field(default_factory=lambda: Point(0, 0))
    p2: Point = field(default_factory=lambda: Point(0, 0))
    label: str = ""
    layer: str = "DIMENSION"
    metadata: EntityMetadata = field(default_factory=EntityMetadata)


@dataclass
class LeaderComponent:
    """Leader line with arrowhead and text, with metadata."""
    type: Literal["leader"] = "leader"
    start: Point = field(default_factory=lambda: Point(0, 0))
    end: Point = field(default_factory=lambda: Point(0, 0))
    text: str = ""
    layer: str = "LEADER"
    metadata: EntityMetadata = field(default_factory=EntityMetadata)


@dataclass
class HatchComponent:
    """Hatch fill for a polygon, with metadata."""
    type: Literal["hatch"] = "hatch"
    points: List[Point] = field(default_factory=list)
    pattern: str = "ANSI31"
    scale: float = 0.3
    angle_deg: float = 45.0
    layer: str = "HATCH"
    metadata: EntityMetadata = field(default_factory=EntityMetadata)


# ===== View =====

@dataclass
class View:
    """A single view (top, front, side) within the drawing."""
    name: str
    circles: List[CircleComponent] = field(default_factory=list)
    polygons: List[PolygonComponent] = field(default_factory=list)
    lines: List[LineComponent] = field(default_factory=list)
    texts: List[TextComponent] = field(default_factory=list)
    dimensions: List[DimensionComponent] = field(default_factory=list)
    leaders: List[LeaderComponent] = field(default_factory=list)
    hatches: List[HatchComponent] = field(default_factory=list)


# ===== Title Block =====

@dataclass
class TitleBlockData:
    """Title block metadata."""
    drawing_title: str = "Furniture Drawing"
    project: str = ""
    client: str = ""
    scale: str = "1:1"
    revision: str = "A"
    designer: str = "AI CAD Drafter"
    date: str = ""
    material_notes: List[str] = field(default_factory=list)
    general_notes: List[str] = field(default_factory=list)


# ===== Full Drawing Model =====

@dataclass
class DrawingModel:
    """Complete furniture shop drawing with entity-level confidence metadata."""
    furniture_type: str = ""
    page_width: float = 420.0
    page_height: float = 297.0
    scale: float = 0.5
    views: List[View] = field(default_factory=list)
    title_block: TitleBlockData = field(default_factory=TitleBlockData)
    known_dimensions: Dict[str, float] = field(default_factory=dict)
    estimated_components: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict with metadata."""
        def point_list(pts):
            return [{"x": p.x, "y": p.y} for p in pts]

        def meta(m):
            return m.to_dict() if m else None

        return {
            "furniture_type": self.furniture_type,
            "page_width": self.page_width,
            "page_height": self.page_height,
            "scale": self.scale,
            "views": [
                {
                    "name": v.name,
                    "circles": [{
                        "center": {"x": c.center.x, "y": c.center.y},
                        "radius": c.radius, "layer": c.layer,
                        "metadata": meta(c.metadata),
                    } for c in v.circles],
                    "polygons": [{
                        "points": point_list(p.points), "layer": p.layer,
                        "name": p.name, "linetype": p.linetype,
                        "metadata": meta(p.metadata),
                    } for p in v.polygons],
                    "lines": [{
                        "start": {"x": l.start.x, "y": l.start.y},
                        "end": {"x": l.end.x, "y": l.end.y},
                        "layer": l.layer,
                        "metadata": meta(l.metadata),
                    } for l in v.lines],
                    "texts": [{
                        "content": t.content,
                        "position": {"x": t.position.x, "y": t.position.y},
                        "height": t.height, "layer": t.layer,
                        "metadata": meta(t.metadata),
                    } for t in v.texts],
                    "dimensions": [{
                        "p1": {"x": d.p1.x, "y": d.p1.y},
                        "p2": {"x": d.p2.x, "y": d.p2.y},
                        "label": d.label, "layer": d.layer,
                        "metadata": meta(d.metadata),
                    } for d in v.dimensions],
                    "leaders": [{
                        "start": {"x": l.start.x, "y": l.start.y},
                        "end": {"x": l.end.x, "y": l.end.y},
                        "text": l.text, "layer": l.layer,
                        "metadata": meta(l.metadata),
                    } for l in v.leaders],
                    "hatches": [{
                        "points": point_list(h.points), "pattern": h.pattern,
                        "scale": h.scale, "angle_deg": h.angle_deg,
                        "layer": h.layer,
                        "metadata": meta(h.metadata),
                    } for h in v.hatches],
                } for v in self.views
            ],
            "title_block": {
                "drawing_title": self.title_block.drawing_title,
                "project": self.title_block.project,
                "client": self.title_block.client,
                "scale": self.title_block.scale,
                "revision": self.title_block.revision,
                "designer": self.title_block.designer,
                "date": self.title_block.date,
                "material_notes": self.title_block.material_notes,
                "general_notes": self.title_block.general_notes,
            },
            "known_dimensions": self.known_dimensions,
            "estimated_components": self.estimated_components,
        }

    def set_entity_metadata(self, view_name: str, entity_type: str,
                            entity_index: int,
                            source: str, confidence: float,
                            evidence: Optional[List[str]] = None):
        """Set confidence metadata on a specific entity by view and index."""
        view = next((v for v in self.views if v.name == view_name), None)
        if not view:
            return

        entities = {
            "circle": view.circles,
            "polygon": view.polygons,
            "line": view.lines,
            "text": view.texts,
            "dimension": view.dimensions,
            "leader": view.leaders,
            "hatch": view.hatches,
        }.get(entity_type)

        if entities and 0 <= entity_index < len(entities):
            entities[entity_index].metadata = EntityMetadata(
                source=source,
                confidence=confidence,
                evidence=evidence or [],
            )

    def get_entity_metadata(self, view_name: str, entity_type: str,
                            entity_index: int) -> Optional[EntityMetadata]:
        """Get confidence metadata for a specific entity."""
        view = next((v for v in self.views if v.name == view_name), None)
        if not view:
            return None

        entities = {
            "circle": view.circles,
            "polygon": view.polygons,
            "line": view.lines,
            "text": view.texts,
            "dimension": view.dimensions,
            "leader": view.leaders,
            "hatch": view.hatches,
        }.get(entity_type)

        if entities and 0 <= entity_index < len(entities):
            return entities[entity_index].metadata
        return None

    @classmethod
    def from_dict(cls, data: dict) -> "DrawingModel":
        """Deserialize from JSON dict."""
        def to_point(d):
            return Point(x=d["x"], y=d["y"])

        def to_meta(d):
            if not d:
                return EntityMetadata()
            return EntityMetadata(
                source=d.get("source", "unknown"),
                confidence=d.get("confidence", 0.0),
                evidence=d.get("evidence", []),
            )

        views = []
        for vd in data.get("views", []):
            views.append(View(
                name=vd["name"],
                circles=[CircleComponent(
                    center=to_point(c["center"]),
                    radius=c["radius"], layer=c.get("layer", "OBJECT"),
                    metadata=to_meta(c.get("metadata")))
                    for c in vd.get("circles", [])],
                polygons=[PolygonComponent(
                    points=[to_point(p) for p in p["points"]],
                    layer=p.get("layer", "OBJECT"),
                    name=p.get("name", ""),
                    linetype=p.get("linetype", "CONTINUOUS"),
                    metadata=to_meta(p.get("metadata")))
                    for p in vd.get("polygons", [])],
                lines=[LineComponent(
                    start=to_point(l["start"]),
                    end=to_point(l["end"]),
                    layer=l.get("layer", "OBJECT"),
                    metadata=to_meta(l.get("metadata")))
                    for l in vd.get("lines", [])],
                texts=[TextComponent(
                    content=t["content"],
                    position=to_point(t["position"]),
                    height=t.get("height", 3),
                    layer=t.get("layer", "MTEXT"),
                    metadata=to_meta(t.get("metadata")))
                    for t in vd.get("texts", [])],
                dimensions=[DimensionComponent(
                    p1=to_point(d["p1"]),
                    p2=to_point(d["p2"]),
                    label=d["label"],
                    layer=d.get("layer", "DIMENSION"),
                    metadata=to_meta(d.get("metadata")))
                    for d in vd.get("dimensions", [])],
                leaders=[LeaderComponent(
                    start=to_point(l["start"]),
                    end=to_point(l["end"]),
                    text=l["text"],
                    layer=l.get("layer", "LEADER"),
                    metadata=to_meta(l.get("metadata")))
                    for l in vd.get("leaders", [])],
                hatches=[HatchComponent(
                    points=[to_point(p) for p in h["points"]],
                    pattern=h.get("pattern", "ANSI31"),
                    scale=h.get("scale", 0.3),
                    angle_deg=h.get("angle_deg", 45),
                    layer=h.get("layer", "HATCH"),
                    metadata=to_meta(h.get("metadata")))
                    for h in vd.get("hatches", [])],
            ))

        tb = data.get("title_block", {})
        return cls(
            furniture_type=data.get("furniture_type", ""),
            page_width=data.get("page_width", 420),
            page_height=data.get("page_height", 297),
            scale=data.get("scale", 0.5),
            views=views,
            title_block=TitleBlockData(
                drawing_title=tb.get("drawing_title", ""),
                project=tb.get("project", ""),
                client=tb.get("client", ""),
                scale=tb.get("scale", "1:1"),
                revision=tb.get("revision", "A"),
                designer=tb.get("designer", ""),
                date=tb.get("date", ""),
                material_notes=tb.get("material_notes", []),
                general_notes=tb.get("general_notes", []),
            ),
            known_dimensions=data.get("known_dimensions", {}),
            estimated_components=data.get("estimated_components", {}),
        )


# ===== Builder Functions =====
# (re-added after refactoring — called by routes.py and svg_exporter.py)

def build_round_pedestal_model(
    top_dia_cm: float = 80.0,
    height_cm: float = 70.0,
    base_dia_cm: float | None = None,
    neck_dia_cm: float | None = None,
    top_thick_cm: float = 4.0,
    collar_dia_cm: float | None = None,
) -> DrawingModel:
    """Build a DrawingModel for a round pedestal table."""
    model = DrawingModel(
        furniture_type="round_pedestal_table",
        scale=0.5,
        known_dimensions={
            "top_diameter_cm": top_dia_cm,
            "overall_height_cm": height_cm,
        },
        estimated_components={
            "pedestal_diameter_cm": base_dia_cm or top_dia_cm * 0.55,
            "neck_diameter_cm": neck_dia_cm or top_dia_cm * 0.28,
            "top_thickness_cm": top_thick_cm,
            "collar_diameter_cm": collar_dia_cm or top_dia_cm * 0.625,
        },
    )
    return model


def build_rectangular_table_model(
    width_cm: float = 120.0,
    depth_cm: float = 80.0,
    height_cm: float = 70.0,
    leg_thickness_cm: float = 6.0,
) -> DrawingModel:
    """Build a DrawingModel for a rectangular table."""
    model = DrawingModel(
        furniture_type="rectangular_table",
        scale=0.5,
        known_dimensions={
            "width_cm": width_cm,
            "depth_cm": depth_cm,
            "overall_height_cm": height_cm,
            "leg_thickness_cm": leg_thickness_cm,
        },
    )
    return model
