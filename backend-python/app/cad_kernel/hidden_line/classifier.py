from app.cad_kernel.hidden_line.models import ViewEdge, ClassifiedEdge
from app.cad_kernel.hidden_line.rules.line_styles import LINE_STYLES


class EdgeClassifier:
    def classify(self, edge: ViewEdge) -> ClassifiedEdge:
        line_class = self._class_for(edge)
        style = LINE_STYLES[line_class]

        return ClassifiedEdge(
            id=edge.id,
            source_entity_id=edge.source_entity_id,
            line_class=line_class,
            layer=style["layer"],
            linetype=style["linetype"],
            lineweight=style["lineweight"],
            data=edge.data,
            reason=self._reason(edge, line_class),
        )

    def _class_for(self, edge: ViewEdge) -> str:
        role = edge.role.lower()
        meta = {k.lower(): str(v).lower() for k, v in edge.metadata.items()}

        if "center" in role or meta.get("role") == "centerline":
            return "centerline"

        if edge.visible is False:
            return "hidden"

        if meta.get("visible") == "false":
            return "hidden"

        if meta.get("role") in ["joinery", "hidden_frame", "internal_frame"]:
            return "hidden"

        if edge.geometry_type == "circle" and meta.get("role") in ["support", "pedestal"]:
            return "silhouette"

        if "construction" in role:
            return "construction"

        if meta.get("silhouette") == "true":
            return "silhouette"

        return "visible"

    def _reason(self, edge: ViewEdge, line_class: str) -> str:
        if line_class == "hidden":
            return "Edge belongs to hidden/internal component or visibility=false."
        if line_class == "centerline":
            return "Centerline edge detected by role/metadata."
        if line_class == "silhouette":
            return "Silhouette outline detected."
        if line_class == "construction":
            return "Construction/reference edge."
        return "Default visible edge."
