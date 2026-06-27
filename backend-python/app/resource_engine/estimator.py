"""Dimension Estimator — provides default dimensions per product type."""
from typing import Dict, Any, Optional


class DimensionEstimator:
    """Estimates standard dimensions for a furniture product type."""

    def estimate(self, product_type: str, subtype: str = "",
                 top_shape: str = "") -> Dict[str, Any]:
        pt = product_type

        # === TABLES ===
        if pt in ("dining_table", "asymmetric_pedestal_table", "oval_pedestal_table",
                  "rectangular_table", "round_pedestal_table", "console_table"):
            if "round" in top_shape:
                return {"diameter_mm": 1200, "height_mm": 750, "top_thickness_mm": 30}
            return {"length_mm": 1800, "depth_mm": 900, "height_mm": 750, "top_thickness_mm": 30}

        if pt == "coffee_table":
            return {"length_mm": 1200, "depth_mm": 600, "height_mm": 380, "top_thickness_mm": 30}

        if pt == "side_table":
            return {"length_mm": 500, "depth_mm": 500, "height_mm": 520, "top_thickness_mm": 25}

        # === SEATING ===
        if pt == "sofa":
            if "3" in subtype:
                return {"length_mm": 2200, "depth_mm": 950, "height_mm": 780, "seat_height_mm": 420}
            if "sectional" in subtype or "L" in subtype:
                return {"length_mm": 2800, "depth_mm": 1800, "height_mm": 780, "seat_height_mm": 420}
            return {"length_mm": 1800, "depth_mm": 900, "height_mm": 780, "seat_height_mm": 420}

        if pt == "lounge_chair":
            return {"length_mm": 800, "depth_mm": 850, "height_mm": 780, "seat_height_mm": 420}

        if pt in ("dining_chair", "chair"):
            return {"length_mm": 520, "depth_mm": 560, "height_mm": 820, "seat_height_mm": 450}

        # === BEDS ===
        if pt in ("bed", "bed_headboard"):
            return {"length_mm": 2030, "depth_mm": 1830, "height_mm": 1000, "platform_height_mm": 300}

        # === STORAGE ===
        if pt in ("sideboard", "tv_console"):
            return {"length_mm": 1800, "depth_mm": 450, "height_mm": 800}

        if pt == "nightstand":
            return {"length_mm": 500, "depth_mm": 420, "height_mm": 500}

        if pt in ("cabinet", "wardrobe"):
            return {"length_mm": 1000, "depth_mm": 500, "height_mm": 1800}

        # === DESK ===
        if pt in ("office_desk", "desk", "reception_counter"):
            return {"length_mm": 1400, "depth_mm": 600, "height_mm": 750}

        # Fallback
        return {"length_mm": 1000, "depth_mm": 500, "height_mm": 750}
