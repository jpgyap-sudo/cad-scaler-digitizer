from __future__ import annotations
from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field

Shape = Literal['circle', 'oval', 'rectangle', 'rounded_rectangle', 'square', 'irregular', 'unknown']
BaseType = Literal['four_legs', 'panel_legs', 'pedestal', 'truncated_cone', 'solid_block', 'sled', 'unknown']
ViewName = Literal['top', 'front', 'side', 'section', 'isometric']


class Component(BaseModel):
    id: str
    type: str
    label: str
    shape: Optional[str] = None
    material: Optional[str] = None
    finish: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    notes: List[str] = Field(default_factory=list)


class FurnitureAnalysis(BaseModel):
    product_name: Optional[str] = None
    category: str
    design_family: List[str] = Field(default_factory=list)
    top_shape: Shape = 'unknown'
    base_type: BaseType = 'unknown'
    components: List[Component] = Field(default_factory=list)
    relationships: Dict[str, Any] = Field(default_factory=dict)
    required_views: List[ViewName] = Field(default_factory=lambda: ['top','front','side'])
    assumptions: List[str] = Field(default_factory=list)
    uncertainty: Dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0, le=1)


class TemplateProposal(BaseModel):
    template_id: str
    template_name: str
    score: float = Field(ge=0, le=1)
    analysis: FurnitureAnalysis
    questions: List[Dict[str, Any]] = Field(default_factory=list)


class UserCorrection(BaseModel):
    field: str
    value: Any
    note: Optional[str] = None


class ApprovedTemplate(BaseModel):
    proposal: TemplateProposal
    corrections: List[UserCorrection] = Field(default_factory=list)
    final_analysis: FurnitureAnalysis
    parameters_mm: Dict[str, float] = Field(default_factory=dict)
