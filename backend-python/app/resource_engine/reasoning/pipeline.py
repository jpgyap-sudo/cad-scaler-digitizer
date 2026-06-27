"""Engineering pipeline — runs all agents, resolves conflicts, returns decision."""
import json
from pathlib import Path
from typing import List, Optional, Any

from .models import EngineeringContext, CloudVisionFeatureSet, RetrievalHit
from .agents import (
    GeometryAgent, DimensionAgent, MaterialAgent,
    JoineryAgent, ValidationAgent,
)
from .scheduler import AgentScheduler
from .resolver import ConflictResolver


class EngineeringPipeline:
    """Runs the multi-agent engineering reasoning pipeline.

    Input: CloudVisionFeatureSet + optional retrieval hits
    Output: EngineeringDecision + SharedMemory
    """

    def __init__(self, reasoning_client: Optional[Any] = None):
        self.agents = [
            GeometryAgent(reasoning_client),
            DimensionAgent(reasoning_client),
            MaterialAgent(reasoning_client),
            JoineryAgent(reasoning_client),
            ValidationAgent(reasoning_client),
        ]

    def run(self, features: CloudVisionFeatureSet,
            retrieval_hits: Optional[List[RetrievalHit]] = None):
        context = EngineeringContext(features=features, retrieval_hits=retrieval_hits or [])
        memory, findings = AgentScheduler(self.agents).run(context)
        decision = ConflictResolver().resolve(context, findings)
        return decision, memory

    def run_from_dict(self, features_dict: dict,
                      retrieval_hits: Optional[List[dict]] = None):
        features = CloudVisionFeatureSet(**features_dict)
        hits = [RetrievalHit(**h) for h in (retrieval_hits or [])]
        return self.run(features, hits)

    def save_outputs(self, decision, memory,
                     decision_path: str = "outputs/engineering_decision.json",
                     memory_path: str = "outputs/agent_memory.json"):
        Path(decision_path).parent.mkdir(parents=True, exist_ok=True)
        Path(memory_path).parent.mkdir(parents=True, exist_ok=True)
        Path(decision_path).write_text(decision.model_dump_json(indent=2))
        memory.save(memory_path)
        return decision_path, memory_path
