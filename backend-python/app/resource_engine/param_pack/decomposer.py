"""Geometry Decomposer — breaks product type into component nodes."""
from .models import VisionFeatures, GeometryPlan, ComponentNode


class GeometryDecomposer:
    """Decomposes a product type into a tree of component nodes."""

    def decompose(self, features: VisionFeatures) -> GeometryPlan:
        pt = features.product_type
        components = []
        warnings = []

        if pt in ("dining_table", "coffee_table", "side_table", "asymmetric_pedestal_table",
                  "oval_pedestal_table", "rectangular_table", "round_pedestal_table", "console_table"):
            top_shape = features.top_shape or "rectangular"
            components.append(ComponentNode(id="top", role="top", shape=top_shape, quantity=1, confidence=0.9))

            support = features.support_type or "unknown"
            if support == "dual_cylindrical_pedestal":
                components.append(ComponentNode(id="large_pedestal", role="support", shape="cylinder", quantity=1, confidence=0.88))
                components.append(ComponentNode(id="small_pedestal", role="support", shape="cylinder", quantity=1, confidence=0.84))
            elif support in ("single_pedestal",):
                components.append(ComponentNode(id="center_pedestal", role="support", shape="cylinder", quantity=1, confidence=0.82))
            elif support in ("four_leg",):
                components.append(ComponentNode(id="legs", role="support", shape="rectangular_prism", quantity=4, confidence=0.82))
            else:
                components.append(ComponentNode(id="support", role="support", shape="unknown", quantity=1, confidence=0.45))
                warnings.append("Support type uncertain.")

            if features.material_top in ("white_stone", "marble", "stone", "travertine"):
                components.append(ComponentNode(id="hidden_frame", role="joinery", shape="rectangular_steel_frame", quantity=1, visible=False, confidence=0.72))

        elif pt in ("sofa", "lounge_chair", "dining_chair", "chair"):
            components += [
                ComponentNode(id="seat_block", role="seat", shape="rectangular_cushion_block", quantity=1, confidence=0.86),
                ComponentNode(id="back_block", role="back", shape="rectangular_back_block", quantity=1, confidence=0.82),
                ComponentNode(id="arms", role="arms", shape="rectangular_arm_block", quantity=2, confidence=0.70),
                ComponentNode(id="base", role="base", shape="low_plinth_or_legs", quantity=1, confidence=0.55),
            ]

        elif pt in ("sideboard", "tv_console", "nightstand", "cabinet", "wardrobe"):
            components += [
                ComponentNode(id="case", role="case", shape="rectangular_box", quantity=1, confidence=0.9),
                ComponentNode(id="fronts", role="doors_or_drawers", shape="rectangular_panels", quantity=4, confidence=0.65),
                ComponentNode(id="base", role="base", shape="plinth_or_legs", quantity=1, confidence=0.55),
            ]

        elif pt in ("bed", "bed_headboard"):
            components += [
                ComponentNode(id="platform", role="platform", shape="rectangular_platform", quantity=1, confidence=0.86),
                ComponentNode(id="headboard", role="headboard", shape="vertical_panel", quantity=1, confidence=0.82),
                ComponentNode(id="base", role="base", shape="low_plinth_or_legs", quantity=1, confidence=0.55),
            ]

        elif pt in ("office_desk", "desk", "reception_counter"):
            components += [
                ComponentNode(id="top", role="top", shape="rectangular", quantity=1, confidence=0.9),
                ComponentNode(id="legs", role="support", shape="rectangular_prism", quantity=4, confidence=0.82),
                ComponentNode(id="modesty_panel", role="modesty", shape="rectangular_panel", quantity=1, confidence=0.70),
            ]

        else:
            components.append(ComponentNode(id="main_body", role="body", shape="unknown", quantity=1, confidence=0.3))
            warnings.append("Product type not recognized.")

        template = self._choose_template(pt, features.top_shape, features.support_type)
        return GeometryPlan(
            product_type=pt, template_family=template,
            components=components, symmetry="bilateral",
            warnings=warnings, confidence=max(0.5, features.confidence * 0.9),
        )

    def _choose_template(self, pt: str, top_shape: str = "", support: str = "") -> str:
        if pt == "dining_table" or pt == "asymmetric_pedestal_table":
            return "table.dual_cylindrical_pedestal"
        if pt == "oval_pedestal_table":
            return "table.single_pedestal_oval"
        if pt == "round_pedestal_table":
            return "table.single_pedestal_round"
        if pt in ("rectangular_table", "console_table"):
            return "table.four_leg_rectangular"
        if pt == "coffee_table":
            return "table.coffee"
        if pt in ("sofa",):
            return "sofa.standard"
        if pt in ("dining_chair", "chair"):
            return "chair.standard"
        if pt in ("bed", "bed_headboard"):
            return "bed.standard"
        if pt in ("sideboard", "tv_console", "nightstand", "cabinet", "wardrobe"):
            return "cabinet.standard"
        if pt in ("office_desk", "desk"):
            return "desk.standard"
        return f"{pt}.generic"
