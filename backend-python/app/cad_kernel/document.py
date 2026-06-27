from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List, Any
from uuid import uuid4

from app.cad_kernel.entities.base import BaseEntity
from app.cad_kernel.layers import LayerManager, Layer


class CADDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Untitled CAD Document"
    units: str = "mm"
    entities: Dict[str, BaseEntity] = {}
    layers: Dict[str, Layer] = {}
    blocks: Dict[str, List[str]] = {}
    constraints: List[Dict[str, Any]] = []
    history: List[Dict[str, Any]] = []

    model_config = {"arbitrary_types_allowed": True}

    def add_entity(self, entity: BaseEntity):
        self.entities[entity.id] = entity
        self.history.append({"event": "entity_added", "entity_id": entity.id, "type": entity.entity_type})
        return entity

    def add_constraint(self, constraint: dict):
        self.constraints.append(constraint)
        self.history.append({"event": "constraint_added", "constraint": constraint})

    def create_block(self, name: str, entity_ids: list[str]):
        self.blocks[name] = entity_ids
        self.history.append({"event": "block_created", "name": name, "entity_ids": entity_ids})

    @classmethod
    def create(cls, name: str = "CAD Document"):
        lm = LayerManager()
        return cls(name=name, layers=lm.layers)
