from .models import SectionDetail

class SectionDetailBuilder:
    def build(self, scene, plane, cut_components):
        notes = [plane.reason]

        roles = {c.get("role") for c in cut_components}
        if "top" in roles:
            notes.append("Call out top material and thickness.")
        if "joinery" in roles:
            notes.append("Show hidden frame / reinforcement as dashed or cut component.")
        if "support" in roles:
            notes.append("Show mounting plate, bolts, and pedestal connection.")
        if "case" in roles:
            notes.append("Show panel thickness and carcass construction.")
        if "seat" in roles or "back" in roles:
            notes.append("Show upholstery layers as schematic, unless exact construction is specified.")

        return SectionDetail(
            id=f"detail_{plane.label.replace('-', '')}",
            label=f"SECTION {plane.label}",
            section_plane_id=plane.id,
            cut_components=cut_components,
            notes=notes,
        )
