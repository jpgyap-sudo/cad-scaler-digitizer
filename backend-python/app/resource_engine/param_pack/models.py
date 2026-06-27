"""Parameter Pack models."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class VisionFeatures(BaseModel):
    product_type: str
    subtype: Optional[str] = None
    top_shape: Optional[str] = None
    support_type: Optional[str] = None
    material_top: Optional[str] = None
    material_base: Optional[str] = None
    visible_parts: List[str] = []
    style_keywords: List[str] = []
    approximate_dimensions_mm: Dict[str, Any] = {}
    confidence: float = Field(default=0.0, ge=0, le=1)


class ComponentNode(BaseModel):
    id: str
    role: str
    shape: str
    quantity: int = 1
    visible: bool = True
    confidence: float = Field(default=0.0, ge=0, le=1)
    notes: List[str] = []


class GeometryPlan(BaseModel):
    product_type: str
    template_family: str
    components: List[ComponentNode]
    symmetry: str = "unknown"
    required_views: List[str] = ["top", "front", "side"]
    warnings: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)


class DimensionPlan(BaseModel):
    product_type: str
    dimensions_mm: Dict[str, Any]
    component_dimensions_mm: Dict[str, Dict[str, Any]] = {}
    assumptions: List[str] = []
    warnings: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)


class CADParameterPack(BaseModel):
    template_id: str
    product_type: str
    parameters: Dict[str, Any]
    components: List[ComponentNode]
    warnings: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)
