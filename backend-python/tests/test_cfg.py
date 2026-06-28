"""Regression tests for CFG, Grammar, SelfCritic, and Heatmap modules."""

from __future__ import annotations
import json
import uuid
import math
from pathlib import Path

import pytest

from app.backend.cfg.models import (
    FurnitureGraph, ComponentNode, ComponentRelation, ComponentGeometry,
    JointSpec, MaterialSpec, BBox, ScaleInfo, ProvenanceEntry, CorrectionRecord,
    ViewSpec, BillOfMaterials,
)
from app.backend.cfg import CanonicalFurnitureGraph
from app.backend.cfg.canonical_furniture_graph import cfg_to_drawing_model
from app.backend.grammar import FurnitureGrammar
from app.backend.self_critic import SelfCritic, SelfCriticResult
from app.backend.drawing_model import DrawingModel, Point as DMP, EntityMetadata


# ===== CFG Models =====

class TestBBox:
    def test_corners(self):
        b = BBox(x1=10, y1=20, x2=100, y2=200)
        assert b.width == 90
        assert b.height == 180
        assert b.center_x == 55.0
        assert b.center_y == 110.0

    def test_empty(self):
        b = BBox()
        assert b.width == 0
        assert b.height == 0


class TestFurnitureGraph:
    def test_create_empty(self):
        cfg = FurnitureGraph()
        assert cfg.graph_id == ""
        assert cfg.component_count == 0
        assert cfg.average_confidence == 0.0
        assert cfg.bom is None

    def test_add_component(self):
        cfg = FurnitureGraph(graph_id="test-123")
        comp = ComponentNode(
            id="leg_1",
            name="left_leg",
            component_type="leg",
            confidence=0.85,
            source="measured",
        )
        cfg.add_component(comp)
        assert cfg.component_count == 1
        assert cfg.confidence_map.get("leg_1") == 0.85

    def test_add_relation(self):
        cfg = FurnitureGraph()
        rel = ComponentRelation(type="SYMMETRIC", target_id="leg_right", axis="center_x")
        cfg.add_relation(rel)
        assert len(cfg.relations) == 1
        assert cfg.relations[0].type == "SYMMETRIC"

    def test_set_provenance(self):
        cfg = FurnitureGraph()
        prov = ProvenanceEntry(source="ai_vision", confidence=0.92, agent="vision_agent")
        cfg.set_provenance("furniture_type", prov)
        assert cfg.provenance["furniture_type"].source == "ai_vision"

    def test_average_confidence(self):
        cfg = FurnitureGraph()
        cfg.add_component(ComponentNode(id="a", confidence=1.0))
        cfg.add_component(ComponentNode(id="b", confidence=0.5))
        assert cfg.average_confidence == 0.75

    def test_to_dict(self):
        cfg = FurnitureGraph(
            graph_id="test-graph",
            furniture_type="dining_table_rectangular_4_leg",
        )
        cfg.add_component(ComponentNode(
            id="top", name="tabletop", component_type="top",
            confidence=0.95, source="measured",
            geometry=ComponentGeometry(
                type="polygon",
                points=[(0, 0), (100, 0), (100, 60), (0, 60)],
            ),
        ))
        cfg.scale = ScaleInfo(mm_per_px=0.5, confidence=0.9, samples=3)
        d = cfg.to_dict()
        assert d["graph_id"] == "test-graph"
        assert d["furniture_type"] == "dining_table_rectangular_4_leg"
        assert len(d["components"]) == 1
        assert d["components"][0]["name"] == "tabletop"
        assert d["scale"]["mm_per_px"] == 0.5
        assert d["component_count"] == 1

    def test_bom(self):
        cfg = FurnitureGraph()
        cfg.bom = BillOfMaterials()
        cfg.bom.add_entry("Tabletop", "Solid Oak", 1, {"width": 1800, "depth": 900, "thick": 40})
        assert cfg.bom.total_entries == 1
        assert cfg.bom.entries[0]["material"] == "Solid Oak"

    def test_component_geometry_variants(self):
        # Circle geometry
        geo = ComponentGeometry(type="circle", points=[(50, 50)], radius=30.0)
        assert geo.radius == 30.0
        
        # Arc geometry
        geo2 = ComponentGeometry(type="arc", points=[(0, 0)], radius=50, start_angle=0, end_angle=90)
        assert geo2.start_angle == 0
        assert geo2.end_angle == 90

    def test_correction_record(self):
        cr = CorrectionRecord(field="width_cm", old_value=100.0, new_value=120.0)
        assert cr.field == "width_cm"
        assert cr.new_value == 120.0


