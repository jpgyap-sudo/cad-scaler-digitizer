from __future__ import annotations
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class DimensionNode(BaseModel):
    id: str
    desc: str = ""
    value: float = 0.0
    unit: str = "mm"

class DimensionSet(BaseModel):
    dimensions: List[Dict[str, Any]] = []
    completeness: float = 0.0
