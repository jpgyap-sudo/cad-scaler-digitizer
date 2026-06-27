"""Handoff models — BOM, cutting, schedules, notes, manifest, production packet."""
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


class CADSceneNode(BaseModel):
    id: str; role: str; shape: str; parameters: Dict[str, Any]
    material_role: Optional[str] = None; visible: bool = True


class ParametricCADSceneGraph(BaseModel):
    product_type: str; template_id: str; units: str = "mm"
    nodes: List[CADSceneNode]; annotations: List[str] = []
    warnings: List[str] = []; confidence: float = Field(default=0.0, ge=0, le=1)


class BOMLine(BaseModel):
    line_no: int; item_code: str; description: str; qty: float; unit: str
    material: Optional[str] = None; finish: Optional[str] = None; notes: List[str] = []


class CuttingLine(BaseModel):
    part_id: str; description: str; qty: int
    length_mm: Optional[float] = None; width_mm: Optional[float] = None
    thickness_mm: Optional[float] = None; material: Optional[str] = None
    edge_detail: Optional[str] = None; notes: List[str] = []


class ScheduleLine(BaseModel):
    item: str; description: str; qty: Optional[float] = None; notes: List[str] = []


class DrawingNotes(BaseModel):
    general_notes: List[str]; material_notes: List[str]
    fabrication_notes: List[str]; installation_notes: List[str]
    warnings: List[str] = []


class CADHandoffManifest(BaseModel):
    product_type: str; template_id: str; units: str = "mm"
    drawing_sheets: List[str]; required_views: List[str]
    required_details: List[str]; required_dimensions: List[str]
    annotation_layers: Dict[str, str]
    source_package_confidence: float; approved_for_drafting: bool


class ProductionPacket(BaseModel):
    product_type: str; template_id: str
    bom: List[BOMLine]; cutting_list: List[CuttingLine]
    hardware_schedule: List[ScheduleLine]; finish_schedule: List[ScheduleLine]
    fabrication_schedule: List[ScheduleLine]
    drawing_notes: DrawingNotes; cad_handoff: CADHandoffManifest
    warnings: List[str] = []; confidence: float = Field(default=0.0, ge=0, le=1)
