"""Manufacturing pipeline — assembly → cutting → weld/finish/pack → QC → ReadyForCAD."""
from .models import CADParameterPack, MaterialSpec, ManufacturingPlan, ReadyForCADPackage
from .agents import AssemblyPlanner, CuttingPlanner, WeldFinishPackagingPlanner, QCAgent


class ManufacturingPipeline:
    def run(self, pack: CADParameterPack, materials: list) -> tuple:
        assembly = AssemblyPlanner().plan_steps(pack)
        cutting = CuttingPlanner().make_cutting_list(pack, materials)
        wfp = WeldFinishPackagingPlanner()
        weld = wfp.weld_schedule(pack)
        finish = wfp.finish_schedule(pack, materials)
        packaging = wfp.packaging_plan(pack)
        risks = self._risk_rules(pack.product_type, pack.parameters, materials)
        plan = ManufacturingPlan(
            product_type=pack.product_type, template_id=pack.template_id,
            production_steps=assembly, cutting_list=cutting,
            weld_schedule=weld, finish_schedule=finish,
            packaging_plan=packaging, risks=risks,
        )
        qc = QCAgent().make_checklist(pack.product_type)
        # Build ReadyForCADPackage
        notes = [f"{s.step_no}. {s.task}" for s in assembly]
        notes += [f"RISK: {r}" for r in risks]
        ready = ReadyForCADPackage(
            product_type=pack.product_type, template_id=pack.template_id,
            cad_parameters=pack.parameters, drawing_notes=notes,
            manufacturing_plan=plan, qc_checklist=qc,
            warnings=list(set(pack.warnings + risks)),
            confidence=pack.confidence,
        )
        return plan, qc, ready

    def _risk_rules(self, pt: str, params: dict, materials: list) -> list:
        risks = []
        if pt in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table","rectangular_table","coffee_table"):
            L = params.get("length_mm", 1800)
            if L > 2400: risks.append("Oversize top requires lifting equipment and two-person handling.")
            for m in materials:
                if "stone" in m.material.lower() or "marble" in m.material.lower():
                    risks.append("Stone top: handle with suction lifters; protect edges during transport.")
        if pt in ("sideboard","cabinet","wardrobe"):
            H = params.get("height_mm", 800)
            if H > 2000: risks.append("Tall cabinet: door alignment and stability must be verified.")
        return risks
