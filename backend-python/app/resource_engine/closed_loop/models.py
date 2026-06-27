"""Closed-loop learning models — ReviewCase, Delta, Scores, Memory, Recommendations."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4


class GeneratedArtifact(BaseModel):
    artifact_type: str  # dxf, pdf, scene_graph, quality_report, image
    path: str; hash: Optional[str] = None; metadata: Dict[str, Any] = {}


class QualitySummary(BaseModel):
    score: float = Field(default=0.0, ge=0, le=1); passed: bool = False
    issues: List[Dict[str, Any]] = []


class Correction(BaseModel):
    field: str; before: Any = None; after: Any = None
    reason: str = ""; severity: str = "normal"; source: str = "engineer"


class ReviewCase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    product_id: str; product_type: str; template_id: str
    status: str = "generated"  # generated, accepted, edited, rejected, needs_more_info
    input_refs: List[GeneratedArtifact] = []
    generated_outputs: List[GeneratedArtifact] = []
    final_outputs: List[GeneratedArtifact] = []
    generated_parameters: Dict[str, Any] = {}
    corrected_parameters: Dict[str, Any] = {}
    quality_summary: Optional[QualitySummary] = None
    corrections: List[Correction] = []
    reviewer: Optional[str] = None; comments: List[str] = []
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DeltaItem(BaseModel):
    field: str; before: Any; after: Any; delta_type: str
    magnitude: Optional[float] = None; reason: str = ""


class DeltaReport(BaseModel):
    case_id: str; product_type: str; template_id: str
    deltas: List[DeltaItem] = []; summary: str = ""


class ResourceScore(BaseModel):
    resource_id: str; used_count: int = 0; approved_count: int = 0
    rejected_count: int = 0; edited_count: int = 0; confidence: float = 0.5


class TemplateScore(BaseModel):
    template_id: str; used_count: int = 0; approved_count: int = 0
    rejected_count: int = 0; edited_count: int = 0
    average_quality_score: float = 0.0; confidence: float = 0.5


class DecisionMemoryItem(BaseModel):
    decision_key: str; trigger: Dict[str, Any]; decision: Any
    reason: str; approved_count: int = 0; rejected_count: int = 0; confidence: float = 0.5


class LearningRecommendation(BaseModel):
    area: str; action: str; reason: str; confidence: float = Field(default=0.0, ge=0, le=1)


class LearningReport(BaseModel):
    case_id: str; recommendations: List[LearningRecommendation]
    updated_resource_scores: List[ResourceScore] = []
    updated_template_scores: List[TemplateScore] = []
    updated_decision_memory: List[DecisionMemoryItem] = []
