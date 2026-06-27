from pathlib import Path
import json
import uuid

from app.productionization.models import Artifact
from app.productionization.config import settings


class VisionAdapter:
    def run(self, request):
        product_type = request.product_type_hint or "dining_table"
        return {
            "product_type": product_type,
            "subtype": "dual cylindrical pedestal table" if product_type == "dining_table" else None,
            "top_shape": "rectangular",
            "support_type": "dual_cylindrical_pedestal" if product_type == "dining_table" else None,
            "material_top": request.material_hints.get("top", "white_stone"),
            "material_base": request.material_hints.get("base", "matte_black_metal"),
            "visible_parts": ["top", "support/base"],
            "style_keywords": ["modern", "minimalist"],
            "approximate_dimensions_mm": request.known_dimensions_mm,
            "confidence": 0.82,
        }


class RetrievalAdapter:
    def run(self, vision):
        return {
            "hits": [
                {
                    "id": "template.table.dual_cylindrical_pedestal.v1",
                    "score": 0.88,
                    "title": "Dual cylindrical pedestal table reference",
                }
            ],
            "resource_ids": [
                "geometry.table.rectangular_top",
                "support.table.dual_cylindrical_pedestal",
                "joinery.hidden_steel_frame",
            ],
        }


class EngineeringAdapter:
    def run(self, vision, retrieval, request):
        dims = {
            "length_mm": 1800,
            "depth_mm": 900,
            "height_mm": 750,
            "top_thickness_mm": 30,
            "large_pedestal_diameter_mm": 420,
            "small_pedestal_diameter_mm": 220,
        }
        dims.update(request.known_dimensions_mm or {})

        return {
            "product_type": vision["product_type"],
            "template_id": "table.dual_cylindrical_pedestal.v1",
            "canonical_parameters": dims,
            "materials": {
                "top": vision.get("material_top", "white_stone"),
                "base": vision.get("material_base", "matte_black_metal"),
            },
            "joinery": {"hidden_steel_frame": True},
            "hardware": [{"item": "M8 bolts", "qty": 8}, {"item": "leveling glides", "qty": 4}],
            "drawing_notes": [
                "TOP: STONE / MARBLE / SINTERED STONE AS SPECIFIED.",
                "BASE: MATTE BLACK METAL.",
                "PROVIDE HIDDEN STEEL FRAME UNDER TOP.",
            ],
            "confidence": 0.86,
        }


class TemplateGraphAdapter:
    def run(self, engineering):
        p = engineering["canonical_parameters"]
        return {
            "product_type": engineering["product_type"],
            "template_id": engineering["template_id"],
            "nodes": [
                {
                    "id": "top",
                    "role": "top",
                    "shape": "rectangular_slab",
                    "parameters": {
                        "length_mm": p["length_mm"],
                        "depth_mm": p["depth_mm"],
                        "thickness_mm": p["top_thickness_mm"],
                    },
                    "material_role": "top",
                },
                {
                    "id": "large_pedestal",
                    "role": "support",
                    "shape": "cylinder",
                    "parameters": {
                        "diameter_mm": p["large_pedestal_diameter_mm"],
                        "height_mm": p["height_mm"] - p["top_thickness_mm"],
                        "x_mm": -420,
                        "y_mm": 0,
                    },
                    "material_role": "base",
                },
                {
                    "id": "small_pedestal",
                    "role": "support",
                    "shape": "cylinder",
                    "parameters": {
                        "diameter_mm": p["small_pedestal_diameter_mm"],
                        "height_mm": p["height_mm"] - p["top_thickness_mm"],
                        "x_mm": 420,
                        "y_mm": 0,
                    },
                    "material_role": "base",
                },
                {
                    "id": "hidden_frame",
                    "role": "joinery",
                    "shape": "rectangular_steel_frame",
                    "parameters": {
                        "length_mm": p["length_mm"] - 240,
                        "depth_mm": p["depth_mm"] - 240,
                    },
                    "material_role": "steel",
                    "visible": False,
                },
            ],
            "annotations": engineering["drawing_notes"],
            "confidence": engineering["confidence"],
        }


