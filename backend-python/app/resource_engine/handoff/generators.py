"""Generators — BOM, cutting list, schedules, drawing notes, handoff manifest."""
from typing import List, Dict, Any
from .models import (
    EngineeringDecisionPackage, ParametricCADSceneGraph, CADSceneNode,
    BOMLine, CuttingLine, ScheduleLine, DrawingNotes, CADHandoffManifest,
)


class BOMGenerator:
    def generate(self, package: EngineeringDecisionPackage, scene: ParametricCADSceneGraph) -> List[BOMLine]:
        lines = []; p = package.canonical_parameters; pt = package.product_type
        if pt in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table",
                  "rectangular_table","console_table","coffee_table","side_table","round_pedestal_table"):
            L, D, T = p.get("length_mm",1800), p.get("depth_mm",900), p.get("top_thickness_mm",30)
            lines.append(BOMLine(line_no=1, item_code="TOP-001", description=f"Table top {L}x{D}mm", qty=1, unit="pc",
                material=package.materials.get("top_material","stone"), finish="honed/polished"))
            lines.append(BOMLine(line_no=2, item_code="BASE-001", description="Pedestal base set (2 cylinders)", qty=1, unit="set",
                material=package.materials.get("base_material","brushed metal")))
        elif pt == "sofa":
            lines.append(BOMLine(line_no=1, item_code="UPH-001", description="Upholstered body", qty=1, unit="pc", material="fabric"))
        elif pt in ("sideboard","cabinet","wardrobe","nightstand","tv_console"):
            lines.append(BOMLine(line_no=1, item_code="CASE-001", description="Casework assembly", qty=1, unit="set", material="wood/MDF"))
        for i, hw in enumerate(package.hardware, len(lines)+1):
            if isinstance(hw, dict):
                lines.append(BOMLine(line_no=i, item_code=f"HW-{i:03d}", description=hw.get("item",""), qty=hw.get("qty",1), unit="pc"))
        return lines


class CuttingListGenerator:
    def generate(self, package: EngineeringDecisionPackage, scene: ParametricCADSceneGraph) -> List[CuttingLine]:
        lines = []; p = package.canonical_parameters; pt = package.product_type
        if pt in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table",
                  "rectangular_table","console_table","coffee_table","side_table","round_pedestal_table"):
            L, D, T = p.get("length_mm",1800), p.get("depth_mm",900), p.get("top_thickness_mm",30)
            lines.append(CuttingLine(part_id="TOP-01", description="Table top slab", qty=1, length_mm=float(L), width_mm=float(D), thickness_mm=float(T), material="stone"))
            ldia = p.get("large_pedestal_diameter_mm",420); sdia = p.get("small_pedestal_diameter_mm",220)
            ph = p.get("pedestal_height_mm",720)
            lines.append(CuttingLine(part_id="PED-L-01", description="Large pedestal column", qty=1, length_mm=float(ph), width_mm=float(ldia), material="steel"))
            lines.append(CuttingLine(part_id="PED-S-01", description="Small pedestal column", qty=1, length_mm=float(ph), width_mm=float(sdia), material="steel"))
        return lines


class ScheduleGenerator:
    def hardware(self, package: EngineeringDecisionPackage) -> List[ScheduleLine]:
        items = []
        for hw in package.hardware:
            if isinstance(hw, dict):
                items.append(ScheduleLine(item=hw.get("item",""), description=hw.get("purpose",""), qty=hw.get("qty",1)))
        if not items:
            items.append(ScheduleLine(item="M8 bolts", description="Mounting hardware", qty=8))
        return items

    def finish(self, package: EngineeringDecisionPackage, scene: ParametricCADSceneGraph) -> List[ScheduleLine]:
        items = []
        for n in scene.nodes:
            if n.material_role:
                items.append(ScheduleLine(item=n.material_role, description=f"Finish for {n.id}"))
        return items

    def fabrication(self, package: EngineeringDecisionPackage) -> List[ScheduleLine]:
        pt = package.product_type
        if pt in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table",
                  "rectangular_table","console_table","coffee_table"):
            return [ScheduleLine(item="metal_fab", description="Fabricate pedestal bases + hidden frame"),
                    ScheduleLine(item="stone_prep", description="Cut and polish stone top")]
        return []


class DrawingNotesGenerator:
    def generate(self, package: EngineeringDecisionPackage) -> DrawingNotes:
        material_notes = []
        for k, v in package.materials.items():
            material_notes.append(f"{k.upper()}: {v}")
        joinery_notes = []
        for k, v in package.joinery.items():
            joinery_notes.append(f"{k.upper()}: {v}")
        hard_notes = []
        for hw in package.hardware:
            if isinstance(hw, dict):
                hard_notes.append(f"{hw.get('qty',1)}x {hw.get('item','')} - {hw.get('purpose','')}")
        return DrawingNotes(
            general_notes=["ALL DIMENSIONS IN MM.","VERIFY ALL DIMENSIONS BEFORE PRODUCTION.","REFER TO ENG DRAWING FOR FABRICATION DETAILS."],
            material_notes=material_notes,
            fabrication_notes=joinery_notes,
            installation_notes=hard_notes,
            warnings=package.warnings,
        )


class CADHandoffManifestGenerator:
    def generate(self, package: EngineeringDecisionPackage, scene: ParametricCADSceneGraph) -> CADHandoffManifest:
        pt = package.product_type
        views = ["top", "front", "side"]
        details = []
        if pt in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table","rectangular_table","console_table"):
            details = ["detail_pedestal_mounting", "detail_top_underside"]
        dims = ["overall_width", "overall_depth", "overall_height", "top_thickness"]
        if "pedestal" in package.template_id:
            dims += ["pedestal_diameter", "pedestal_offset"]
        return CADHandoffManifest(
            product_type=pt, template_id=package.template_id,
            drawing_sheets=["A3_shop_drawing"],
            required_views=views, required_details=details, required_dimensions=dims,
            annotation_layers={"notes": "ANNOTATIONS", "dimensions": "DIMENSIONS", "title_block": "TITLE_BLOCK"},
            source_package_confidence=package.confidence,
            approved_for_drafting=package.approved_for_drafting,
        )
