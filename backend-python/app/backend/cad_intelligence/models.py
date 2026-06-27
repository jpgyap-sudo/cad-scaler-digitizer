from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional

Point = tuple[float, float]
BBox = tuple[float, float, float, float]

@dataclass
class OCRItem:
    text: str
    bbox: BBox
    confidence: float = 1.0

@dataclass
class OCRDimension:
    raw_text: str
    value: float
    unit: str
    value_mm: float
    kind: str
    bbox: BBox
    confidence: float = 1.0

@dataclass
class DetectedLine:
    id: str
    start: Point
    end: Point
    length_px: float
    angle_deg: float
    thickness: float = 1.0
    role: str = "unknown"
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class DetectedCircle:
    id: str
    center: Point
    radius_px: float
    role: str = "object_circle"
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class DimensionAssociation:
    dimension: OCRDimension
    target_id: Optional[str]
    target_type: Optional[str]
    measured_px: Optional[float]
    confidence: float
    reason: str

@dataclass
class ScaleSolution:
    mm_per_px: Optional[float]
    confidence: float
    samples: list[dict[str, Any]]
    rejected_samples: list[dict[str, Any]]
    reason: str

@dataclass
class CadEntity:
    id: str
    type: str
    geometry: dict[str, Any]
    source: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    layer: str = "OBJECT"
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class PipelineResult:
    dimensions: list[OCRDimension]
    lines: list[DetectedLine]
    circles: list[DetectedCircle]
    associations: list[DimensionAssociation]
    scale: ScaleSolution
    entities: list[CadEntity]
    debug: dict[str, Any]
