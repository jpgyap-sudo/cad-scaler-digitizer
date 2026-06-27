"""Conflict resolver — merges agent findings into unified EngineeringDecision."""
from typing import List
from .models import (
    EngineeringContext, EngineeringDecision, AgentFinding,
    CloudVisionFeatureSet, RetrievalHit,
)


class ConflictResolver:
    """Merges findings from all agents into a single EngineeringDecision."""

    def resolve(self, context: EngineeringContext,
                findings: List[AgentFinding]) -> EngineeringDecision:
        f = context.features

        # Extract decisions from each agent
        geometry = {}
        dimensions = {}
        materials = {}
        joinery = {}
        all_warnings = []
        total_confidence = 0.0
        confidence_count = 0

        for af in findings:
            decisions = af.decisions or {}
            if af.category == "geometry":
                geometry = decisions
            elif af.category == "dimension":
                dimensions = decisions
            elif af.category == "material":
                materials = decisions
            elif af.category == "joinery":
                joinery = decisions
            elif af.category == "validation":
                joinery["validation_notes"] = decisions.get("notes", [])
            all_warnings.extend(af.warnings or [])
            if af.confidence > 0:
                total_confidence += af.confidence
                confidence_count += 1

        avg_confidence = round(total_confidence / max(confidence_count, 1), 2)

        return EngineeringDecision(
            product_type=f.product_type,
            subtype=f.subtype,
            geometry=geometry,
            dimensions_mm=dimensions,
            materials=materials,
            joinery=joinery,
            manufacturing_notes=f.construction_notes or [],
            validation_warnings=all_warnings,
            agent_findings=findings,
            confidence=avg_confidence,
        )
