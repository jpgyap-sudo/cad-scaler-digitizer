"""Decision fusion models — single engineering truth from multiple agent outputs."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime


class DecisionValue(BaseModel):
    key: str; value: Any; source: str
    confidence: float = Field(default=0.0, ge=0, le=1)
    priority: int = 50; reason: str = ""


class Conflict(BaseModel):
    key: str; candidates: List[DecisionValue]
    selected: DecisionValue; resolution_reason: str


class AuditEvent(BaseModel):
    event_type: str; message: str; data: Dict[str, Any] = {}
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AuditTrail(BaseModel):
    events: List[AuditEvent] = []
    def add(self, event_type: str, message: str, data: dict | None = None):
        self.events.append(AuditEvent(event_type=event_type, message=message, data=data or {}))


class AgentOutput(BaseModel):
    source: str; category: str; values: Dict[str, Any] = {}
    confidence: float = Field(default=0.0, ge=0, le=1)
    priority: int = 50; warnings: List[str] = []


class EngineeringDecisionPackage(BaseModel):
    product_type: str; template_id: str
    canonical_parameters: Dict[str, Any]
    geometry: Dict[str, Any] = {}; materials: Dict[str, Any] = {}
    joinery: Dict[str, Any] = {}; hardware: List[Dict[str, Any]] = []
    manufacturing_notes: List[str] = []; drawing_notes: List[str] = []
    warnings: List[str] = []; conflicts: List[Conflict] = []
    approved_for_drafting: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)


class CADSceneNode(BaseModel):
    id: str; role: str; shape: str; parameters: Dict[str, Any]
    material_role: Optional[str] = None; visible: bool = True


class CADViewSpec(BaseModel):
    view_id: str; view_type: str; required: bool = True; notes: List[str] = []


class ParametricCADSceneGraph(BaseModel):
    product_type: str; template_id: str; units: str = "mm"
    nodes: List[CADSceneNode]; views: List[CADViewSpec]
    annotations: List[str] = []; bom_refs: List[str] = []
    warnings: List[str] = []; confidence: float = Field(default=0.0, ge=0, le=1)