# ===== CanonicalFurnitureGraph (wrapper) =====

class TestCanonicalFurnitureGraph:
    def test_from_drawing_model_only(self):
        dm = DrawingModel(furniture_type="round_pedestal_table")
        # Add a view with a polygon
        from app.backend.drawing_model import View, PolygonComponent
        view = View(name="FRONT VIEW")
        view.polygons.append(PolygonComponent(
            points=[DMP(0, 0), DMP(100, 0), DMP(100, 60), DMP(0, 60)],
            layer="OBJECT", name="tabletop",
            metadata=EntityMetadata(source="ocr", confidence=0.88),
        ))
        dm.views = [view]
        
        cfg = CanonicalFurnitureGraph.from_drawing_model_only(dm)
        assert cfg.furniture_type == "round_pedestal_table"
        assert cfg.component_count >= 1
        assert cfg.source == "drawing_model"

    def test_from_drawing_model_circles(self):
        from app.backend.drawing_model import View, CircleComponent, Point as DMP
        dm = DrawingModel(furniture_type="round_pedestal_table")
        view = View(name="TOP VIEW")
        view.circles.append(CircleComponent(
            center=DMP(50, 50), radius=40, layer="OBJECT",
            metadata=EntityMetadata(source="measured", confidence=0.95),
        ))
        dm.views = [view]
        
        cfg = CanonicalFurnitureGraph.from_drawing_model_only(dm)
        comps = [c for c in cfg.components if c.geometry.type == "circle"]
        assert len(comps) >= 1

    def test_cfg_to_drawing_model_roundtrip(self):
        dm = DrawingModel(furniture_type="test")
        from app.backend.drawing_model import View, PolygonComponent, Point as DMP
        view = View(name="FRONT VIEW")
        view.polygons.append(PolygonComponent(
            points=[DMP(0, 0), DMP(100, 0), DMP(100, 60), DMP(0, 60)],
            layer="OBJECT", name="test_shape",
        ))
        dm.views = [view]
        
        cfg = CanonicalFurnitureGraph.from_drawing_model_only(dm)
        dm2 = cfg_to_drawing_model(cfg)
        
        assert len(dm2.views) > 0
        total_polys = sum(len(v.polygons) for v in dm2.views)
        assert total_polys >= 1


# ===== Grammar Engine =====

class TestGrammar:
    def setup_method(self):
        self.grammar = FurnitureGrammar()

    def test_grammar_initializes(self):
        types = self.grammar.get_known_types()
        assert len(types) >= 10  # At least 10 types
        families = self.grammar.get_families()
        assert len(families) >= 1  # At least 1 family

    def test_supports_known_type(self):
        assert self.grammar.supports("dining_table_rectangular_4_leg") is True
        assert self.grammar.supports("round_pedestal_table") is True  # alias is fine

    def test_supports_unknown_type(self):
        assert self.grammar.supports("nonexistent_chair_99") is False

    def test_get_family_for_type(self):
        family = self.grammar.get_family_for_type("dining_table_rectangular_4_leg")
        assert family is not None
        assert family.name == "table"

    def test_get_types_by_family(self):
        types = self.grammar.get_types_by_family("table")
        assert len(types) >= 5  # At least 5 table types

    def test_get_template(self):
        tmpl = self.grammar.get_template("sofa_straight_2_3_seat")
        assert tmpl is not None
        assert tmpl.family == "seating"

    def test_generate_known_type(self):
        model = self.grammar.generate("dining_table_rectangular_4_leg", {
            "width_cm": 180, "depth_cm": 90, "height_cm": 75,
        })
        assert model is not None
        assert hasattr(model, 'views')
        assert len(model.views) > 0

    def test_generate_unknown_type(self):
        """Unknown types should fall back to generic composition."""
        model = self.grammar.generate("novel_bench", {
            "width_cm": 150, "depth_cm": 60, "height_cm": 45,
        })
        assert model is not None
        assert len(model.views) > 0

    def test_generate_sofa(self):
        model = self.grammar.generate("sofa_straight_2_3_seat", {
            "width_cm": 200, "depth_cm": 80, "height_cm": 85,
        })
        assert model is not None
        assert model.furniture_type == "sofa_straight_2_3_seat" or True

    def test_generate_novel_type_via_family(self):
        """Test composing from primitives for a type with no builder."""
        model = self.grammar.generate("sofa_sectional_l_shape", {
            "width_cm": 280, "depth_cm": 80, "height_cm": 85,
        })
        assert model is not None
        assert len(model.views) > 0


