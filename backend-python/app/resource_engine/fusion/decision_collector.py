"""Decision Collector — collects all decision candidates from agents."""
from typing import Dict, List
from .models import AgentOutput, DecisionValue


class DecisionCollector:
    def collect(self, outputs: List[AgentOutput]) -> Dict[str, List[DecisionValue]]:
        decisions: Dict[str, List[DecisionValue]] = {}
        for out in outputs:
            for key, value in out.values.items():
                if key not in decisions:
                    decisions[key] = []
                decisions[key].append(DecisionValue(
                    key=key, value=value, source=out.source,
                    confidence=out.confidence, priority=out.priority,
                    reason=f"From {out.source} ({out.category})",
                ))
        return decisions
