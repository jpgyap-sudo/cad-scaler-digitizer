from app.cad_kernel.hidden_line.models import ViewEdge


class CenterlineGenerator:
    def generate_for_view(self, view):
        extra = []
        for edge in view.edges:
            role = edge.metadata.get("role", "")
            if edge.geometry_type == "circle" and role in ["support", "pedestal"]:
                data = edge.data
                cx = data.get("cx", 0)
                cy = data.get("cy", 0)
                r = data.get("r", 100)
                extra.append(ViewEdge(
                    id=f"{edge.id}_center_x",
                    source_entity_id=edge.source_entity_id,
                    role="centerline",
                    geometry_type="line",
                    data={"x1": cx - r * 1.2, "y1": cy, "x2": cx + r * 1.2, "y2": cy},
                    metadata={"role": "centerline"},
                ))
                extra.append(ViewEdge(
                    id=f"{edge.id}_center_y",
                    source_entity_id=edge.source_entity_id,
                    role="centerline",
                    geometry_type="line",
                    data={"x1": cx, "y1": cy - r * 1.2, "x2": cx, "y2": cy + r * 1.2},
                    metadata={"role": "centerline"},
                ))
        view.edges.extend(extra)
        return view
