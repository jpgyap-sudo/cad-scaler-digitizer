"""CAD Scene Graph Builder — final graph for DXF generation."""
from .models import EngineeringDecisionPackage, ParametricCADSceneGraph, CADSceneNode, CADViewSpec


class CADSceneGraphBuilder:
    def build(self, package: EngineeringDecisionPackage) -> ParametricCADSceneGraph:
        pt, tpl = package.product_type, package.template_id; p = package.canonical_parameters
        nodes = []
        if pt in ("dining_table","asymmetric_pedestal_table","oval_pedestal_table",
                  "rectangular_table","console_table","coffee_table","side_table","round_pedestal_table"):
            nodes.append(CADSceneNode(id="top", role="top", shape="rectangle",
                parameters={"length_mm": p.get("length_mm",1800),"depth_mm": p.get("depth_mm",900),"thickness_mm": p.get("top_thickness_mm",30)},
                material_role="top"))
            if "dual_cylindrical" in tpl:
                nodes.append(CADSceneNode(id="large_pedestal",role="support",shape="cylinder",
                    parameters={"diameter_mm": p.get("large_pedestal_diameter_mm",420),"height_mm": p.get("pedestal_height_mm",720),"x_mm": p.get("left_pedestal_x_mm",-420)},
                    material_role="base"))
                nodes.append(CADSceneNode(id="small_pedestal",role="support",shape="cylinder",
                    parameters={"diameter_mm": p.get("small_pedestal_diameter_mm",220),"height_mm": p.get("pedestal_height_mm",720),"x_mm": p.get("right_pedestal_x_mm",420)},
                    material_role="base"))
            if package.joinery:
                nodes.append(CADSceneNode(id="hidden_frame",role="joinery",shape="rectangular_frame",visible=False,
                    parameters={"length_mm": p.get("length_mm",1800)-240,"depth_mm": p.get("depth_mm",900)-240},
                    material_role="steel"))
        elif pt in ("sofa","lounge_chair","dining_chair","chair"):
            nodes.append(CADSceneNode(id="seat",role="seat",shape="upholstered_block",parameters=p,material_role="upholstery"))
            nodes.append(CADSceneNode(id="back",role="back",shape="upholstered_back",parameters=p,material_role="upholstery"))
        elif pt in ("sideboard","tv_console","nightstand","cabinet","wardrobe"):
            nodes.append(CADSceneNode(id="case",role="case",shape="rectangular_box",parameters=p,material_role="casework"))
        elif pt in ("bed","bed_headboard"):
            nodes.append(CADSceneNode(id="platform",role="platform",shape="rectangular_platform",parameters=p))
            nodes.append(CADSceneNode(id="headboard",role="headboard",shape="vertical_panel",parameters=p))
        views = [CADViewSpec(view_id="top",view_type="top"),CADViewSpec(view_id="front",view_type="front_elevation"),CADViewSpec(view_id="side",view_type="side_elevation")]
        return ParametricCADSceneGraph(product_type=pt,template_id=tpl,nodes=nodes,views=views,
            annotations=package.drawing_notes+package.manufacturing_notes,warnings=package.warnings,confidence=package.confidence)
