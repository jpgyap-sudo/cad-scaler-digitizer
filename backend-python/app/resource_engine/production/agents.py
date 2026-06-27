"""Material, joinery, hardware agents — deterministic rule-based production planning."""
from statistics import mean
from typing import Dict, List, Optional, Any, Tuple
from .models import (
    CADParameterPack, MaterialSpec, MaterialPlan, JoinerySpec, JoineryPlan,
    HardwareItem, HardwarePlan, BOM, BOMItem, ShopDrawingNotePack,
)

# ===== Material Rules =====
MATERIAL_ALIASES = {
    "white_stone": "marble / sintered stone", "marble": "marble / sintered stone",
    "stone": "marble / sintered stone", "travertine": "travertine",
    "walnut": "solid walnut / walnut veneer", "oak": "solid oak / oak veneer",
    "fabric": "upholstery fabric", "leather": "upholstery leather",
    "matte_black_metal": "matte black powdercoated steel",
    "brushed_metal": "brushed stainless steel",
    "lacquer": "gloss/matte lacquer finish",
}

DEFAULT_THICKNESS_MM = {
    "marble / sintered stone": 30, "travertine": 30,
    "solid walnut / walnut veneer": 25,
    "matte black powdercoated steel": 3,
    "gloss/matte lacquer finish": 18,
}

EDGE_TREATMENTS = {
    "marble / sintered stone": "eased, polished edge",
    "travertine": "chamfered, honed edge",
    "solid walnut / walnut veneer": "eased, sealed edge",
}


class MaterialProductionAgent:
    def run(self, pack: CADParameterPack, hints: Optional[Dict[str, str]] = None) -> MaterialPlan:
        hints = hints or {}
        pt = pack.product_type; p = pack.parameters
        specs = []; warnings = []

        if pt in ("dining_table","coffee_table","side_table","asymmetric_pedestal_table",
                  "oval_pedestal_table","rectangular_table","round_pedestal_table","console_table"):
            raw_top = hints.get("top") or hints.get("material_top") or "white_stone"
            raw_base = hints.get("base") or hints.get("material_base") or "matte_black_metal"
            t = MATERIAL_ALIASES.get(raw_top, raw_top)
            b = MATERIAL_ALIASES.get(raw_base, raw_base)
            specs.append(MaterialSpec(role="top", material=t, finish="honed/polished as selected",
                thickness_mm=p.get("top_thickness_mm") or DEFAULT_THICKNESS_MM.get(t),
                edge_treatment=EDGE_TREATMENTS.get(t), notes=["Verify slab availability."], confidence=0.86))
            specs.append(MaterialSpec(role="base", material=b, finish="matte powdercoat / brushed",
                thickness_mm=DEFAULT_THICKNESS_MM.get(b), notes=["Finish sample to be approved."], confidence=0.82))

        elif pt in ("sofa","lounge_chair","dining_chair","chair"):
            raw = hints.get("upholstery") or "fabric"
            m = MATERIAL_ALIASES.get(raw, raw)
            specs.append(MaterialSpec(role="upholstery", material=m, finish="selected fabric/leather",
                notes=["Confirm fabric code and seam layout."], confidence=0.80))

        elif pt in ("sideboard","tv_console","nightstand","cabinet","wardrobe"):
            raw = hints.get("case") or "walnut"
            m = MATERIAL_ALIASES.get(raw, raw)
            specs.append(MaterialSpec(role="casework", material=m, finish="veneer/lacquer as selected",
                thickness_mm=18, edge_treatment="eased edges", notes=["Confirm veneer direction."], confidence=0.78))

        elif pt in ("office_desk","desk","reception_counter"):
            specs.append(MaterialSpec(role="top", material="MDF with melamine / solid surface",
                thickness_mm=25, finish="selected", notes=["Verify edge banding."], confidence=0.80))

        elif pt in ("bed","bed_headboard"):
            specs.append(MaterialSpec(role="upholstery", material=hints.get("upholstery","fabric"),
                finish="selected", notes=["Confirm headboard panel."], confidence=0.75))

        conf = mean([s.confidence for s in specs]) if specs else 0.3
        return MaterialPlan(product_type=pt, materials=specs, warnings=warnings, confidence=round(conf, 3))


# ===== Joinery Rules =====
class JoineryProductionAgent:
    def run(self, pack: CADParameterPack, material_plan: MaterialPlan) -> JoineryPlan:
        pt = pack.product_type; specs = []; warnings = []
        mat_by_role = {m.role: m.material for m in material_plan.materials}

        if pt in ("dining_table","coffee_table","side_table","asymmetric_pedestal_table",
                  "oval_pedestal_table","rectangular_table","console_table"):
            top_mat = mat_by_role.get("top", "")
            if any(kw in top_mat for kw in ["marble","stone","travertine"]):
                specs.append(JoinerySpec(role="hidden_steel_frame", method="welded steel subframe",
                    components=["rectangular_tube_frame","mounting_plate"], confidence=0.84,
                    notes=["Steel frame bolted to stone top underside.", "All welds ground smooth and painted."]))
            specs.append(JoinerySpec(role="support_attachment", method="bolted plate connection",
                components=["top_plate","pedestal_flange","M8_bolts"], confidence=0.78,
                notes=["Mounting plate to be counterbored flush with pedestal top."]))

        elif pt in ("sideboard","tv_console","nightstand","cabinet","wardrobe"):
            specs.append(JoinerySpec(role="carcass", method="dowel + glue + cam lock",
                components=["side_panels","top_panel","shelves"], confidence=0.82,
                notes=["18mm panels, dowel + glue + cam lock assembly."]))
            specs.append(JoinerySpec(role="door_hinge", method="concealed hinge cup",
                components=["doors","frame"], confidence=0.78, notes=["Adjustable concealed hinges."]))

        elif pt in ("sofa","lounge_chair"):
            specs.append(JoinerySpec(role="internal_frame", method="plywood + webbing + foam",
                components=["seat_frame","back_frame","arms"], confidence=0.80,
                notes=["Plywood frame with elastic webbing suspension."]))

        elif pt in ("office_desk","desk"):
            specs.append(JoinerySpec(role="modesty_panel", method="screw + bracket attachment",
                components=["panel","legs"], confidence=0.76, notes=["Panel screws into leg brackets."]))

        conf = mean([s.confidence for s in specs]) if specs else 0.35
        return JoineryPlan(product_type=pt, joinery=specs, warnings=warnings, confidence=round(conf, 3))


