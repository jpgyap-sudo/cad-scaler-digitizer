from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime


class GenerateRequest(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    product_type_hint: Optional[str] = None
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    known_dimensions_mm: Dict[str, Any] = {}
    material_hints: Dict[str, Any] = {}
    notes: List[str] = []


class Artifact(BaseModel):
    artifact_type: str
    path: str
    metadata: Dict[str, Any] = {}


class PipelineStageResult(BaseModel):
    stage: str
    status: str = "ok"
    output: Dict[str, Any] = {}
    warnings: List[str] = []


class GenerateResponse(BaseModel):
    job_id: str
    case_id: str
    status: str
    artifacts: List[Artifact] = []
    quality_score: float = 0.0
    warnings: List[str] = []


class JobRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = "created"
    request: Optional[GenerateRequest] = None
    stages: List[PipelineStageResult] = []
    response: Optional[GenerateResponse] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ReviewCorrection(BaseModel):
    field: str
    before: Any = None
    after: Any = None
    reason: str = ""


class ReviewActionRequest(BaseModel):
    reviewer: str = "engineer"
    comments: List[str] = []
    corrections: List[ReviewCorrection] = []
    corrected_parameters: Dict[str, Any] = {}
