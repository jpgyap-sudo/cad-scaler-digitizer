"""Shared memory and message bus for inter-agent communication."""
import json
from pathlib import Path
from typing import List
from .models import AgentFinding, AgentMessage


class SharedMemory:
    """Stores agent findings and enables inter-agent communication."""

    def __init__(self):
        self.findings: List[AgentFinding] = []
        self.messages: List[AgentMessage] = []

    def add_finding(self, finding: AgentFinding):
        self.findings.append(finding)

    def add_message(self, message: AgentMessage):
        self.messages.append(message)

    def findings_by_category(self, category: str) -> List[AgentFinding]:
        return [f for f in self.findings if f.category == category]

    def dump(self) -> dict:
        return {
            "findings": [f.model_dump() for f in self.findings],
            "messages": [m.model_dump() for m in self.messages],
        }

    def save(self, path: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.dump(), indent=2), encoding="utf-8")
        return str(p)


class MessageBus:
    """Allows agents to broadcast and read messages during the pipeline run."""

    def __init__(self, memory: SharedMemory):
        self.memory = memory

    def broadcast(self, sender: str, topic: str, payload: dict):
        self.memory.add_message(AgentMessage(sender=sender, topic=topic, payload=payload))

    def read(self, topic: str) -> List[AgentMessage]:
        return [m for m in self.memory.messages if m.topic == topic]
