from app.cad_kernel.document import CADDocument


class BlockManager:
    def __init__(self, document: CADDocument):
        self.document = document

    def create_component_block(self, name: str, entities):
        ids = [e.id for e in entities]
        self.document.create_block(name, ids)
        return ids
