"""Scene Graph Builder — builds CAD scene graph from template instance."""
from .models import TemplateInstance, ParametricCADSceneGraph, CADSceneNode, CADViewSpec


class TemplateSceneGraphBuilder:
    def build(self, instance: TemplateInstance) -> ParametricCADSceneGraph:
        p = instance.resolved_parameters
        nodes = []
        for c in instance.components:
            comp_params = {}
            for template_param_key, param_name in c.parameter_map.items():
                val = p.get(param_name, p.get(template_param_key))
                if val is not None:
                    comp_params[template_param_key] = val
            nodes.append(CADSceneNode(
                id=c.id, role=c.role, shape=c.shape,
                parameters=comp_params or p,
                material_role=c.material_role,
                visible=c.visible, notes=c.notes,
            ))
        views = [CADViewSpec(view_id=v, view_type=v) for v in instance.required_views]
        return ParametricCADSceneGraph(
            product_type=instance.product_type,
            template_id=instance.template_id,
            nodes=nodes, views=views,
            details=instance.required_details,
            annotations=instance.drawing_notes,
            warnings=instance.warnings,
            confidence=instance.confidence,
        )
