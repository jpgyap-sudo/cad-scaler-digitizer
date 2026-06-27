"""TemplateResolver — resolves detected product_type → template graph with parameter overrides."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from .template_loader import TemplateGraphLoader

# Mapping from normalized furniture types (as used by /digitize and /digitize/hybrid)
# to the product_type field in template graphs
PRODUCT_TYPE_MAP = {
    "round_pedestal_table": "round_pedestal_table",
    "rectangular_table": "rectangular_table",
    "oval_pedestal_table": "oval_pedestal_table",
    "console_table": "console_table",
    "coffee_table": "coffee_table",
    "side_table": "side_table",
    "office_desk": "office_desk",
    "cabinet": "sideboard",           # generic cabinet → sideboard template
    "sideboard": "sideboard",
    "tv_console": "tv_console",
    "nightstand": "nightstand",
    "wardrobe": "wardrobe",
    "bed": "bed",
    "bed_headboard": "bed_headboard",
    "sofa": "sofa",
    "lounge_chair": "lounge_chair",
    "dining_chair": "dining_chair",
    "chair": "dining_chair",         # generic chair → dining_chair template
    "reception_counter": "reception_counter",
    "asymmetric_pedestal_table": "asymmetric_pedestal_table",
}

# Dimensional mapping: how detected_dimension keys (in cm) map to template parameter names (in mm)
DIMENSION_CM_TO_MM_MAP: Dict[str, Dict[str, str]] = {
    "rectangular_table": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm", "top_thickness_cm": "top_thickness_mm",
        "leg_thickness_cm": "leg_size_mm",
    },
    "round_pedestal_table": {
        "top_diameter_cm": "diameter_mm", "overall_height_cm": "height_mm",
        "top_thickness_cm": "top_thickness_mm",
        "base_diameter_cm": "pedestal_diameter_mm",
        "neck_diameter_cm": "pedestal_height_mm",
    },
    "oval_pedestal_table": {
        "length_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm", "top_thickness_cm": "top_thickness_mm",
        "pedestal_dia_cm": "pedestal_diameter_mm",
    },
    "console_table": {
        "length_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm", "top_thickness_cm": "top_thickness_mm",
        "leg_thick_cm": "leg_size_mm",
    },
    "coffee_table": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm", "top_thickness_cm": "top_thickness_mm",
    },
    "side_table": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm", "top_thickness_cm": "top_thickness_mm",
    },
    "office_desk": {
        "length_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm", "top_thickness_cm": "top_thickness_mm",
        "leg_thick_cm": "leg_size_mm", "modesty_panel_h_cm": "modesty_panel_height_mm",
    },
    "sideboard": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm",
    },
    "tv_console": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm",
    },
    "nightstand": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm",
    },
    "wardrobe": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm",
    },
    "bed": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm",
    },
    "bed_headboard": {
        "width_cm": "width_mm", "overall_height_cm": "height_mm",
    },
    "sofa": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm",
        "seat_height_cm": "seat_height_mm",
    },
    "lounge_chair": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm",
        "seat_height_cm": "seat_height_mm",
    },
    "dining_chair": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "seat_height_cm": "seat_height_mm",
        "overall_height_cm": "overall_height_mm",
    },
    "reception_counter": {
        "width_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "overall_height_mm",
        "counter_height_cm": "counter_height_mm",
    },
    "asymmetric_pedestal_table": {
        "length_cm": "length_mm", "depth_cm": "depth_mm",
        "overall_height_cm": "height_mm", "top_thickness_cm": "top_thickness_mm",
        "large_ped_dia_cm": "large_pedestal_diameter_mm",
        "small_ped_dia_cm": "small_pedestal_diameter_mm",
        "left_ped_x_cm": "left_pedestal_x_mm",
        "right_ped_x_cm": "right_pedestal_x_mm",
    },
}


class TemplateResolutionError(Exception):
    """Raised when template resolution fails."""


class TemplateResolver:
    """Resolves a detected furniture type into a template graph with parameter overrides.

    Bridges the gap between /digitize/hybrid's detected dimensions (in cm)
    and the template graph parameters (in mm).
    """

    def __init__(self, loader: Optional[TemplateGraphLoader] = None):
        self._loader = loader or TemplateGraphLoader().load()

    def resolve(self, furniture_type: str,
                detected_dims_cm: Dict[str, float],
                materials: Optional[Dict[str, str]] = None,
                ) -> Dict[str, Any]:
        """Resolve a furniture_type + detected dimensions → template graph.

        Args:
            furniture_type: Normalized furniture type (e.g. 'round_pedestal_table')
            detected_dims_cm: Dict of dimension keys → values in cm
            materials: Optional dict of component → material description

        Returns:
            Dict with keys:
                - template: the full template graph dict
                - resolved_parameters: template parameters with dimension overrides applied (in mm)
                - constraints: evaluated constraint results
                - component_views: required views from template
                - warnings: any constraint warnings

        Raises:
            TemplateResolutionError if no template found for the given type.
        """
        # Map normalized furniture type to template product_type
        tpl_product_type = PRODUCT_TYPE_MAP.get(furniture_type)
        if not tpl_product_type:
            raise TemplateResolutionError(
                f"No template mapping for furniture_type '{furniture_type}'"
            )

        tpl = self._loader.get_default(tpl_product_type)
        if not tpl:
            raise TemplateResolutionError(
                f"No template found for product_type '{tpl_product_type}' "
                f"(mapped from '{furniture_type}')"
            )

        # Build resolved parameters: start with defaults, overlay detected dims
        resolved_mm: Dict[str, float] = {}
        for param in tpl.get("parameters", []):
            pname = param["name"]
            resolved_mm[pname] = param.get("default")

        # Map detected cm dimensions → template mm parameters
        dim_map = DIMENSION_CM_TO_MM_MAP.get(tpl_product_type, {})
        for dim_key, val_cm in detected_dims_cm.items():
            if val_cm is None or val_cm <= 0:
                continue
            tpl_param = dim_map.get(dim_key)
            if tpl_param:
                # Convert cm → mm for the template
                resolved_mm[tpl_param] = val_cm * 10.0
            else:
                # Try direct match on parameter name
                for pname in resolved_mm:
                    if dim_key.replace("_cm", "_mm") == pname:
                        resolved_mm[pname] = val_cm * 10.0
                        break

        # Evaluate constraints against resolved parameters
        constraints = tpl.get("constraints", [])
        constraint_results = self._evaluate_constraints(constraints, resolved_mm)

        # Collect warnings from constraints
        warnings = [
            c["description"]
            for c in constraint_results
            if not c["passed"] and c.get("severity") != "info"
        ]

        # Build response
        result = {
            "template": tpl,
            "resolved_parameters": resolved_mm,
            "constraints": constraint_results,
            "component_views": tpl.get("required_views", []),
            "required_details": tpl.get("required_details", []),
            "drawing_notes": tpl.get("drawing_notes", []),
            "warnings": warnings,
        }

        if materials:
            result["materials"] = materials

        return result

    def resolve_all(self) -> List[Dict[str, Any]]:
        """Get all available template summaries for the frontend catalog."""
        summaries = []
        for tpl in self._loader.list_all():
            summaries.append({
                "id": tpl["id"],
                "name": tpl.get("name", ""),
                "product_type": tpl.get("product_type", ""),
                "family": tpl.get("family", ""),
                "parameter_count": len(tpl.get("parameters", [])),
                "component_count": len(tpl.get("components", [])),
                "required_views": tpl.get("required_views", []),
            })
        return summaries

    def _evaluate_constraints(
        self, constraints: List[Dict[str, Any]],
        resolved: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Evaluate template constraints against resolved parameters.

        Simple expression evaluator supporting: <=, >=, <, >, ==, and, or.
        """
        results = []
        for c in constraints:
            expr = c.get("expression", "")
            severity = c.get("severity", "warning")

            try:
                passed = self._eval_expression(expr, resolved)
            except Exception as e:
                passed = True  # soft-fail on evaluation errors
                print(f"[TemplateResolver] Constraint eval failed: {e}")

            results.append({
                "id": c["id"],
                "description": c.get("description", ""),
                "expression": expr,
                "severity": severity,
                "passed": passed,
            })
        return results

    def _eval_expression(self, expr: str, params: Dict[str, float]) -> bool:
        """Evaluate a simple constraint expression with parameter values substituted."""
        # Handle "and" / "or" operators
        if " and " in expr.lower():
            parts = expr.lower().split(" and ")
            return all(self._eval_simple(p.strip(), params) for p in parts)
        if " or " in expr.lower():
            parts = expr.lower().split(" or ")
            return any(self._eval_simple(p.strip(), params) for p in parts)
        return self._eval_simple(expr, params)

    def _eval_simple(self, expr: str, params: Dict[str, float]) -> bool:
        """Evaluate a single comparison expression like '720 <= height_mm <= 780'."""
        expr = expr.strip()

        # Handle chained comparisons: a <= b <= c
        import re
        chain_match = re.match(
            r"([\w_]+)\s*(<=|<|>=|>|==)\s*([\w_]+)\s*(<=|<|>=|>|==)\s*([\w_]+)",
            expr
        )
        if chain_match:
            left, op1, middle, op2, right = (
                chain_match.group(1), chain_match.group(2),
                chain_match.group(3), chain_match.group(4), chain_match.group(5)
            )
            left_val = self._resolve_value(left, params)
            middle_val = self._resolve_value(middle, params)
            right_val = self._resolve_value(right, params)
            return (self._apply_op(left_val, op1, middle_val)
                    and self._apply_op(middle_val, op2, right_val))

        # Handle simple binary comparisons
        simple_match = re.match(
            r"([\w_.]+)\s*(<=|<|>=|>|==)\s*([\w_.]+)", expr
        )
        if simple_match:
            left, op, right = (
                simple_match.group(1), simple_match.group(2), simple_match.group(3)
            )
            left_val = self._resolve_value(left, params)
            right_val = self._resolve_value(right, params)
            return self._apply_op(left_val, op, right_val)

        # Fallback: try Python eval for complex expressions
        safe_globals = {"__builtins__": {}}
        safe_locals = {k: v for k, v in params.items()}
        return bool(eval(expr, safe_globals, safe_locals))

    def _resolve_value(self, token: str, params: Dict[str, float]) -> float:
        """Resolve a token to a float value (parameter lookup or literal number)."""
        try:
            return float(token)
        except ValueError:
            pass
        if token in params:
            return float(params[token])
        # Try stripping common suffixes
        for suffix in ["_mm", "_cm", "_m"]:
            base = token.replace(suffix, "")
            if base in params:
                return float(params[base])
        raise ValueError(f"Cannot resolve '{token}' — not a parameter or numeric literal")

    def _apply_op(self, left: float, op: str, right: float) -> bool:
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "==":
            return abs(left - right) < 0.001
        return False
