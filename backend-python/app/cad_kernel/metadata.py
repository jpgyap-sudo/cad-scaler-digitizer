from pydantic import BaseModel
from typing import Any, Dict, Optional


class EntityMetadata(BaseModel):
    material_role: Optional[str] = None
    material: Optional[str] = None
    finish: Optional[str] = None
    bom_ref: Optional[str] = None
    manufacturing_process: Optional[str] = None
    tolerance: Optional[str] = None
    extra: Dict[str, Any] = {}
