"""Base agent class — all engineering agents inherit from this."""
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from .models import EngineeringContext, AgentFinding
from .memory import SharedMemory, MessageBus


class BaseAgent(ABC):
    name = "base_agent"
    category = "base"

    def __init__(self, reasoning_client: Optional[Any] = None):
        self.reasoning_client = reasoning_client

    @abstractmethod
    def run(self, context: EngineeringContext, memory: SharedMemory,
            bus: MessageBus) -> AgentFinding:
        raise NotImplementedError

    def context_json(self, context: EngineeringContext, memory: SharedMemory) -> str:
        payload = {
            "context": context.model_dump(),
            "existing_findings": [f.model_dump() for f in memory.findings],
        }
        return json.dumps(payload, indent=2)

    def cloud_or_rules(self, prompt: str, fallback_func: Callable) -> Dict[str, Any]:
        if self.reasoning_client:
            try:
                return self.reasoning_client.complete_json(prompt)
            except Exception as e:
                data = fallback_func()
                data.setdefault("warnings", []).append(f"Cloud failed; used rules: {e}")
                return data
        return fallback_func()

    def finding(self, data: dict) -> AgentFinding:
        return AgentFinding(
            agent_name=self.name, category=self.category,
            summary=data.get("summary", ""),
            decisions=data.get("decisions", {}),
            confidence=float(data.get("confidence", 0.5)),
            warnings=data.get("warnings", []),
            evidence=data.get("evidence", []),
        )
