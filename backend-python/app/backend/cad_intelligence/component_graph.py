"""Component Graph Builder — groups detected CadEntity items into furniture components.

Uses spatial clustering + entity type + confidence to identify:
- Table: top, legs/pedestal, apron, hidden_frame
- Cabinet: case, doors, drawers, base
- Seating: seat, back, arms, base
- Bed: platform, headboard
"""
from __future__ import annotations
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from .models import CadEntity, DetectedLine, DetectedCircle, PipelineResult


class ComponentNode:
    """A detected furniture component with its child entities."""
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.entities: List[CadEntity] = []
        self.confidence: float = 0.0
        self.bbox: Optional[Tuple[float, float, float, float]] = None  # min_x, min_y, max_x, max_y
        self.dimensions_mm: Dict[str, float] = {}

    def add_entity(self, entity: CadEntity):
        self.entities.append(entity)
        self.confidence = max(self.confidence, entity.confidence)
        # Update bounding box
        geo = entity.geometry
        if entity.type == "line":
            sx, sy = geo.get("start", (0, 0))
            ex, ey = geo.get("end", (0, 0))
            pts = [(sx, sy), (ex, ey)]
        elif entity.type == "circle":
            cx, cy = geo.get("center", (0, 0))
            r = geo.get("radius", 0)
            pts = [(cx - r, cy - r), (cx + r, cy + r)]
        else:
            return
        for px, py in pts:
            if self.bbox is None:
                self.bbox = (px, py, px, py)
            else:
                self.bbox = (
                    min(self.bbox[0], px), min(self.bbox[1], py),
                    max(self.bbox[2], px), max(self.bbox[3], py),
                )

    def get_dimensions_mm(self) -> Dict[str, float]:
        """Estimate width/height/depth from bounding box."""
        if not self.bbox:
            return {}
        w = self.bbox[2] - self.bbox[0]
        h = self.bbox[3] - self.bbox[1]
        dims = {}
        if w > 0: dims["width_mm"] = round(w, 1)
        if h > 0: dims["height_mm"] = round(h, 1)
        return dims

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "entity_count": len(self.entities),
            "confidence": round(self.confidence, 3),
            "dimensions_mm": self.get_dimensions_mm(),
        }


class ComponentGraph:
    """Groups detected entities into furniture components."""
    
    def __init__(self, result: PipelineResult):
        self.result = result
        self.nodes: Dict[str, ComponentNode] = {}
        self._build()

    def _build(self):
        """Group entities by spatial proximity and type heuristics."""
        entities = self.result.entities
        lines = self.result.lines
        circles = self.result.circles

        # Layer-based grouping
        layer_groups: Dict[str, List[CadEntity]] = defaultdict(list)
        for e in entities:
            layer_groups[e.layer or "OBJECT"].append(e)

        # Build component nodes from layer groups
        component_map = {
            "OBJECT": self._detect_components_from_layer,
            "DIMENSIONS": None,
            "ANNOTATION": None,
            "UNKNOWN": None,
        }

        for layer, ents in layer_groups.items():
            if layer == "OBJECT" and ents:
                self._detect_components_from_layer(ents)
            elif layer == "DIMENSIONS":
                pass  # Skip — dimensions are not furniture components
            elif layer == "ANNOTATION":
                pass  # Skip
            elif layer == "UNKNOWN" and len(ents) > 3:
                # Unknown grouped entities — attempt clustering
                self._cluster_entities(ents, "unknown_component")

        # Generate names based on what we found
        self._label_components()

    def _detect_components_from_layer(self, entities: List[CadEntity]):
        """Heuristic detection of component roles from entities."""
        # Count horizontal vs vertical lines
        horiz_count = 0
        vert_count = 0
        circles_found = []
        for e in entities:
            if e.type == "line":
                angle = abs(e.geometry.get("angle_deg", 0)) % 180
                if angle < 30 or angle > 150:
                    horiz_count += 1
                elif 60 < angle < 120:
                    vert_count += 1
            elif e.type == "circle":
                circles_found.append(e)

        # If many horizontals + no circles = likely panel/rectangular
        if horiz_count > vert_count * 2 and horiz_count > 5:
            node = ComponentNode("horizontal_surface", "top")
            for e in entities:
                node.add_entity(e)
            self.nodes["top"] = node
        elif vert_count > horiz_count * 2 and vert_count > 5:
            node = ComponentNode("vertical_panel", "support")
            for e in entities:
                node.add_entity(e)
            self.nodes["support"] = node
        elif circles_found:
            # Has circles — likely round pedestal
            circle_node = ComponentNode("round_surface", "top")
            for c in circles_found:
                for e in entities:
                    if e.type == "circle":
                        circle_node.add_entity(e)
            self.nodes["top"] = circle_node
        else:
            # Mixed — cluster spatially
            self._cluster_entities(entities, "mixed_component")

    def _cluster_entities(self, entities: List[CadEntity], base_name: str):
        """Simple spatial clustering of entities into groups."""
        if not entities:
            return
        # Use a simple grid-based cluster: 200mm cells
        grid: Dict[Tuple[int, int], List[CadEntity]] = defaultdict(list)
        cell_size = 200.0
        for e in entities:
            geo = e.geometry
            cx, cy = 0.0, 0.0
            if e.type == "line":
                sx, sy = geo.get("start", (0, 0))
                ex, ey = geo.get("end", (0, 0))
                cx, cy = (sx + ex) / 2, (sy + ey) / 2
            elif e.type == "circle":
                cx, cy = geo.get("center", (0, 0))
            gx, gy = int(cx / cell_size), int(cy / cell_size)
            grid[(gx, gy)].append(e)

        for i, (_, ents) in enumerate(grid.items()):
            if len(ents) < 2:
                continue
            node = ComponentNode(f"{base_name}_{i}", "unknown")
            for e in ents:
                node.add_entity(e)
            self.nodes[f"{base_name}_{i}"] = node

    def _label_components(self):
        """Generate human-readable labels based on available nodes."""
        if "top" in self.nodes and "support" in self.nodes:
            self.nodes["top"].role = "top"
            self.nodes["support"].role = "support"
            self._name = "table_or_desk"
        elif "top" in self.nodes:
            self._name = "tabletop"
        else:
            self._name = "furniture"

    @property
    def name(self) -> str:
        return getattr(self, '_name', 'furniture')

    def summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "component_count": len(self.nodes),
            "components": {k: v.to_dict() for k, v in self.nodes.items()},
            "total_entities": sum(len(n.entities) for n in self.nodes.values()),
        }

    def to_agent_output(self) -> Dict[str, Any]:
        """Convert to dict for fusion pipeline AgentOutput."""
        return {
            "component_count": len(self.nodes),
            "components": [v.to_dict() for v in self.nodes.values()],
            "detected_name": self.name,
        }