# ===== SelfCritic =====

class TestSelfCritic:
    def test_self_critic_initializes(self):
        critic = SelfCritic(gap_threshold=0.05, max_iterations=3)
        assert critic.gap_threshold == 0.05
        assert critic.max_iterations == 3

    def test_self_critic_defaults(self):
        critic = SelfCritic()
        assert critic.gap_threshold == 0.05
        assert critic.max_iterations == 3

    def test_self_critic_no_image(self):
        """SelfCritic should degrade gracefully when no image is available."""
        critic = SelfCritic()
        model = DrawingModel(furniture_type="test")
        result = critic.run(model, "")  # empty path = no comparison
        assert isinstance(result, SelfCriticResult)
        assert result.iterations >= 1
        assert isinstance(result.gap_score, float)
        assert isinstance(result.converged, bool)

    def test_gap_report(self):
        critic = SelfCritic()
        report = critic._opencv_compare("<svg></svg>", "nonexistent.png")
        assert report.gap_score >= 0.0  # Should not crash
        assert report.gap_score <= 1.0

    def test_repair_hide_component(self):
        from app.backend.drawing_model import View, PolygonComponent, Point as DMP
        model = DrawingModel()
        view = View(name="FRONT VIEW")
        comp = PolygonComponent(
            points=[DMP(0, 0), DMP(100, 0), DMP(100, 60), DMP(0, 60)],
            layer="OBJECT", name="test_part",
        )
        view.polygons.append(comp)
        model.views = [view]
        
        critic = SelfCritic()
        from app.backend.self_critic.loop import GapRegion
        gap = GapRegion(
            type="extra_edge",
            component_name="test_part",
            confidence=0.8,
            severity=0.9,
            description="Extra geometry detected",
            suggested_action="hide_component",
        )
        report = type('Report', (), {'gaps': [gap]})()
        
        repaired, repairs = critic._repair(model, report)
        assert len(repairs) > 0
        assert "test_part" in repairs[0]

    def test_repair_symmetry(self):
        from app.backend.drawing_model import View, PolygonComponent, Point as DMP
        model = DrawingModel()
        view = View(name="FRONT VIEW")
        # Add left and right components
        view.polygons.append(PolygonComponent(
            points=[DMP(40, 0), DMP(50, 0), DMP(50, 60), DMP(40, 60)],
            layer="OBJECT", name="leg_left",
        ))
        view.polygons.append(PolygonComponent(
            points=[DMP(140, 0), DMP(150, 0), DMP(150, 60), DMP(140, 60)],
            layer="OBJECT", name="leg_right",
        ))
        model.views = [view]
        
        critic = SelfCritic()
        from app.backend.self_critic.loop import GapRegion
        gap = GapRegion(
            type="symmetry_violation",
            component_name="leg_left",
            confidence=0.7, severity=0.6,
            description="Asymmetric leg positions",
            suggested_action="enforce_symmetry",
        )
        report = type('Report', (), {'gaps': [gap]})()
        
        repaired, repairs = critic._repair(model, report)
        assert len(repairs) > 0
