"""Template Graph models."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class EngineeringDecisionPackage(BaseModel):
    product_type: str; template_id: str; canonical_parameters: Dict[str, Any]
    geometry: Dict[str, Any] = {}; materials: Dict[str, Any] = {}
    joinery: Dict[str, Any] = {}; hardware: List[Dict[str, Any]] = []
    manufacturing_notes: List[str] = []; drawing_notes: List[str] = []
    warnings: List[str] = []; approved_for_drafting: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)


class TemplateParameter(BaseModel):
    name: str; default: Any; min_value: Optional[float] = None
    max_value: Optional[float] = None; unit: str = "mm"; description: str = ""


class TemplateComponent(BaseModel):
    id: str; role: str; shape: str; required: bool = True; visible: bool = True
    material_role: Optional[str] = None; parameter_map: Dict[str, str] = {}; notes: List[str] = []


class TemplateConstraint(BaseModel):
    id: str; description: str; expression: str; severity: str = "warning"


class FurnitureTemplate(BaseModel):
    id: str; name: str; product_type: str; family: str
    parameters: List[TemplateParameter]; components: List[TemplateComponent]
    constraints: List[TemplateConstraint] = []
    required_views: List[str] = ["top", "front_elevation", "side_elevation"]
    required_details: List[str] = []; drawing_notes: List[str] = []


class TemplateInstance(BaseModel):
    template_id: str; product_type: str; resolved_parameters: Dict[str, Any]
    components: List[TemplateComponent]; constraints: List[TemplateConstraint]
    required_views: List[str]; required_details: List[str]; drawing_notes: List[str]
    warnings: List[str] = []; confidence: float = Field(default=0.0, ge=0, le=1)


class CADSceneNode(BaseModel):
    id: str; role: str; shape: str; parameters: Dict[str, Any]
    material_role: Optional[str] = None; visible: bool = True; notes: List[str] = []


class CADViewSpec(BaseModel):
    view_id: str; view_type: str; required: bool = True; notes: List[str] = []


class ParametricCADSceneGraph(BaseModel):
    product_type: str; template_id: str; units: str = "mm"
    nodes: List[CADSceneNode]; views: List[CADViewSpec]; details: List[str]
    annotations: List[str] = []; warnings: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)
