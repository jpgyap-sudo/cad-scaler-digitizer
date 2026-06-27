"""Agent scheduler — runs agents sequentially with shared memory."""
from typing import List
from .models import EngineeringContext, AgentFinding
from .memory import SharedMemory, MessageBus
from .base_agent import BaseAgent


class AgentScheduler:
    def __init__(self, agents: List[BaseAgent]):
        self.agents = agents

    def run(self, context: EngineeringContext):
        memory = SharedMemory()
        bus = MessageBus(memory)

        findings = []
        for agent in self.agents:
            result = agent.run(context, memory, bus)
            finding = agent.finding(result)
            memory.add_finding(finding)
            findings.append(finding)

        return memory, findings
