class ConstraintEngine:
    def apply(self, document):
        # This is the first version: records constraints but does not solve complex geometry yet.
        # Future versions should implement coincident, equal, offset, center, parallel, etc.
        document.history.append({"event": "constraints_evaluated", "count": len(document.constraints)})
        return document

    def add_center_constraint(self, document, child_id: str, parent_id: str):
        document.add_constraint({"type": "center", "child_id": child_id, "parent_id": parent_id})

    def add_offset_constraint(self, document, entity_id: str, offset_mm: float):
        document.add_constraint({"type": "offset", "entity_id": entity_id, "offset_mm": offset_mm})
