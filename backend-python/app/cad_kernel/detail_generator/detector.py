from .models import DetailCandidate

class DetailCandidateDetector:
    def detect(self, scene, sections=None):
        nodes = scene.get("nodes", [])
        roles = {n.get("role") for n in nodes}
        shapes = {n.get("shape") for n in nodes}
        template = scene.get("template_id", "")
        details = []

        if "top" in roles:
            details.append(DetailCandidate(id="D_TOP_EDGE",detail_type="top_edge_thickness",
                source_node_ids=[n["id"] for n in nodes if n.get("role")=="top"],
                priority=70,reason="Show tabletop thickness, edge treatment, and finish."))
        if "joinery" in roles or any("frame" in (n.get("id","") or "") for n in nodes):
            details.append(DetailCandidate(id="D_HIDDEN_FRAME",detail_type="hidden_frame",
                source_node_ids=[n["id"] for n in nodes if n.get("role") in ("joinery","top")],
                priority=95,reason="Hidden frame needs enlarged detail for production."))
        if "cylinder" in shapes or "dual_cylindrical" in template:
            details.append(DetailCandidate(id="D_PEDESTAL_MOUNT",detail_type="pedestal_mounting_plate",
                source_node_ids=[n["id"] for n in nodes if n.get("role") in ("support","joinery","top")],
                priority=100,reason="Pedestal-to-top connection requires detail."))
        if scene.get("product_type") in ("sideboard","tv_console","cabinet","nightstand"):
            details.append(DetailCandidate(id="D_CASE_HARDWARE",detail_type="casework_hardware",
                source_node_ids=[n["id"] for n in nodes if n.get("role") in ("case","doors_or_drawers")],
                priority=90,reason="Casework needs hinge/drawer runner/front reveal detail."))
        if scene.get("product_type") in ("sofa","lounge_chair","dining_chair"):
            details.append(DetailCandidate(id="D_UPHOLSTERY",detail_type="upholstery_build_up",
                source_node_ids=[n["id"] for n in nodes if n.get("role") in ("seat","back","arms")],
                priority=90,reason="Upholstery needs build-up/detail note."))
        return sorted(details, key=lambda d: d.priority, reverse=True)
