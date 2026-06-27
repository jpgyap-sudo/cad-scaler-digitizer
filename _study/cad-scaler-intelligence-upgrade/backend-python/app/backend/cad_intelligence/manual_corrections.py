from __future__ import annotations
from .models import PipelineResult

def apply_manual_corrections(result: PipelineResult, corrections: list[dict]) -> PipelineResult:
    line_by_id = {line.id: line for line in result.lines}
    entity_by_id = {entity.id: entity for entity in result.entities}

    for c in corrections:
        action = c.get("action")
        if action == "set_line_role":
            line_id = c.get("line_id")
            role = c.get("role")
            if line_id in line_by_id and role:
                line_by_id[line_id].role = role
                line_by_id[line_id].confidence = 0.98
                line_by_id[line_id].metadata["manual_correction"] = True
        elif action == "confirm_scale":
            mm_per_px = c.get("mm_per_px")
            if mm_per_px and mm_per_px > 0:
                result.scale.mm_per_px = float(mm_per_px)
                result.scale.confidence = 0.99
                result.scale.reason = "User-confirmed scale"
        elif action == "set_entity_confidence":
            entity_id = c.get("entity_id")
            confidence = c.get("confidence")
            if entity_id in entity_by_id and confidence is not None:
                entity_by_id[entity_id].confidence = float(confidence)
                entity_by_id[entity_id].metadata["manual_correction"] = True
    return result
