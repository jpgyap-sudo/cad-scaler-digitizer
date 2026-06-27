"""Recommendation engine — generates learning recommendations from deltas + status."""
from typing import List
from .models import ReviewCase, DeltaReport, LearningRecommendation


class RecommendationEngine:
    def recommend(self, case: ReviewCase, delta: DeltaReport) -> List[LearningRecommendation]:
        recs = []
        if case.status == "rejected":
            recs.append(LearningRecommendation(
                area="template", action=f"Review template {case.template_id} for {case.product_type}",
                reason="Drawing was rejected by reviewer.", confidence=0.7))
        if case.status == "edited" and len(delta.deltas) > 0:
            recs.append(LearningRecommendation(
                area="parameters", action=f"Update default parameters for {case.product_type}",
                reason=f"{len(delta.deltas)} parameters were edited.", confidence=0.65))
        if case.status == "accepted":
            recs.append(LearningRecommendation(
                area="template", action=f"Reinforce template {case.template_id}",
                reason="Drawing was approved.", confidence=0.9))
        if not recs:
            recs.append(LearningRecommendation(
                area="monitor", action=f"Review case {case.id}",
                reason="No automatic recommendation.", confidence=0.3))
        return recs
