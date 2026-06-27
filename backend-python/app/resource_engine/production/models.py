"""Production planning models — material, joinery, hardware, BOM, note pack."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class CADParameterPack(BaseModel):
    """Clean parameter pack consumed by CAD generator."""
    template_id: str
    product_type: str
    parameters: Dict[str, Any]
    components: Optional[List[Dict[str, Any]]] = None
    warnings: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)


class MaterialSpec(BaseModel):
    role: str
    material: str
    finish: Optional[str] = None
    thickness_mm: Optional[float] = None
    edge_treatment: Optional[str] = None
    notes: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)


class MaterialPlan(BaseModel):
    product_type: str
    materials: List[MaterialSpec]
    warnings: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)


class JoinerySpec(BaseModel):
    role: str
    method: str
    components: List[str] = []
    notes: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)


class JoineryPlan(BaseModel):
    product_type: str
    joinery: List[JoinerySpec]
    warnings: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)


class HardwareItem(BaseModel):
    item: str
    qty: int = 1
    size: Optional[str] = None
    material: Optional[str] = None
    purpose: Optional[str] = None
    notes: List[str] = []


class HardwarePlan(BaseModel):
    product_type: str
    hardware: List[HardwareItem]
    warnings: List[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)


class BOMItem(BaseModel):
    item_code: str
    description: str
    qty: float
    unit: str
    material: Optional[str] = None
    notes: List[str] = []


class BOM(BaseModel):
    product_type: str
    items: List[BOMItem]
    warnings: List[str] = []


class ShopDrawingNotePack(BaseModel):
    product_type: str
    general_notes: List[str]
    material_notes: List[str]
    joinery_notes: List[str]
    hardware_notes: List[str]
    warnings: List[str] = []
