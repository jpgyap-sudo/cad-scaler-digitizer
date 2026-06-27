"""Multi-Agent Engineering Reasoning Framework — specialized sub-agents that 
collaborate via shared memory to produce a unified EngineeringDecision.

Each agent makes ONE kind of decision (geometry, dimension, material, joinery, 
validation), then the conflict resolver merges them into a single decision.

Architecture:
    CloudVisionFeatureSet + RetrievalHits
        ↓
    AgentScheduler runs 5 agents with shared memory + message bus
        ↓
    ConflictResolver produces unified EngineeringDecision
        ↓
    Scene Graph / CAD Generator
"""
from .pipeline import EngineeringPipeline
from .models import EngineeringContext, EngineeringDecision, AgentFinding, CloudVisionFeatureSet
