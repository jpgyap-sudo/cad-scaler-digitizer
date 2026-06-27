"""Engineering reasoning models — context, findings, decisions, messages."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime


class CloudVisionFeatureSet(BaseModel):
    """Features extracted from a photo by VLM."""
    product_type: str = "unknown"
    subtype: Optional[str] = None
    top_shape: Optional[str] = None
    support_type: Optional[str] = None
    material_top: Optional[str] = None
    material_base: Optional[str] = None
    upholstery_type: Optional[str] = None
    visible_parts: List[str] = []
    inferred_hidden_parts: List[str] = []
    construction_notes: List[str] = []
    style_keywords: List[str] = []
    approximate_dimensions_mm: Dict[str, Any] = {}
    confidence: float = Field(default=0.0, ge=0, le=1)


class RetrievalHit(BaseModel):
    id: str
    score: float = Field(default=0.0, ge=0, le=1)
    title: str = ""
    source_type: str = "resource"
    text: str = ""
    tags: List[str] = []
    metadata: Dict[str, Any] = {}


class EngineeringContext(BaseModel):
    features: CloudVisionFeatureSet
    retrieval_hits: List[RetrievalHit] = []
    project_type: str = "furniture_shopdrawing"
    units: str = "mm"


class AgentFinding(BaseModel):
    agent_name: str
    category: str
    summary: str
    decisions: Dict[str, Any] = {}
    confidence: float = Field(default=0.0, ge=0, le=1)
    warnings: List[str] = []
    evidence: List[str] = []
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AgentMessage(BaseModel):
    sender: str
    topic: str
    payload: Dict[str, Any]
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class EngineeringDecision(BaseModel):
    product_type: str
    subtype: Optional[str] = None
    geometry: Dict[str, Any] = {}
    dimensions_mm: Dict[str, Any] = {}
    materials: Dict[str, Any] = {}
    joinery: Dict[str, Any] = {}
    manufacturing_notes: List[str] = []
    validation_warnings: List[str] = []
    agent_findings: List[AgentFinding] = []
    confidence: float = Field(default=0.0, ge=0, le=1)
