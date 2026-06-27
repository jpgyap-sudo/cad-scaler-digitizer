"""Dimension Estimator — estimates dimensions with sanity checks."""
from .models import VisionFeatures, GeometryPlan, DimensionPlan

# Standard dimension profiles
STANDARD_DIMENSIONS = {
    "dining_table": {"length_mm": 1800, "depth_mm": 900, "height_mm": 750, "top_thickness_mm": 30},
    "coffee_table": {"length_mm": 1200, "depth_mm": 600, "height_mm": 380, "top_thickness_mm": 30},
    "side_table": {"length_mm": 500, "depth_mm": 500, "height_mm": 520, "top_thickness_mm": 25},
    "sofa_2_seater": {"length_mm": 1800, "depth_mm": 900, "height_mm": 780, "seat_height_mm": 420},
    "sofa_3_seater": {"length_mm": 2200, "depth_mm": 950, "height_mm": 780, "seat_height_mm": 420},
    "lounge_chair": {"length_mm": 800, "depth_mm": 850, "height_mm": 780, "seat_height_mm": 420},
    "dining_chair": {"length_mm": 520, "depth_mm": 560, "height_mm": 820, "seat_height_mm": 450},
    "bed_king": {"length_mm": 2030, "depth_mm": 1830, "height_mm": 1000, "platform_height_mm": 300},
    "bed_queen": {"length_mm": 2030, "depth_mm": 1580, "height_mm": 1000, "platform_height_mm": 300},
    "sideboard": {"length_mm": 1800, "depth_mm": 450, "height_mm": 800},
    "tv_console": {"length_mm": 1800, "depth_mm": 450, "height_mm": 600},
    "nightstand": {"length_mm": 500, "depth_mm": 420, "height_mm": 500},
    "cabinet": {"length_mm": 1000, "depth_mm": 500, "height_mm": 1800},
    "wardrobe": {"length_mm": 1200, "depth_mm": 600, "height_mm": 2000},
    "office_desk": {"length_mm": 1400, "depth_mm": 600, "height_mm": 750, "modesty_panel_h_mm": 150},
    "desk": {"length_mm": 1400, "depth_mm": 600, "height_mm": 750, "modesty_panel_h_mm": 150},
    "reception_counter": {"length_mm": 1800, "depth_mm": 800, "height_mm": 1100},
    "console_table": {"length_mm": 1200, "depth_mm": 400, "height_mm": 750},
    "asymmetric_pedestal_table": {"length_mm": 1800, "depth_mm": 900, "height_mm": 750, "top_thickness_mm": 30},
    "oval_pedestal_table": {"length_mm": 1800, "depth_mm": 1000, "height_mm": 750, "top_thickness_mm": 30},
    "round_pedestal_table": {"diameter_mm": 1200, "height_mm": 750, "top_thickness_mm": 30},
    "rectangular_table": {"length_mm": 1800, "depth_mm": 900, "height_mm": 750, "top_thickness_mm": 30},
}


class DimensionEstimator:
    """Estimates dimensions with per-product-type sanity checks."""

    def estimate(self, features: VisionFeatures, geometry: GeometryPlan) -> DimensionPlan:
        key = self._standard_key(features)
        dims = dict(STANDARD_DIMENSIONS.get(key, STANDARD_DIMENSIONS.get(features.product_type, {})))
        dims.update({k: v for k, v in features.approximate_dimensions_mm.items() if v})

        assumptions = [f"Used standard: {key}"]
        warnings = []

        dims.setdefault("length_mm", 1000)
        dims.setdefault("depth_mm", 500)
        dims.setdefault("height_mm", 750)

        if features.product_type in ("dining_table", "asymmetric_pedestal_table", "oval_pedestal_table",
                                      "rectangular_table", "console_table", "round_pedestal_table"):
            dims.setdefault("top_thickness_mm", 30)
            if not (720 <= dims.get("height_mm", 750) <= 780):
                warnings.append(f"Dining height {dims['height_mm']}mm outside 720-780mm range.")

        if features.product_type == "coffee_table":
            if not (300 <= dims.get("height_mm", 380) <= 480):
                warnings.append("Coffee table height outside normal range.")

        if features.product_type in ("sofa", "lounge_chair"):
            dims.setdefault("seat_height_mm", 420)
            if not (380 <= dims.get("seat_height_mm", 420) <= 460):
                warnings.append("Sofa seat height outside common range.")

        if features.product_type in ("office_desk", "desk"):
            dims.setdefault("modesty_panel_h_mm", 150)
            if dims.get("depth_mm", 600) < 500:
                warnings.append("Desk depth below 500mm minimum.")

        component_dims = self._component_dimensions(features, geometry, dims)

        return DimensionPlan(
            product_type=features.product_type,
            dimensions_mm=dims,
            component_dimensions_mm=component_dims,
            assumptions=assumptions,
            warnings=warnings,
            confidence=max(0.55, features.confidence * 0.85),
        )

    def _standard_key(self, features: VisionFeatures) -> str:
        if features.product_type == "sofa":
            if features.subtype and "3" in features.subtype:
                return "sofa_3_seater"
            return "sofa_2_seater"
        if features.product_type == "bed":
            if features.subtype and "queen" in features.subtype.lower():
                return "bed_queen"
            return "bed_king"
        return features.product_type

    def _component_dimensions(self, features, geometry, dims):
        out = {}
        for c in geometry.components:
            if c.role == "top":
                out[c.id] = {"length_mm": dims.get("length_mm"), "depth_mm": dims.get("depth_mm"),
                             "thickness_mm": dims.get("top_thickness_mm", 30)}
            elif c.id == "large_pedestal":
                out[c.id] = {"diameter_mm": max(300, round(dims.get("depth_mm", 900) * 0.47)),
                             "height_mm": dims.get("height_mm", 750) - dims.get("top_thickness_mm", 30)}
            elif c.id == "small_pedestal":
                out[c.id] = {"diameter_mm": max(160, round(dims.get("depth_mm", 900) * 0.24)),
                             "height_mm": dims.get("height_mm", 750) - dims.get("top_thickness_mm", 30)}
            elif c.role in ("seat", "back", "arms", "case", "platform", "headboard", "modesty"):
                out[c.id] = dict(dims)
        return out
