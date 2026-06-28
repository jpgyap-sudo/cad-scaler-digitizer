"""
Furniture Engineering Agent
============================
Reverse-engineers furniture from product data and generates complete
engineering specifications for manufacturing CAD/DXF production.

Integrates with:
- crawl_to_dxf for dimension extraction
- dxf_exporter for template-based DXF generation
- template_graph for parametric engineering templates
- comparison_agent for validation feedback
"""

import os
import json
import logging
import math
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger("engineering_agent")

# ---------------------------------------------------------------------------
# Knowledge Bases
# ---------------------------------------------------------------------------

# Standard material thicknesses by type (mm)
MATERIAL_THICKNESS = {
    "solid_wood": {"top": [25, 30, 38, 45], "leg": [40, 50, 60, 70], "apron": [18, 22, 25], "shelf": [18, 22, 25]},
    "plywood": {"top": [18, 22, 25, 30], "leg": [30, 40], "apron": [15, 18, 22], "shelf": [15, 18, 22, 25]},
    "mdf": {"top": [18, 22, 25, 30, 40], "leg": [30, 40], "apron": [15, 18], "shelf": [15, 18, 22]},
    "metal": {"frame": [2, 3, 4, 5, 6], "leg": [1.5, 2, 2.5, 3], "bracket": [3, 4, 5]},
    "glass": {"top": [6, 8, 10, 12, 15], "shelf": [6, 8, 10]},
    "stone": {"top": [12, 15, 20, 25, 30]},
}

# Joinery standards by material and joint type
JOINERY_STANDARDS = {
    "solid_wood": {
        "mortise_tenon": {"depth_min": 20, "depth_max": 40, "tenon_thickness": [6, 8, 10, 12]},
        "dowel": {"diameter": [6, 8, 10, 12], "depth": [25, 30, 35, 40], "spacing": [60, 80, 100]},
        "pocket_screw": {"screw_size": [4, 5], "spacing": [100, 150, 200]},
    },
    "plywood": {
        "dowel": {"diameter": [6, 8, 10], "depth": [20, 25, 30], "spacing": [80, 100, 120]},
        "confirmat": {"diameter": [5, 7], "length": [35, 40, 50, 55]},
        "cam_lock": {"diameter": [15, 18], "depth": [12, 15]},
    },
    "metal": {
        "weld": {"fillet_size": [3, 4, 5, 6], "prep": ["bevel", "square"]},
        "threaded_insert": {"diameter": [6, 8, 10], "length": [12, 15]},
    },
}

# Ergonomics standards by furniture type
ERGONOMICS = {
    "sofa": {"seat_height": (40, 48), "seat_depth": (50, 65), "arm_height": (20, 28), "back_height": (50, 70)},
    "dining_chair": {"seat_height": (43, 48), "seat_depth": (38, 45), "back_height": (35, 50), "arm_height": (50, 65)},
    "dining_table": {"height": (72, 78), "knee_clearance": (60, 68), "overhang": (20, 30)},
    "coffee_table": {"height": (35, 50), "overhang": (15, 25)},
    "desk": {"height": (72, 76), "knee_clearance": (60, 68), "depth": (60, 80)},
    "bed": {"height": (35, 50), "mattress_thickness": (15, 30)},
    "cabinet": {"base_height": (85, 90), "counter_depth": (55, 65)},
}

