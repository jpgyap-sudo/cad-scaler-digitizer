"""Phase 5 — Closed-Loop Learning System.
Tracks every generated drawing → review → correction → delta → confidence update → memory.

Integrates with: Quality Evaluator (3E-10), Resource Library, Template Graph, DB Persistence.

Persistence: Auto-saves to SQLite via db_persistence module, with JSON fallback.
Key models: ReviewCase, ResourceScore, TemplateScore, DecisionMemoryItem, LearningReport.
"""
from .models import (
    GeneratedArtifact, QualitySummary, Correction, ReviewCase,
    DeltaItem, DeltaReport, ResourceScore, TemplateScore,
    DecisionMemoryItem, LearningRecommendation, LearningReport,
)
from .delta_engine import DeltaEngine
from .resource_confidence import ResourceConfidenceEngine
from .template_ranking import TemplateRankingEngine
from .decision_memory import DecisionMemoryEngine
from .recommendation_engine import RecommendationEngine
from .pipeline import ClosedLoopPipeline
