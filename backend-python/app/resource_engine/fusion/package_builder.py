"""Engineering Package Builder — builds the final decision package."""
from statistics import mean
from .models import AgentOutput, EngineeringDecisionPackage, AuditTrail


class EngineeringPackageBuilder:
    def build(self, product_type: str, template_id: str, flat_final: dict,
              conflicts: list, outputs: list[AgentOutput], validation=None):
        confidences = [o.confidence for o in outputs if o.confidence > 0]
        avg_conf = round(mean(confidences), 3) if confidences else 0.5
        approved = validation.approved_for_drafting if validation else True

        # Extract category groupings
        geometry = {k: v for k, v in flat_final.items() if k in ("top_shape","support_type","template_family","symmetry")}
        materials = {k: v for k, v in flat_final.items() if "material" in k or k.endswith("_finish")}
        joinery = {k: v for k, v in flat_final.items() if "joinery" in k or "hidden" in k}

        all_warnings = []
        for o in outputs:
            all_warnings.extend(o.warnings)
        if validation:
            all_warnings.extend([i.get("message","") for i in validation.issues])

        return EngineeringDecisionPackage(
            product_type=product_type, template_id=template_id,
            canonical_parameters=flat_final,
            geometry=geometry, materials=materials, joinery=joinery,
            manufacturing_notes=[], drawing_notes=[],
            warnings=list(set(all_warnings)),
            conflicts=conflicts,
            approved_for_drafting=approved,
            confidence=avg_conf,
        )