# ===== Hardware Rules =====
class HardwareSelectionAgent:
    def run(self, pack: CADParameterPack, joinery_plan: JoineryPlan) -> HardwarePlan:
        pt = pack.product_type; items = []; warnings = []

        if pt in ("dining_table","coffee_table","side_table","asymmetric_pedestal_table",
                  "oval_pedestal_table","rectangular_table","console_table"):
            items = [
                HardwareItem(item="M8 x 30mm hex bolt", qty=8, size="M8x30", material="zinc plated steel", purpose="Mounting plate to pedestal"),
                HardwareItem(item="M8 flat washer", qty=16, size="M8", material="zinc plated steel", purpose="Under bolt head and nut"),
                HardwareItem(item="Rubber anti-slip pad", qty=4, size="30mm dia", material="rubber", purpose="Base plate to floor"),
            ]
        elif pt in ("sideboard","tv_console","nightstand","cabinet","wardrobe"):
            items = [
                HardwareItem(item="Concealed hinge", qty=8, purpose="Door to frame attachment"),
                HardwareItem(item="Push-to-open latch", qty=4, purpose="Tool-less door opening"),
            ]
        elif pt in ("sofa","lounge_chair"):
            items = [
                HardwareItem(item="Plastic glides", qty=4, purpose="Leg bottom to floor protection"),
            ]

        conf = 0.78 if items else 0.3
        return HardwarePlan(product_type=pt, hardware=items, warnings=warnings, confidence=conf)


# ===== Manufacturing / BOM =====
class ManufacturingAgent:
    def make_bom(self, pack: CADParameterPack, materials: MaterialPlan,
                 joinery: JoineryPlan, hardware: HardwarePlan) -> BOM:
        items = []; pt = pack.product_type; p = pack.parameters
        if pt in ("dining_table","coffee_table","side_table","asymmetric_pedestal_table",
                  "oval_pedestal_table","rectangular_table","console_table"):
            L, D = p.get("length_mm",1800), p.get("depth_mm",900)
            items.append(BOMItem(item_code="TOP-001", description=f"Table top {L}x{D} mm", qty=1, unit="pc", material=self._mat(materials,"top")))
            items.append(BOMItem(item_code="BASE-001", description="Pedestal base set", qty=1, unit="set", material=self._mat(materials,"base")))
        elif pt in ("sofa","lounge_chair","dining_chair"):
            items.append(BOMItem(item_code="UPH-001", description="Upholstered body", qty=1, unit="pc", material=self._mat(materials,"upholstery")))
        elif pt in ("sideboard","tv_console","nightstand","cabinet","wardrobe"):
            items.append(BOMItem(item_code="CASE-001", description="Carcass assembly", qty=1, unit="set", material=self._mat(materials,"casework")))
        for i, hw in enumerate(hardware.hardware, 1):
            items.append(BOMItem(item_code=f"HW-{i:03d}", description=hw.item, qty=hw.qty, unit="pc", material=hw.material, notes=hw.notes+([hw.purpose] if hw.purpose else [])))
        warns = materials.warnings + joinery.warnings + hardware.warnings
        return BOM(product_type=pt, items=items, warnings=warns)

    def make_note_pack(self, pack: CADParameterPack, materials: MaterialPlan,
                        joinery: JoineryPlan, hardware: HardwarePlan) -> ShopDrawingNotePack:
        mat_notes = []
        for m in materials.materials:
            n = f"{m.role.upper()}: {m.material}"
            if m.thickness_mm: n += f", {m.thickness_mm}MM"
            if m.finish: n += f", {m.finish}"
            if m.edge_treatment: n += f", EDGE: {m.edge_treatment}"
            mat_notes.append(n)
            mat_notes += m.notes
        join_notes = [f"{j.role.upper()}: {j.method}" for j in joinery.joinery] + sum((j.notes for j in joinery.joinery), [])
        hw_notes = []
        for h in hardware.hardware:
            l = f"{h.qty}x {h.item}"
            if h.size: l += f" ({h.size})"
            if h.purpose: l += f" - {h.purpose}"
            hw_notes.append(l)
        return ShopDrawingNotePack(
            product_type=pack.product_type,
            general_notes=["ALL DIMENSIONS IN MM.","VERIFY DIMENSIONS/MATERIAL/FINISH BEFORE PRODUCTION."],
            material_notes=mat_notes, joinery_notes=join_notes, hardware_notes=hw_notes,
            warnings=list(set(pack.warnings + materials.warnings + joinery.warnings + hardware.warnings)),
        )

    def _mat(self, materials: MaterialPlan, role: str):
        for m in materials.materials:
            if m.role == role: return m.material
        return None