# Furniture classification hierarchy
FURNITURE_FAMILIES = {
    "seating": {
        "sofa": {"subtypes": ["2-seater", "3-seater", "L-sectional", "chaise"], "key_dims": ["width", "depth", "height", "seat_height", "arm_height"]},
        "dining_chair": {"subtypes": ["side", "arm", "carver"], "key_dims": ["width", "depth", "height", "seat_height"]},
        "armchair": {"subtypes": ["club", "wing", "slipper", "accent"], "key_dims": ["width", "depth", "height", "seat_height", "arm_height"]},
        "lounge_chair": {"subtypes": ["chaise", "recliner", "egg"], "key_dims": ["width", "depth", "height", "seat_height", "recline"]},
        "stool": {"subtypes": ["bar", "counter", "step"], "key_dims": ["width", "depth", "height", "seat_height"]},
        "bench": {"subtypes": ["dining", "storage", "garden"], "key_dims": ["width", "depth", "height", "seat_height"]},
        "ottoman": {"subtypes": ["cube", "rectangular", "round"], "key_dims": ["width", "depth", "height"]},
    },
    "tables": {
        "dining_table": {"subtypes": ["rectangular", "round", "oval", "square", "extendable"], "key_dims": ["width", "depth", "height", "top_thickness"]},
        "coffee_table": {"subtypes": ["rectangular", "round", "nested", "lift-top"], "key_dims": ["width", "depth", "height", "top_thickness"]},
        "side_table": {"subtypes": ["end", "lamp", "c-table"], "key_dims": ["width", "depth", "height"]},
        "console_table": {"subtypes": ["straight", "curved", "with-drawers"], "key_dims": ["width", "depth", "height"]},
        "desk": {"subtypes": ["writing", "computer", "standing", "corner"], "key_dims": ["width", "depth", "height"]},
    },
    "storage": {
        "cabinet": {"subtypes": ["base", "wall", "tall", "display"], "key_dims": ["width", "depth", "height", "shelf_count"]},
        "wardrobe": {"subtypes": ["sliding", "hinged", "walk-in"], "key_dims": ["width", "depth", "height", "hanging_height"]},
        "bookcase": {"subtypes": ["standard", "leaning", "ladder"], "key_dims": ["width", "depth", "height", "shelf_thickness"]},
        "nightstand": {"subtypes": ["single", "drawer", "shelf"], "key_dims": ["width", "depth", "height"]},
    },
    "beds": {
        "bed": {"subtypes": ["platform", "sleigh", "panel", "storage"], "key_dims": ["width", "length", "height", "headboard_height"]},
        "headboard": {"subtypes": ["flat", "tufted", "slat", "panel"], "key_dims": ["width", "height", "thickness"]},
    },
    "workspace": {
        "office_desk": {"subtypes": ["executive", "standing", "corner"], "key_dims": ["width", "depth", "height", "thickness"]},
        "reception_desk": {"subtypes": ["straight", "L-shape", "curved"], "key_dims": ["width", "depth", "height", "counter_depth"]},
    },
    "outdoor": {
        "outdoor_dining": {"subtypes": ["table", "chair", "bench"], "key_dims": ["width", "depth", "height"]},
        "outdoor_lounger": {"subtypes": ["fixed", "adjustable", "folding"], "key_dims": ["width", "length", "height"]},
    },
}

# ---------- Component templates ----------
COMPONENT_TEMPLATES = {
    "rectangular_table": [
        {"name": "table_top", "type": "panel", "material_default": "solid_wood", "thickness_min": 25, "thickness_max": 45},
        {"name": "apron_front", "type": "panel", "material_default": "solid_wood", "thickness_min": 18, "thickness_max": 25},
        {"name": "apron_back", "type": "panel", "material_default": "solid_wood", "thickness_min": 18, "thickness_max": 25},
        {"name": "apron_left", "type": "panel", "material_default": "solid_wood", "thickness_min": 18, "thickness_max": 25},
        {"name": "apron_right", "type": "panel", "material_default": "solid_wood", "thickness_min": 18, "thickness_max": 25},
        {"name": "legs", "type": "leg_set", "count": 4, "material_default": "solid_wood", "section_min": 40, "section_max": 70},
        {"name": "corner_brackets", "type": "hardware", "count": 4, "material_default": "metal"},
        {"name": "cross_stretchers", "type": "rail", "count": 2, "material_default": "solid_wood", "section_min": 20, "section_max": 30},
        {"name": "adjustable_feet", "type": "hardware", "count": 4, "material_default": "plastic"},
    ],
    "upholstered_sofa": [
        {"name": "frame_front", "type": "panel", "material_default": "plywood", "thickness_min": 15, "thickness_max": 22},
        {"name": "frame_back", "type": "panel", "material_default": "plywood", "thickness_min": 15, "thickness_max": 22},
        {"name": "frame_sides", "type": "panel", "count": 2, "material_default": "plywood", "thickness_min": 15, "thickness_max": 22},
        {"name": "seat_platform", "type": "panel", "material_default": "plywood", "thickness_min": 12, "thickness_max": 18},
        {"name": "sinuous_springs", "type": "suspension", "count": 8, "material_default": "metal"},
        {"name": "seat_cushion", "type": "cushion", "count": 2, "material_default": "foam", "thickness_min": 100, "thickness_max": 150},
        {"name": "back_cushion", "type": "cushion", "count": 3, "material_default": "foam", "thickness_min": 80, "thickness_max": 120},
        {"name": "fabric_cover", "type": "upholstery", "material_default": "fabric"},
        {"name": "legs", "type": "leg_set", "count": 4, "material_default": "metal", "section_min": 20, "section_max": 30},
    ],
}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ComponentAnalysis:
    name: str
    quantity: int
    material: str
    dimensions_mm: dict  # {width, depth, height, thickness, etc}
    joinery: list  # [{type: str, description: str, probability: float}]
    confidence: float

