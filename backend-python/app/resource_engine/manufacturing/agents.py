"""Manufacturing agents — assembly planning, cutting, welding/finish/packaging, QC."""
from .models import (
    CADParameterPack, MaterialSpec, ProductionStep, CuttingItem,
    WeldItem, FinishItem, PackagingItem, QCCheck, QCChecklist,
)

# === Product routes (phase sequences per product type) ===
PRODUCT_ROUTES = {
    "dining_table": ["material_prep", "metal_fabrication", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "asymmetric_pedestal_table": ["material_prep", "metal_fabrication", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "coffee_table": ["material_prep", "metal_fabrication", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "console_table": ["material_prep", "metal_fabrication", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "oval_pedestal_table": ["material_prep", "metal_fabrication", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "rectangular_table": ["material_prep", "metal_fabrication", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "sideboard": ["material_prep", "panel_cutting", "edge_banding", "carcass_assembly", "hardware_install", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "tv_console": ["material_prep", "panel_cutting", "edge_banding", "carcass_assembly", "hardware_install", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "cabinet": ["material_prep", "panel_cutting", "edge_banding", "carcass_assembly", "hardware_install", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "wardrobe": ["material_prep", "panel_cutting", "edge_banding", "carcass_assembly", "hardware_install", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "nightstand": ["material_prep", "panel_cutting", "edge_banding", "carcass_assembly", "hardware_install", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
    "sofa": ["material_prep", "frame_cutting", "frame_assembly", "foam_build_up", "upholstery_cutting", "upholstery_install", "qc", "packaging"],
    "lounge_chair": ["material_prep", "frame_cutting", "frame_assembly", "foam_build_up", "upholstery_cutting", "upholstery_install", "qc", "packaging"],
    "dining_chair": ["material_prep", "frame_cutting", "frame_assembly", "foam_build_up", "upholstery_cutting", "upholstery_install", "qc", "packaging"],
    "bed": ["material_prep", "frame_cutting", "frame_assembly", "upholstery_cutting", "upholstery_install", "qc", "packaging"],
    "bed_headboard": ["material_prep", "panel_cutting", "upholstery_cutting", "upholstery_install", "qc", "packaging"],
    "office_desk": ["material_prep", "panel_cutting", "edge_banding", "carcass_assembly", "hardware_install", "dry_fit", "finishing", "final_assembly", "qc", "packaging"],
}

PHASE_TASKS = {
    "material_prep": "Confirm material, dimensions, and approved finish samples.",
    "metal_fabrication": "Fabricate metal support/base and hidden frame if required.",
    "dry_fit": "Dry-fit components and verify alignment before finishing.",
    "finishing": "Apply finish or polish/seal material as specified.",
    "final_assembly": "Install top, support/base, hardware, and leveling glides.",
    "qc": "Perform production QC checklist.",
    "packaging": "Protect and pack item for transport.",
    "panel_cutting": "Cut panels according to approved dimensions.",
    "edge_banding": "Apply edge banding or edge finishing.",
    "carcass_assembly": "Assemble carcass and verify squareness.",
    "hardware_install": "Install hinges, runners, glides, or connectors.",
    "frame_cutting": "Cut internal frame components.",
    "frame_assembly": "Assemble internal frame.",
    "foam_build_up": "Apply foam and padding build-up.",
    "upholstery_cutting": "Cut upholstery according to approved layout.",
    "upholstery_install": "Install upholstery and finish seams.",
}

PHASE_STATIONS = {
    "metal_fabrication": "metal shop",
    "frame_cutting": "wood shop", "panel_cutting": "wood shop",
    "edge_banding": "wood shop", "carcass_assembly": "wood shop",
    "foam_build_up": "upholstery shop", "upholstery_cutting": "upholstery shop",
    "upholstery_install": "upholstery shop",
    "qc": "quality control",
    "packaging": "packing area",
}


class AssemblyPlanner:
    def plan_steps(self, pack: CADParameterPack) -> list:
        route = PRODUCT_ROUTES.get(pack.product_type, ["material_prep", "final_assembly", "qc", "packaging"])
        steps = []
        for idx, phase in enumerate(route, 1):
            steps.append(ProductionStep(
                step_no=idx, phase=phase,
                task=PHASE_TASKS.get(phase, f"Perform {phase}."),
                station=PHASE_STATIONS.get(phase, "assembly area"),
                dependencies=[idx - 1] if idx > 1 else [],
            ))
        return steps


class CuttingPlanner:
    def make_cutting_list(self, pack: CADParameterPack, materials: list) -> list:
        p = pack.parameters; items = []
        if pack.product_type in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table",
                                  "rectangular_table","console_table","coffee_table"):
            L, D, T = p.get("length_mm",1800), p.get("depth_mm",900), p.get("top_thickness_mm",30)
            top_mat = "stone/marble" if T >= 20 else "wood"
            items.append(CuttingItem(part_id="TOP-01", description="Table top", material=top_mat, qty=1, length_mm=L, width_mm=D, thickness_mm=float(T)))
        return items


class WeldFinishPackagingPlanner:
    def weld_schedule(self, pack: CADParameterPack) -> list:
        if pack.product_type in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table",
                                  "coffee_table","console_table"):
            return [WeldItem(joint_id="W01", description="Weld mounting plate to pedestal column", process="MIG")]
        return []

    def finish_schedule(self, pack: CADParameterPack, materials: list) -> list:
        items = []
        for m in materials:
            items.append(FinishItem(part_id=m.role, finish=m.finish or "standard", prep=["Clean surface"], notes=m.notes))
        return items

    def packaging_plan(self, pack: CADParameterPack) -> list:
        return [PackagingItem(item="Finished product", method="Corner protection + shrink wrap + custom crate")]


class QCAgent:
    def make_checklist(self, product_type: str) -> QCChecklist:
        checks = [
            QCCheck(check_id="QC-01", description="Dimensions match parameter pack", acceptance_criteria="Within +/- 2mm", stage="dry_fit"),
            QCCheck(check_id="QC-02", description="Finish quality visual inspection", acceptance_criteria="No visible defects", stage="finishing"),
            QCCheck(check_id="QC-03", description="Hardware torque and alignment", acceptance_criteria="All fasteners torqued", stage="final_assembly"),
            QCCheck(check_id="QC-04", description="Leveling and stability check", acceptance_criteria="No wobble on flat surface", stage="final_assembly"),
            QCCheck(check_id="QC-05", description="Packaging integrity", acceptance_criteria="Protected for transport", stage="packaging"),
        ]
        return QCChecklist(product_type=product_type, checks=checks)
