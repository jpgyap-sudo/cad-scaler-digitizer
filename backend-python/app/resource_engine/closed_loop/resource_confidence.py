"""Resource confidence engine — tracks usage and approval per resource."""
from statistics import mean
from typing import Dict, List
from .models import ReviewCase, ResourceScore


class ResourceConfidenceEngine:
    def update_scores(self, existing: List[ResourceScore], case: ReviewCase,
                      resource_ids: List[str]) -> List[ResourceScore]:
        scores: Dict[str, ResourceScore] = {s.resource_id: s for s in existing}
        for rid in resource_ids:
            if rid not in scores:
                scores[rid] = ResourceScore(resource_id=rid)
            scores[rid].used_count += 1
            if case.status == "accepted":
                scores[rid].approved_count += 1
            elif case.status == "rejected":
                scores[rid].rejected_count += 1
            elif case.status == "edited":
                scores[rid].edited_count += 1
            scores[rid].confidence = self._calc_confidence(scores[rid])
        return list(scores.values())

    def _calc_confidence(self, s: ResourceScore) -> float:
        if s.used_count == 0: return 0.5
        approvals = s.approved_count / max(s.used_count, 1)
        penalties = (s.rejected_count * 0.3 + s.edited_count * 0.1) / max(s.used_count, 1)
        return round(max(0.05, min(0.99, 0.5 + approvals * 0.5 - penalties)), 2)
