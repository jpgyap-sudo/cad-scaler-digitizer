"""Template Instantiator — resolves parameters, applies constraints."""
from typing import Any, Dict, List
from .models import EngineeringDecisionPackage, FurnitureTemplate, TemplateInstance, TemplateConstraint


class TemplateInstantiator:
    def __init__(self, library: "TemplateLibrary"):
        self.library = library

    def instantiate(self, package: EngineeringDecisionPackage) -> TemplateInstance:
        tmpl = self.library.get(package.template_id)
        if not tmpl:
            return TemplateInstance(
                template_id=package.template_id, product_type=package.product_type,
                resolved_parameters=package.canonical_parameters, components=[],
                constraints=[], required_views=[], required_details=[], drawing_notes=[],
                warnings=[f"Template {package.template_id} not found"],
                confidence=package.confidence,
            )
        resolved = self._resolve_params(tmpl, package.canonical_parameters)
        warnings = self._evaluate_constraints(tmpl.constraints, resolved)
        return TemplateInstance(
            template_id=tmpl.id, product_type=tmpl.product_type,
            resolved_parameters=resolved, components=tmpl.components,
            constraints=tmpl.constraints, required_views=tmpl.required_views,
            required_details=tmpl.required_details, drawing_notes=tmpl.drawing_notes,
            warnings=warnings, confidence=package.confidence,
        )

    def _resolve_params(self, tmpl: FurnitureTemplate, canonical: Dict[str, Any]) -> Dict[str, Any]:
        params = {}
        for tp in tmpl.parameters:
            val = canonical.get(tp.name, tp.default)
            if tp.min_value is not None and val is not None and val < tp.min_value:
                val = tp.min_value
            if tp.max_value is not None and val is not None and val > tp.max_value:
                val = tp.max_value
            params[tp.name] = val
        # Merge any extra canonical params not in template
        for k, v in canonical.items():
            if k not in params:
                params[k] = v
        return params

    def _evaluate_constraints(self, constraints: List[TemplateConstraint],
                               params: Dict[str, Any]) -> List[str]:
        warnings = []
        for c in constraints:
            expr = c.expression
            for k, v in params.items():
                if isinstance(v, (int, float)):
                    expr = expr.replace(k, str(v))
            try:
                result = eval(expr)
                if not result:
                    warnings.append(f"[{c.severity}] {c.description}")
            except Exception:
                warnings.append(f"Constraint eval failed: {c.expression}")
        return warnings
