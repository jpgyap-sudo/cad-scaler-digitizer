from __future__ import annotations
from .models import CadEntity, DimensionAssociation

def apply_dimension_evidence(entities: list[CadEntity], associations: list[DimensionAssociation]) -> list[CadEntity]:
    association_by_target = {assoc.target_id: assoc for assoc in associations if assoc.target_id}
    for entity in entities:
        matched = None
        for evidence_id in entity.evidence:
            if evidence_id in association_by_target:
                matched = association_by_target[evidence_id]
                break
        if matched:
            entity.source = "ocr_associated"
            entity.confidence = min(0.98, max(entity.confidence, matched.confidence + 0.12))
            entity.evidence.append(matched.dimension.raw_text)
            entity.metadata["dimension_text"] = matched.dimension.raw_text
            entity.metadata["dimension_value_mm"] = matched.dimension.value_mm
            entity.metadata["dimension_association_confidence"] = matched.confidence
    return entities

def confidence_summary(entities: list[CadEntity]) -> dict:
    if not entities:
        return {"average": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
    high = [e for e in entities if e.confidence >= 0.75]
    medium = [e for e in entities if 0.45 <= e.confidence < 0.75]
    low = [e for e in entities if e.confidence < 0.45]
    return {
        "average": sum(e.confidence for e in entities) / len(entities),
        "high": len(high),
        "medium": len(medium),
        "low": len(low),
        "total": len(entities),
    }
