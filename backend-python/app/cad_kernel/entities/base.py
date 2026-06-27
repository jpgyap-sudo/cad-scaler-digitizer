from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from uuid import uuid4

from app.cad_kernel.math.transform import Transform
from app.cad_kernel.metadata import EntityMetadata


class BaseEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: str
    layer: str = "VISIBLE"
    name: Optional[str] = None
    parent_id: Optional[str] = None
    visible: bool = True
    transform: Transform = Transform()
    metadata: EntityMetadata = EntityMetadata()
    parameters: Dict[str, Any] = {}

    def bbox(self):
        return None
