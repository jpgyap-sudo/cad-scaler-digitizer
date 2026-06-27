from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class ViewEdge(BaseModel):
    id: str
    source_entity_id: str
    role: str = "edge"
    geometry_type: str = "line"  # line, circle, polyline
    data: Dict[str, Any]
    depth: float = 0
    visible: bool = True
    metadata: Dict[str, Any] = {}


class ClassifiedEdge(BaseModel):
    id: str
    source_entity_id: str
    line_class: str  # visible, hidden, centerline, silhouette, construction
    layer: str
    linetype: str
    lineweight: int = 25
    data: Dict[str, Any]
    reason: str = ""


class DrawingView(BaseModel):
    view_id: str
    view_type: str
    edges: List[ViewEdge]
    metadata: Dict[str, Any] = {}


class HiddenLineResult(BaseModel):
    view_id: str
    view_type: str
    classified_edges: List[ClassifiedEdge]
    warnings: List[str] = []
    quality_score: float = Field(default=0.0, ge=0, le=1)
