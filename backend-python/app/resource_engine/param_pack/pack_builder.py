"""Parameter Pack Builder — merges geometry + dimensions into CADParameterPack."""
from statistics import mean
from .models import GeometryPlan, DimensionPlan, CADParameterPack


class ParameterPackBuilder:
    """Builds a clean parameter pack for CAD generation."""

    def build(self, geometry: GeometryPlan, dimensions: DimensionPlan) -> CADParameterPack:
        params = dict(dimensions.dimensions_mm)

        # Add component-level dimensions
        for comp_id, comp_dims in dimensions.component_dimensions_mm.items():
            for k, v in comp_dims.items():
                if v is not None:
                    params[f"{comp_id}_{k}"] = v

        # Normalize for common template families
        if geometry.template_family == "table.dual_cylindrical_pedestal":
            large = dimensions.component_dimensions_mm.get("large_pedestal", {})
            small = dimensions.component_dimensions_mm.get("small_pedestal", {})
            params["large_pedestal_diameter_mm"] = large.get("diameter_mm", 420)
            params["small_pedestal_diameter_mm"] = small.get("diameter_mm", 220)
            ped_h = large.get("height_mm", params.get("height_mm", 750) - params.get("top_thickness_mm", 30))
            params["pedestal_height_mm"] = ped_h
            params.setdefault("left_pedestal_x_mm", -round(params.get("length_mm", 1800) * 0.23))
            params.setdefault("right_pedestal_x_mm", round(params.get("length_mm", 1800) * 0.23))

        warnings = list(geometry.warnings) + list(dimensions.warnings)
        confidence = round(mean([geometry.confidence, dimensions.confidence]), 3)

        return CADParameterPack(
            template_id=geometry.template_family,
            product_type=geometry.product_type,
            parameters=params,
            components=geometry.components,
            warnings=warnings,
            confidence=confidence,
        )