class DrawingEngineAdapter:
    def run(self, case_id: str, scene_graph: dict, engineering: dict):
        import ezdxf
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A3

        out_dir = settings.output_dir / case_id
        out_dir.mkdir(parents=True, exist_ok=True)

        dxf_path = out_dir / "shopdrawing.dxf"
        pdf_path = out_dir / "shopdrawing.pdf"
        scene_path = out_dir / "scene_graph.json"
        engineering_path = out_dir / "engineering_decision.json"

        scene_path.write_text(json.dumps(scene_graph, indent=2), encoding="utf-8")
        engineering_path.write_text(json.dumps(engineering, indent=2), encoding="utf-8")

        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        for layer in ["TOP", "BASE", "HIDDEN", "TEXT", "DIMENSIONS"]:
            if layer not in doc.layers:
                doc.layers.new(layer)

        p = engineering["canonical_parameters"]
        L, D, H, T = p["length_mm"], p["depth_mm"], p["height_mm"], p["top_thickness_mm"]

        # top view
        msp.add_lwpolyline([(-L/2,-D/2),(L/2,-D/2),(L/2,D/2),(-L/2,D/2)], close=True, dxfattribs={"layer": "TOP"})
        msp.add_circle((-420,0), p["large_pedestal_diameter_mm"]/2, dxfattribs={"layer": "BASE"})
        msp.add_circle((420,0), p["small_pedestal_diameter_mm"]/2, dxfattribs={"layer": "BASE"})
        msp.add_lwpolyline([(-L/2+120,-D/2+120),(L/2-120,-D/2+120),(L/2-120,D/2-120),(-L/2+120,D/2-120)], close=True, dxfattribs={"layer": "HIDDEN"})
        msp.add_text("TOP VIEW", dxfattribs={"height": 45, "layer": "TEXT"}).set_placement((-L/2, D/2+100))

        # front elevation
        fy = -1500
        msp.add_lwpolyline([(-L/2,fy+H-T),(L/2,fy+H-T),(L/2,fy+H),(-L/2,fy+H)], close=True, dxfattribs={"layer":"TOP"})
        msp.add_lwpolyline([(-420-210,fy),(-420+210,fy),(-420+210,fy+H-T),(-420-210,fy+H-T)], close=True, dxfattribs={"layer":"BASE"})
        msp.add_lwpolyline([(420-110,fy),(420+110,fy),(420+110,fy+H-T),(420-110,fy+H-T)], close=True, dxfattribs={"layer":"BASE"})
        msp.add_text("FRONT ELEVATION", dxfattribs={"height": 45, "layer": "TEXT"}).set_placement((-L/2, fy+H+100))
        msp.add_text(f"OVERALL: {L}L x {D}D x {H}H MM", dxfattribs={"height": 35, "layer": "TEXT"}).set_placement((-L/2, fy-160))
        msp.add_text("PROVIDE HIDDEN STEEL FRAME UNDER STONE TOP", dxfattribs={"height": 30, "layer": "TEXT"}).set_placement((-L/2, fy-230))

        doc.saveas(str(dxf_path))

        c = canvas.Canvas(str(pdf_path), pagesize=A3)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, 800, "HOMEU SHOP DRAWING")
        c.setFont("Helvetica", 10)
        c.drawString(40, 780, f"Product: {engineering['product_type']}")
        c.drawString(40, 760, f"Template: {engineering['template_id']}")
        c.drawString(40, 740, f"Overall: {L}L x {D}D x {H}H mm")
        c.rect(40, 500, 300, 160)
        c.drawString(50, 645, "TOP VIEW PLACEHOLDER")
        c.rect(40, 260, 300, 160)
        c.drawString(50, 405, "FRONT ELEVATION PLACEHOLDER")
        c.save()

        return [
            Artifact(artifact_type="dxf", path=str(dxf_path)),
            Artifact(artifact_type="pdf", path=str(pdf_path)),
            Artifact(artifact_type="scene_graph", path=str(scene_path)),
            Artifact(artifact_type="engineering_decision", path=str(engineering_path)),
        ]


class QualityAdapter:
    def run(self, artifacts, engineering):
        warnings = []
        score = 0.88
        params = engineering["canonical_parameters"]
        if params.get("height_mm", 0) < 720 or params.get("height_mm", 0) > 780:
            warnings.append("Dining table height outside normal range.")
            score -= 0.12
        if not any(a.artifact_type == "dxf" for a in artifacts):
            warnings.append("No DXF generated.")
            score -= 0.3
        return {"score": max(0, min(1, score)), "passed": score >= 0.8, "issues": warnings}