@dataclass
class EngineeringAnalysis:
    product_id: str
    furniture_type: str
    furniture_subtype: str
    family: str
    overall_dims: dict  # {width_cm, depth_cm, height_cm}
    dimensions_confidence: float
    materials: dict  # {component: {material, confidence}}
    components: list[dict]
    joinery: list[dict]
    structural_notes: list[str]
    manufacturing_notes: list[str]
    bom: list[dict]  # Bill of Materials
    hardware: list[dict]
    layers: list[str]
    confidence_scores: dict
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "furniture_type": self.furniture_type,
            "furniture_subtype": self.furniture_subtype,
            "family": self.family,
            "overall_dimensions": self.overall_dims,
            "dimensions_confidence": self.dimensions_confidence,
            "materials": self.materials,
            "components": self.components,
            "joinery": self.joinery,
            "structural_notes": self.structural_notes,
            "manufacturing_notes": self.manufacturing_notes,
            "bill_of_materials": self.bom,
            "hardware": self.hardware,
            "recommended_layers": self.layers,
            "confidence_scores": self.confidence_scores,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Analysis Engine
# ---------------------------------------------------------------------------

def classify_furniture(furniture_type: str, dimensions: dict = None) -> dict:
    """Classify furniture into family, type, subtype based on name/dims."""
    ft_lower = furniture_type.lower().replace("_", " ").replace("-", " ")

    # Find the matching family and type
    for family, types in FURNITURE_FAMILIES.items():
        for ftype, info in types.items():
            if ftype.replace("_", " ") in ft_lower or ft_lower in ftype.replace("_", " "):
                return {"family": family, "type": ftype, "subtypes": info["subtypes"], "key_dims": info["key_dims"]}

    # Heuristic from dimensions
    if dimensions:
        w = dimensions.get("width_cm", 0)
        d = dimensions.get("depth_cm", 0) or dimensions.get("length_cm", 0)
        h = dimensions.get("overall_height_cm", 0) or dimensions.get("height_cm", 0)

        if w > 150 and d > 70 and 70 < h < 100:
            return {"family": "tables", "type": "dining_table", "subtypes": ["rectangular"], "key_dims": ["width", "depth", "height", "top_thickness"]}
        if w > 120 and d > 70 and 40 < h < 55:
            return {"family": "tables", "type": "coffee_table", "subtypes": ["rectangular"], "key_dims": ["width", "depth", "height"]}
        if w > 100 and d > 70 and 70 < h < 90:
            return {"family": "seating", "type": "sofa", "subtypes": ["3-seater"], "key_dims": ["width", "depth", "height", "seat_height", "arm_height"]}

    return {"family": "furniture", "type": furniture_type, "subtypes": ["standard"], "key_dims": ["width", "depth", "height"]}


def estimate_dimensions(furniture_type: str, page_dims: dict = None) -> dict:
    """Estimate overall dimensions using ergonomic standards + page data."""
    result = {}
    classification = classify_furniture(furniture_type, page_dims)

    if page_dims:
        for k, v in page_dims.items():
            if v and v > 0:
                result[k] = round(float(v), 1)

    # Fill missing from ergonomics
    ergo = ERGONOMICS.get(classification["type"], {})
    if "height" not in result and ergo.get("height"):
        result["height_cm"] = round(sum(ergo["height"]) / 2, 1)
    if "seat_height" not in result and ergo.get("seat_height"):
        result["seat_height_cm"] = round(sum(ergo["seat_height"]) / 2, 1)
    if "seat_depth" not in result and ergo.get("seat_depth"):
        result["seat_depth_cm"] = round(sum(ergo["seat_depth"]) / 2, 1)
    if "overhang" not in result and ergo.get("overhang"):
        result["overhang_cm"] = round(sum(ergo["overhang"]) / 2, 1)

    return result


