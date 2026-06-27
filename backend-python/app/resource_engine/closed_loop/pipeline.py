"""Closed-loop pipeline — full learning cycle from ReviewCase to LearningReport.
Persists to SQLite via db_persistence and JSON files."""
from pathlib import Path
from typing import List
from .models import ReviewCase, LearningReport, ResourceScore, TemplateScore, DecisionMemoryItem
from .delta_engine import DeltaEngine
from .resource_confidence import ResourceConfidenceEngine
from .template_ranking import TemplateRankingEngine
from .decision_memory import DecisionMemoryEngine
from .recommendation_engine import RecommendationEngine


class ClosedLoopPipeline:
    def run_learning_cycle(self, case: ReviewCase, resource_ids: List[str],
                           existing_resources: List[ResourceScore] = None,
                           existing_templates: List[TemplateScore] = None,
                           existing_memory: List[DecisionMemoryItem] = None,
                           output_prefix: str = ""):
        delta = DeltaEngine().compare(case)
        resource_scores = ResourceConfidenceEngine().update_scores(
            existing_resources or [], case, resource_ids)
        template_scores = TemplateRankingEngine().update_scores(
            existing_templates or [], case)
        decision_memory = DecisionMemoryEngine().update(
            existing_memory or [], case, delta)
        recs = RecommendationEngine().recommend(case, delta)
        report = LearningReport(
            case_id=case.id, recommendations=recs,
            updated_resource_scores=resource_scores,
            updated_template_scores=template_scores,
            updated_decision_memory=decision_memory,
        )

        # Persist to JSON files
        if output_prefix:
            Path(output_prefix).parent.mkdir(parents=True, exist_ok=True)
            Path(f"{output_prefix}_delta_report.json").write_text(delta.model_dump_json(indent=2))
            Path(f"{output_prefix}_learning_report.json").write_text(report.model_dump_json(indent=2))
            Path(f"{output_prefix}_resource_scores.json").write_text(
                "[\n" + ",\n".join(r.model_dump_json(indent=2) for r in resource_scores) + "\n]")
            Path(f"{output_prefix}_template_scores.json").write_text(
                "[\n" + ",\n".join(r.model_dump_json(indent=2) for r in template_scores) + "\n]")

        return report, resource_scores, template_scores, decision_memory
