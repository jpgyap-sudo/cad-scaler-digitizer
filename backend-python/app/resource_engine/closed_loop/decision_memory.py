"""Decision memory — records engineering decisions for replay and analysis."""
from typing import Dict, List
from .models import ReviewCase, DeltaReport, DecisionMemoryItem


class DecisionMemoryEngine:
    def update(self, existing: List[DecisionMemoryItem], case: ReviewCase,
               delta: DeltaReport) -> List[DecisionMemoryItem]:
        memory: Dict[str, DecisionMemoryItem] = {m.decision_key: m for m in existing}
        for d in delta.deltas:
            key = f"{case.product_type}.{d.field}"
            if key not in memory:
                memory[key] = DecisionMemoryItem(
                    decision_key=key,
                    trigger={"product_type": case.product_type, "field": d.field,
                             "delta_type": d.delta_type, "magnitude": d.magnitude},
                    decision=d.after, reason=d.reason,
                )
            mem = memory[key]
            if case.status == "accepted":
                mem.approved_count += 1
            elif case.status == "rejected":
                mem.rejected_count += 1
        for mem in memory.values():
            total = mem.approved_count + mem.rejected_count
            mem.confidence = round(max(0.05, min(0.99,
                0.5 + (mem.approved_count / max(total, 1)) * 0.3 - (mem.rejected_count / max(total, 1)) * 0.2)), 2)
        return list(memory.values())