def estimate_materials(furniture_type: str, family: str) -> list:
    """Estimate likely construction materials based on furniture type."""
    suggestions = []

    if family in ("tables", "beds", "storage"):
        suggestions.append({"component": "primary_structure", "material": "Solid Oak", "confidence": 80, "alternatives": ["Ash", "Walnut", "Beech"]})
        suggestions.append({"component": "secondary_panels", "material": "Plywood 18mm", "confidence": 75, "alternatives": ["MDF", "Particle Board"]})
        if "table" in furniture_type or "desk" in furniture_type:
            suggestions.append({"component": "top_surface", "material": "Solid Walnut", "confidence": 85, "alternatives": ["Oak Veneer MDF", "Marble", "Tempered Glass"]})
    elif family in ("seating",):
        suggestions.append({"component": "frame", "material": "Plywood 15mm + Solid Hardwood", "confidence": 85, "alternatives": ["Solid Beech", "Steel Frame"]})
        suggestions.append({"component": "cushion", "material": "High-density foam + poly fiber", "confidence": 80, "alternatives": ["Memory foam", "Down feather"]})
        suggestions.append({"component": "upholstery", "material": "Polyester fabric", "confidence": 75, "alternatives": ["Leather", "Velvet", "Linen"]})

    return suggestions


def estimate_joinery(furniture_type: str, family: str, materials: list) -> list:
    """Estimate joinery methods from furniture type and materials."""
    joints = []

    if family in ("tables", "beds"):
        joints.append({"type": "mortise_and_tenon", "components": "apron_to_leg", "probability": 85, "description": "Haunched mortise and tenon, 12mm tenon, 30mm depth"})
        joints.append({"type": "dowel", "components": "apron_to_leg", "probability": 70, "description": "8mm dowels, 4 per joint, 30mm depth"})
        joints.append({"type": "pocket_screw", "components": "stretcher_to_leg", "probability": 60, "description": "No. 8 x 2.5mm pocket screws"})
    elif family in ("storage",):
        joints.append({"type": "dowel", "components": "panel_to_panel", "probability": 80, "description": "8mm dowels at 100mm spacing"})
        joints.append({"type": "cam_lock", "components": "knock_down_fittings", "probability": 75, "description": "15mm cam lock + 7mm confirmat screw"})
    elif family in ("seating",):
        joints.append({"type": "dowel", "components": "frame_joints", "probability": 85, "description": "10mm dowels, glued and screwed"})
        joints.append({"type": "screw_and_glue", "components": "panel_to_panel", "probability": 80, "description": "4.5 x 40mm screws + PVA glue"})

    return joints


def generate_bom(components: list, materials: list, dimensions: dict) -> list:
    """Generate Bill of Materials from components and dimensions."""
    bom = []
    for comp in components[:6]:
        w = dimensions.get("width_cm", 100)
        d = dimensions.get("depth_cm", 80) or dimensions.get("length_cm", 80)
        h = dimensions.get("overall_height_cm", 75) or dimensions.get("height_cm", 75)

        mat = comp.get("material_default", "solid_wood")
        thickness = comp.get("thickness_min", 18)
        count = comp.get("count", 1)
        part_w = w - 4
        part_d = d - 4

        bom.append({
            "component": comp["name"],
            "quantity": count,
            "material": mat,
            "size_mm": f"{int(part_w * 10)} x {int(part_d * 10)} x {thickness}mm",
            "notes": "",
        })

    # Basic hardware
    bom.append({"component": "screws", "quantity": 20, "material": "steel", "size_mm": "4.5 x 50mm", "notes": "Countersunk"})
    bom.append({"component": "wood_glue", "quantity": 1, "material": "PVA", "size_mm": "250ml", "notes": "Titebond II or equivalent"})

    return bom


def generate_layers(furniture_type: str) -> list:
    """Generate CAD layer recommendations."""
    return [
        {"name": "OUTLINE", "color": 7, "description": "Visible edges and outlines"},
        {"name": "HIDDEN", "color": 2, "description": "Hidden lines behind visible surfaces"},
        {"name": "CENTER", "color": 3, "description": "Centerlines for symmetry"},
        {"name": "DIMENSIONS", "color": 4, "description": "Dimension lines and text"},
        {"name": "TEXT", "color": 7, "description": "Annotations and notes"},
        {"name": "HATCH", "color": 8, "description": "Section hatch patterns"},
        {"name": "WOOD", "color": 6, "description": "Wood grain direction indicators"},
        {"name": "HARDWARE", "color": 5, "description": "Hardware and fasteners"},
        {"name": "SECTION", "color": 3, "description": "Section cutting plane lines"},
        {"name": "REFERENCE", "color": 9, "description": "Reference geometry"},
    ]


