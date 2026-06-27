"""Template ranking engine — scores template performance over time."""
from typing import Dict, List
from .models import ReviewCase, TemplateScore


class TemplateRankingEngine:
    def update_scores(self, existing: List[TemplateScore], case: ReviewCase) -> List[TemplateScore]:
        scores: Dict[str, TemplateScore] = {s.template_id: s for s in existing}
        tid = case.template_id
        if tid not in scores:
            scores[tid] = TemplateScore(template_id=tid)
        s = scores[tid]
        s.used_count += 1
        if case.status == "accepted":
            s.approved_count += 1
        elif case.status == "rejected":
            s.rejected_count += 1
        elif case.status == "edited":
            s.edited_count += 1
        if case.quality_summary:
            s.average_quality_score = round(
                (s.average_quality_score * (s.used_count - 1) + case.quality_summary.score) / max(s.used_count, 1), 2)
        s.confidence = round(max(0.05, min(0.99,
            0.5 + (s.approved_count / max(s.used_count, 1)) * 0.3
            - (s.rejected_count / max(s.used_count, 1)) * 0.2
            + s.average_quality_score * 0.2)), 2)
        return list(scores.values())
