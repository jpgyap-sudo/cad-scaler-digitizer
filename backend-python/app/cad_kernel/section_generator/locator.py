from .models import SectionPlane

class SectionLocator:
    def suggest_planes(self, scene):
        nodes = scene.get("nodes", [])
        sections = []

        roles = {n.get("role") for n in nodes}
        template = scene.get("template_id", "")

        if "top" in roles:
            sections.append(SectionPlane(
                id="section_AA",
                label="A-A",
                orientation="longitudinal",
                position_mm=0,
                target_node_ids=[n.get("id") for n in nodes if n.get("role") in ["top", "joinery"]],
                reason="Show tabletop thickness and hidden frame."
            ))

        if "dual_cylindrical" in template or any(n.get("shape") == "cylinder" for n in nodes):
            sections.append(SectionPlane(
                id="section_BB",
                label="B-B",
                orientation="transverse",
                position_mm=0,
                target_node_ids=[n.get("id") for n in nodes if n.get("role") in ["support", "joinery"]],
                reason="Show pedestal mounting and base connection."
            ))

        if "casework" in template or "sideboard" == scene.get("product_type"):
            sections.append(SectionPlane(
                id="section_CC",
                label="C-C",
                orientation="vertical",
                position_mm=0,
                target_node_ids=[n.get("id") for n in nodes if n.get("role") in ["case", "doors_or_drawers"]],
                reason="Show carcass, panel thickness, and hardware clearances."
            ))

        if scene.get("product_type") in ["sofa", "lounge_chair", "dining_chair"]:
            sections.append(SectionPlane(
                id="section_UPH",
                label="Upholstery Section",
                orientation="vertical",
                position_mm=0,
                target_node_ids=[n.get("id") for n in nodes if n.get("role") in ["seat", "back", "arms"]],
                reason="Show upholstery build-up and seat height."
            ))

        return sections