def analyze_product(
    product_id: str,
    furniture_type: str,
    page_dimensions: dict = None,
    detected_dimensions: dict = None,
) -> EngineeringAnalysis:
    """Full engineering analysis of a furniture product."""
    classification = classify_furniture(furniture_type, page_dimensions)
    dims = estimate_dimensions(furniture_type, page_dimensions)

    # Merge detected dimensions
    if detected_dimensions:
        for k, v in detected_dimensions.items():
            if v and v > 0:
                dims[k] = round(float(v), 1)

    materials = estimate_materials(classification["type"], classification["family"])
    joinery = estimate_joinery(classification["type"], classification["family"], materials)

    # Get component template
    template_key = classification["type"]
    components = COMPONENT_TEMPLATES.get(template_key, [])
    if not components:
        # Fallback: generate basic components from classification
        components = [{"name": "primary_body", "type": "assembly", "material_default": "solid_wood", "thickness_min": 18, "thickness_max": 25}]

    bom = generate_bom(components, materials, dims)
    layers = generate_layers(furniture_type)

    # Structural notes
    structural = []
    if "dining_table" in classification["type"] or "table" in furniture_type:
        structural.append("Primary load path: tabletop → apron → legs → floor")
        structural.append("Side-to-side stability provided by cross stretchers")
        structural.append("Corner brackets reinforce apron-to-leg joints")
    elif "sofa" in classification["type"] or "chair" in furniture_type:
        structural.append("Primary load path: seat → frame → legs → floor")
        structural.append("Sinuous springs provide suspension across seat width")
        structural.append("Corner blocks reinforce all frame joints")

    # Manufacturing notes
    manufacturing = []
    manufacturing.append("All exposed edges to be sanded to 220 grit before finishing")
    manufacturing.append("Apply clear polyurethane finish, 3 coats with light sanding between coats")
    manufacturing.append("Assembly order: frame → surface prep → finish → final assembly → hardware")
    manufacturing.append("Allow 24h glue cure time before stress testing")

    # Confidence scores
    has_page_dims = bool(page_dimensions and any(v for v in page_dimensions.values() if v))
    has_detected_dims = bool(detected_dimensions and any(v for v in detected_dimensions.values() if v))

    confidence = {
        "overall_dimensions": 85 if has_page_dims else 70,
        "materials": 80,
        "joinery": 75,
        "structural_analysis": 80,
        "manufacturing_process": 85,
        "component_breakdown": 80,
    }
    if has_page_dims:
        confidence["overall_dimensions"] = 95

    return EngineeringAnalysis(
        product_id=product_id,
        furniture_type=classification["type"],
        furniture_subtype=classification.get("subtypes", ["standard"])[0],
        family=classification["family"],
        overall_dims=dims,
        dimensions_confidence=confidence["overall_dimensions"] / 100,
        materials=materials,
        components=[asdict(c) if hasattr(c, '__dataclass_fields__') else c for c in components],
        joinery=joinery,
        structural_notes=structural,
        manufacturing_notes=manufacturing,
        bom=bom,
        hardware=[{"name": "screws", "type": "confirmat", "size": "7x50mm", "quantity": 16}],
        layers=[l["name"] for l in layers],
        confidence_scores=confidence,
        created_at=datetime.utcnow().isoformat(),
    )


def persist_analysis(analysis: EngineeringAnalysis) -> bool:
    """Store analysis in Postgres knowledge base."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO engineering_analyses (product_id, furniture_type, furniture_subtype, family,
                overall_dims_json, materials_json, components_json, joinery_json, bom_json,
                confidence_scores_json, analysis_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (product_id) DO UPDATE SET
                furniture_type = EXCLUDED.furniture_type,
                materials_json = EXCLUDED.materials_json,
                confidence_scores_json = EXCLUDED.confidence_scores_json,
                updated_at = NOW()
        """, (
            analysis.product_id, analysis.furniture_type, analysis.furniture_subtype, analysis.family,
            json.dumps(analysis.overall_dims),
            json.dumps(analysis.materials),
            json.dumps(analysis.components),
            json.dumps(analysis.joinery),
            json.dumps(analysis.bom),
            json.dumps(analysis.confidence_scores),
            json.dumps(analysis.to_dict()),
        ))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Failed to persist engineering analysis: {e}")
        return False
