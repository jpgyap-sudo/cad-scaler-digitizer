from app.cad_kernel.spatial_index import SpatialIndex


class SceneEvaluator:
    def evaluate(self, document):
        index = SpatialIndex().build(document.entities.values())
        warnings = []

        if not document.entities:
            warnings.append("Document has no entities.")

        visible = [e for e in document.entities.values() if e.visible]
        if not visible:
            warnings.append("Document has no visible entities.")

        document.history.append({
            "event": "scene_evaluated",
            "entity_count": len(document.entities),
            "spatial_items": len(index.items),
            "warnings": warnings,
        })
        return {"warnings": warnings, "entity_count": len(document.entities)}
