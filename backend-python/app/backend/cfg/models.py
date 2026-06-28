"""
Canonical Furniture Graph — shared data model for all pipeline stages.

Every module reads from and writes to this graph instead of passing
ad-hoc dicts. This is a PURE dataclass module with zero dependencies
on other app modules.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List, Tuple


@dataclass
class BBox:
    """Axis-aligned bounding box."""
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0

    @property
    def width(self) -> float:
        return abs(self.x2 - self.x1)

    @property
    def height(self) -> float:
        return abs(self.y2 - self.y1)

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0


@dataclass
class ComponentGeometry:
    """The geometric representation of a furniture component."""
    type: str = "polygon"          # "polygon" | "circle" | "arc"
    points: List[Tuple[float, float]] = field(default_factory=list)
    radius: Optional[float] = None
    start_angle: Optional[float] = None
    end_angle: Optional[float] = None
    bounding_box: BBox = field(default_factory=BBox)


@dataclass
class ComponentRelation:
    """Explicit geometric relationship between two components."""
    type: str = "PARENT_OF"        # PARENT_OF, ALIGNED_H, ALIGNED_V, SYMMETRIC, CENTERED, PARALLEL, EQUAL_SIZE
    target_id: str = ""
    axis: Optional[str] = None     # "x" | "y" | "center" | "center_x" | "center_y"
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentNode:
    """A named, typed furniture component with geometry."""
    id: str = ""
    name: str = ""                  # "tabletop", "leg_1", "backrest"
    component_type: str = ""        # "top", "support", "panel", "leg", "seat", "backrest", "arm", "door", "drawer", "shelf"
    view: str = ""                  # "top" | "front" | "side"
    geometry: ComponentGeometry = field(default_factory=ComponentGeometry)
    dimensions_mm: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    source: str = "schema_default"  # "measured" | "ocr" | "ratio" | "schema_default" | "user"
    relations: List[ComponentRelation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JointSpec:
    """A joinery specification connecting components."""
    type: str = ""                  # "mortise_tenon" | "dowel" | "screw" | "cam_lock" | "hidden_steel_frame"
    components: List[str] = field(default_factory=list)
    description: str = ""
    confidence: float = 0.0


@dataclass
class MaterialSpec:
    """Material specification for a component."""
    material: str = ""
    finish: Optional[str] = None
    thickness_mm: Optional[float] = None
    confidence: float = 0.0
    source: str = "schema_default"


@dataclass
class HardwareSpec:
    """Hardware specification."""
    type: str = ""                  # "screw" | "bracket" | "cam_lock" | "confirmat"
    quantity: int = 0
    size: str = ""
    components: List[str] = field(default_factory=list)


@dataclass
class BillOfMaterials:
    """Complete bill of materials."""
    entries: List[Dict[str, Any]] = field(default_factory=list)

    def add_entry(self, name: str, material: str, qty: int, dims_mm: Dict[str, float], notes: str = ""):
        self.entries.append({
            "name": name,
            "material": material,
            "qty": qty,
            "dimensions_mm": dims_mm,
            "notes": notes,
        })

    @property
    def total_entries(self) -> int:
        return len(self.entries)


@dataclass
class ScaleInfo:
    """Scale solution with confidence."""
    mm_per_px: Optional[float] = None
    confidence: float = 0.0
    samples: int = 0
    rejected: int = 0


@dataclass
class ProvenanceEntry:
    """Provenance tracking for a single field value."""
    source: str = ""               # "ai_vision" | "ocr" | "pixel_geometry" | "template_default" | "user"
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    agent: str = ""                # "vision_agent" | "dimension_agent" | "construction_agent" | etc.
    timestamp: str = ""


@dataclass
class CorrectionRecord:
    """A single user or auto-correction event."""
    field: str = ""
    old_value: Any = None
    new_value: Any = None
    timestamp: str = ""
    user_id: Optional[str] = None


@dataclass
class ViewSpec:
    """Specification for a generated view."""
    name: str = ""                 # "TOP VIEW", "FRONT VIEW", etc.
    type: str = "top"              # "top" | "front" | "side" | "section" | "exploded"

    _valid_types = {"top", "front", "side", "section", "exploded"}


@dataclass
class FurnitureGraph:
    """The canonical furniture graph — everything in one structure.

    Usage:
        cfg = FurnitureGraph(furniture_type="dining_table_rectangular_4_leg")
        cfg.add_component(ComponentNode(name="tabletop", ...))
        cfg.add_relation(ComponentRelation(type="CENTERED", target_id="leg_1", ...))
        drawing_model = cfg.to_drawing_model()  # for existing exporters
    """

    # === Identity ===
    graph_id: str = ""
    source: str = "upload"          # "upload" | "ai_vision" | "template" | "catalog" | "user_edit"
    furniture_type: str = ""
    furniture_family: str = ""      # "dining_table", "coffee_table", "sofa", etc.

    # === Measurement ===
    overall_dimensions: Dict[str, float] = field(default_factory=dict)
    scale: Optional[ScaleInfo] = None

    # === Component Hierarchy ===
    components: List[ComponentNode] = field(default_factory=list)
    relations: List[ComponentRelation] = field(default_factory=list)

    # === Manufacturing ===
    materials: Dict[str, MaterialSpec] = field(default_factory=dict)
    joinery: List[JointSpec] = field(default_factory=list)
    hardware: List[HardwareSpec] = field(default_factory=list)
    bom: Optional[BillOfMaterials] = None

    # === Engineering ===
    views: Dict[str, ViewSpec] = field(default_factory=dict)
    annotations: List[str] = field(default_factory=list)

    # === Provenance ===
    provenance: Dict[str, ProvenanceEntry] = field(default_factory=dict)
    corrections: List[CorrectionRecord] = field(default_factory=list)

    # === Learning ===
    confidence_map: Dict[str, float] = field(default_factory=dict)

    # === Metadata ===
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_component(self, component: ComponentNode):
        self.components.append(component)
        self.confidence_map[component.id or component.name] = component.confidence

    def add_relation(self, relation: ComponentRelation):
        self.relations.append(relation)

    def set_provenance(self, field: str, entry: ProvenanceEntry):
        self.provenance[field] = entry

    def add_correction(self, correction: CorrectionRecord):
        self.corrections.append(correction)

    def set_overall_dimension(self, key: str, value_mm: float):
        self.overall_dimensions[key] = value_mm

    def get_component(self, name: str) -> Optional[ComponentNode]:
        for c in self.components:
            if c.name == name or c.id == name:
                return c
        return None

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def average_confidence(self) -> float:
        if not self.confidence_map:
            return 0.0
        return sum(self.confidence_map.values()) / len(self.confidence_map)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict for API responses."""
        def _bbox(b: BBox) -> dict:
            return {"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2}

        def _geo(g: ComponentGeometry) -> dict:
            return {
                "type": g.type,
                "points": g.points,
                "radius": g.radius,
                "start_angle": g.start_angle,
                "end_angle": g.end_angle,
                "bounding_box": _bbox(g.bounding_box),
            }

        def _node(n: ComponentNode) -> dict:
            return {
                "id": n.id,
                "name": n.name,
                "component_type": n.component_type,
                "view": n.view,
                "geometry": _geo(n.geometry),
                "dimensions_mm": n.dimensions_mm,
                "confidence": round(n.confidence, 3),
                "source": n.source,
                "relations": [{"type": r.type, "target": r.target_id, "axis": r.axis, "confidence": round(r.confidence, 3)} for r in n.relations],
            }

        return {
            "graph_id": self.graph_id,
            "source": self.source,
            "furniture_type": self.furniture_type,
            "furniture_family": self.furniture_family,
            "overall_dimensions": self.overall_dimensions,
            "scale": {"mm_per_px": self.scale.mm_per_px, "confidence": round(self.scale.confidence, 3)} if self.scale else None,
            "components": [_node(c) for c in self.components],
            "relations": [{"type": r.type, "target": r.target_id, "axis": r.axis, "confidence": round(r.confidence, 3)} for r in self.relations],
            "materials": {k: {"material": v.material, "finish": v.finish, "confidence": round(v.confidence, 3)} for k, v in self.materials.items()},
            "joinery": [{"type": j.type, "components": j.components, "description": j.description} for j in self.joinery],
            "hardware": [{"type": h.type, "qty": h.quantity, "size": h.size} for h in self.hardware],
            "bom": self.bom.entries if self.bom else [],
            "views": {k: {"name": v.name, "type": v.type} for k, v in self.views.items()},
            "provenance": {k: {"source": v.source, "confidence": round(v.confidence, 3), "agent": v.agent, "evidence": v.evidence[:3]} for k, v in self.provenance.items()},
            "confidence_map": {k: round(v, 3) for k, v in self.confidence_map.items()},
            "component_count": self.component_count,
            "average_confidence": round(self.average_confidence, 3),
            "correction_count": len(self.corrections),
        }
