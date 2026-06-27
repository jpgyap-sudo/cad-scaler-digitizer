from app.cad_kernel.document import CADDocument
from app.cad_kernel.entities.primitives import RectangleEntity, CircleEntity, TextEntity, BoxEntity, CylinderEntity
from app.cad_kernel.math.vector import Vec2, Vec3
from app.cad_kernel.metadata import EntityMetadata


class SceneGraphImporter:
    def import_scene(self, scene: dict, name: str = "Imported Scene") -> CADDocument:
        doc = CADDocument.create(name=name)

        for node in scene.get("nodes", []):
            role = node.get("role")
            shape = node.get("shape")
            p = node.get("parameters", {})
            material_role = node.get("material_role")
            visible = node.get("visible", True)
            layer = self._layer_for(role, visible)

            metadata = EntityMetadata(material_role=material_role, extra={"scene_node_id": node.get("id"), "role": role, "shape": shape})

            if shape in ["rectangular_slab", "rectangle", "rectangular_box"]:
                if role in ["top"]:
                    e = RectangleEntity(
                        name=node.get("id"),
                        center=Vec2(x=0, y=0),
                        width=p.get("length_mm", p.get("width_mm", 1000)),
                        height=p.get("depth_mm", p.get("height_mm", 500)),
                        layer=layer,
                        visible=visible,
                        metadata=metadata,
                        parameters=p,
                    )
                else:
                    e = BoxEntity(
                        name=node.get("id"),
                        center=Vec3(x=0, y=0, z=p.get("height_mm", 0)/2),
                        length=p.get("length_mm", 1000),
                        depth=p.get("depth_mm", 500),
                        height=p.get("height_mm", 500),
                        layer=layer,
                        visible=visible,
                        metadata=metadata,
                        parameters=p,
                    )

            elif shape == "cylinder":
                e = CylinderEntity(
                    name=node.get("id"),
                    center=Vec3(x=p.get("x_mm", 0), y=p.get("y_mm", 0), z=p.get("height_mm", 0)/2),
                    diameter=p.get("diameter_mm", 100),
                    height=p.get("height_mm", 500),
                    layer=layer,
                    visible=visible,
                    metadata=metadata,
                    parameters=p,
                )

            elif shape in ["rectangular_steel_frame", "rectangular_frame"]:
                e = RectangleEntity(
                    name=node.get("id"),
                    center=Vec2(x=0, y=0),
                    width=p.get("length_mm", 1000),
                    height=p.get("depth_mm", 500),
                    layer="HIDDEN",
                    visible=visible,
                    metadata=metadata,
                    parameters=p,
                )

            else:
                e = TextEntity(
                    name=node.get("id"),
                    insert=Vec2(x=0, y=0),
                    text=f"Unsupported node: {node.get('id')} {shape}",
                    layer="TEXT",
                    metadata=metadata,
                    parameters=p,
                )

            doc.add_entity(e)

        for i, note in enumerate(scene.get("annotations", [])[:20]):
            doc.add_entity(TextEntity(
                insert=Vec2(x=-1000, y=-1200 - i*60),
                text=note,
                height=35,
                layer="TEXT",
            ))

        return doc

    def _layer_for(self, role, visible=True):
        if not visible:
            return "HIDDEN"
        if role == "top":
            return "TOP"
        if role == "support":
            return "BASE"
        if role == "joinery":
            return "JOINERY"
        return "VISIBLE"
