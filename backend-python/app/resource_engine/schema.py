"""Enhanced scene schema — ResourceHit, VisionFeatureSet, quality_score."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class VisionFeatureSet(BaseModel):
    """Features extracted from an image (by VLM or OCR+geometry pipeline)."""
    product_type: str = ""
    top_shape: Optional[str] = None
    support_type: Optional[str] = None
    material_top: Optional[str] = None
    material_base: Optional[str] = None
    symmetry: Optional[str] = None
    style_keywords: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)


class ResourceHit(BaseModel):
    """Evidence for why a resource was selected."""
    resource_id: str
    score: float = Field(ge=0, le=1)
    reason: str = ""


class SceneComponent(BaseModel):
    """A component in the scene graph (top, support, joinery, material)."""
    role: str
    resource_id: str
    parameters: Dict[str, Any] = {}
    confidence: float = Field(default=0.0, ge=0, le=1)


class ParametricSceneGraph(BaseModel):
    """Complete product description with all component references."""
    product_type: str
    drawing_type: str = "shopdrawing"
    style: str = "homeu_modern"
    units: str = "mm"
    components: List[SceneComponent]
    materials: List[SceneComponent] = []
    rules: List[str] = []
    resource_hits: List[ResourceHit] = []
    warnings: List[str] = []
    notes: List[str] = []
    quality_score: float = 0.0
