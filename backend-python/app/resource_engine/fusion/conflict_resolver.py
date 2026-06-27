"""Conflict Resolver — resolves conflicts by priority then confidence."""
from typing import Any, Dict, List, Tuple
from .models import DecisionValue, Conflict, AuditTrail


class ConflictResolver:
    def resolve(self, decisions: Dict[str, List[DecisionValue]], audit: AuditTrail
                ) -> Tuple[Dict[str, Any], List[Conflict]]:
        final = {}; conflicts = []
        for key, candidates in decisions.items():
            selected = sorted(candidates, key=lambda c: (c.priority, c.confidence), reverse=True)[0]
            final[key] = selected.value
            if len({str(c.value) for c in candidates}) > 1:
                c = Conflict(key=key, candidates=candidates, selected=selected,
                             resolution_reason=f"Priority {selected.priority} / Confidence {selected.confidence} from {selected.source}")
                conflicts.append(c)
                audit.add("conflict_resolved", f"Resolved {key}", c.model_dump())
            else:
                audit.add("decision", f"{key}={selected.value}", {"source": selected.source, "confidence": selected.confidence})
        return final, conflicts
