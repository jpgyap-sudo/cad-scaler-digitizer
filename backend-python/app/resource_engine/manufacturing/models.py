"""Manufacturing planning models."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class CADParameterPack(BaseModel):
    template_id: str; product_type: str; parameters: Dict[str, Any]
    warnings: List[str] = []; confidence: float = Field(default=0.0, ge=0, le=1)

class MaterialSpec(BaseModel):
    role: str; material: str; finish: Optional[str] = None
    thickness_mm: Optional[float] = None; edge_treatment: Optional[str] = None; notes: List[str] = []

class JoinerySpec(BaseModel):
    role: str; method: str; components: List[str] = []; notes: List[str] = []

class HardwareItem(BaseModel):
    item: str; qty: int = 1; size: Optional[str] = None
    material: Optional[str] = None; purpose: Optional[str] = None; notes: List[str] = []

class ProductionStep(BaseModel):
    step_no: int; phase: str; task: str; station: str
    notes: List[str] = []; dependencies: List[int] = []

class CuttingItem(BaseModel):
    part_id: str; description: str; material: str; qty: int
    length_mm: Optional[float] = None; width_mm: Optional[float] = None
    thickness_mm: Optional[float] = None; notes: List[str] = []

class WeldItem(BaseModel):
    joint_id: str; description: str; process: str = "MIG/TIG"; notes: List[str] = []

class FinishItem(BaseModel):
    part_id: str; finish: str; prep: List[str] = []; notes: List[str] = []

class PackagingItem(BaseModel):
    item: str; method: str; notes: List[str] = []

class ManufacturingPlan(BaseModel):
    product_type: str; template_id: str
    production_steps: List[ProductionStep]; cutting_list: List[CuttingItem]
    weld_schedule: List[WeldItem] = []; finish_schedule: List[FinishItem] = []
    packaging_plan: List[PackagingItem] = []; risks: List[str] = []

class QCCheck(BaseModel):
    check_id: str; description: str; acceptance_criteria: str; stage: str

class QCChecklist(BaseModel):
    product_type: str; checks: List[QCCheck]

class ReadyForCADPackage(BaseModel):
    product_type: str; template_id: str; cad_parameters: Dict[str, Any]
    drawing_notes: List[str]; manufacturing_plan: ManufacturingPlan
    qc_checklist: QCChecklist; warnings: List[str] = []; confidence: float = Field(default=0.0, ge=0, le=1)
