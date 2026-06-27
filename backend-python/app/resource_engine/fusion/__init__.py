"""Phase 3C-4C Decision Fusion — merges all agent outputs into one EngineeringDecisionPackage.
Highest priority: validation corrections > specs > manufacturing > dimensions > references > vision > defaults.
Outputs: EngineeringDecisionPackage + ParametricCADSceneGraph + AuditTrail.
"""
from .models import (DecisionValue, Conflict, AuditTrail, AgentOutput, EngineeringDecisionPackage,
                     CADSceneNode, CADViewSpec, ParametricCADSceneGraph)
from .decision_collector import DecisionCollector
from .conflict_resolver import ConflictResolver
from .package_builder import EngineeringPackageBuilder
from .scene_graph_builder import CADSceneGraphBuilder
from .pipeline import FusionPipeline
