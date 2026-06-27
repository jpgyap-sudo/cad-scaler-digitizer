from pydantic import BaseModel
from typing import Dict, List, Optional

class DetailCandidate(BaseModel):
    id: str; detail_type: str; source_node_ids: List[str] = []
    priority: int = 50; reason: str = ""

class DetailView(BaseModel):
    detail_id: str; detail_type: str; label: str
    note: str = ""; scale: str = "1:2"; priority: int = 50

class DetailViewSet(BaseModel):
    details: List[DetailView] = []; quality_score: float = 0.0
