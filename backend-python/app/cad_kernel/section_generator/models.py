from pydantic import BaseModel
from typing import Dict, List, Optional

class SectionPlane(BaseModel):
    id: str
    label: str
    orientation: str
    position_mm: float
    target_node_ids: List[str] = []
    reason: str = ""

class SectionDetail(BaseModel):
    id: str
    label: str
    section_plane_id: str
    drawing_scale: str = "1:5"
    cut_components: List[Dict] = []
    notes: List[str] = []

class SectionSet(BaseModel):
    sections: List[SectionPlane] = []
    details: List[SectionDetail] = []
    warnings: List[str] = []
    quality_score: float = 0
