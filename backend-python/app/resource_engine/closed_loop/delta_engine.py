"""Delta engine — compares generated vs corrected parameters."""
from typing import Any, Dict, List, Tuple
from .models import ReviewCase, DeltaItem, DeltaReport


class DeltaEngine:
    def compare(self, case: ReviewCase) -> DeltaReport:
        deltas = []
        gen = case.generated_parameters or {}
        cor = case.corrected_parameters or {}
        all_keys = set(gen.keys()) | set(cor.keys())
        for key in sorted(all_keys):
            before = gen.get(key)
            after = cor.get(key)
            if before != after:
                delta_type = self._delta_type(before, after)
                magnitude = None
                if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                    magnitude = round(abs(float(after) - float(before)), 1)
                deltas.append(DeltaItem(
                    field=key, before=before, after=after,
                    delta_type=delta_type, magnitude=magnitude,
                    reason=f"{key}: {before} → {after}",
                ))
        summary = f"{len(deltas)} parameter{'s' if len(deltas)!=1 else ''} changed"
        return DeltaReport(case_id=case.id, product_type=case.product_type,
                           template_id=case.template_id, deltas=deltas, summary=summary)

    def _delta_type(self, before, after) -> str:
        if before is None: return "added"
        if after is None: return "removed"
        if isinstance(before, str) and isinstance(after, str): return "text_change"
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            return "value_change"
        return "type_change"
