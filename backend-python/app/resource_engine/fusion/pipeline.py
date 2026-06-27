"""Fusion pipeline — collects, resolves, packages, builds scene graph."""
from typing import Dict, List, Optional, Any
from .models import AgentOutput, AuditTrail
from .decision_collector import DecisionCollector
from .conflict_resolver import ConflictResolver
from .package_builder import EngineeringPackageBuilder
from .scene_graph_builder import CADSceneGraphBuilder


class FusionPipeline:
    """Fuses multiple agent outputs into one EngineeringDecisionPackage + ParametricCADSceneGraph."""
    def __init__(self):
        self.collector = DecisionCollector()
        self.resolver = ConflictResolver()
        self.pkg_builder = EngineeringPackageBuilder()
        self.scene_builder = CADSceneGraphBuilder()

    def run(self, product_type: str, template_id: str,
            outputs: List[AgentOutput], validation=None,
            output_prefix: str = ""):
        audit = AuditTrail()
        audit.add("fusion_started", f"Fusing {len(outputs)} outputs", {"product_type": product_type})
        decisions = self.collector.collect(outputs)
        audit.add("collected", f"{len(decisions)} decision keys", {"keys": list(decisions.keys())})
        flat_final, conflicts = self.resolver.resolve(decisions, audit)
        package = self.pkg_builder.build(product_type, template_id, flat_final, conflicts, outputs, validation)
        scene = self.scene_builder.build(package)
        return package, scene, audit
