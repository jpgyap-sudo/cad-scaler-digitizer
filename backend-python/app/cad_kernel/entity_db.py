from app.cad_kernel.document import CADDocument


class EntityDB:
    def __init__(self, document: CADDocument):
        self.document = document

    def add(self, entity):
        return self.document.add_entity(entity)

    def get(self, entity_id: str):
        return self.document.entities[entity_id]

    def by_layer(self, layer: str):
        return [e for e in self.document.entities.values() if e.layer == layer]

    def by_type(self, entity_type: str):
        return [e for e in self.document.entities.values() if e.entity_type == entity_type]

    def all(self):
        return list(self.document.entities.values())
