"""Phase 3E-0 — Template Graph Engine. 
Template-driven scene graph generation from FurnitureTemplate definitions.

Each archetype (table.dual_cylindrical_pedestal, sofa.three_seater, etc.)
is defined as a Template → Components → Parameters → Constraints → Views graph.
The engine instantiates a template from an EngineeringDecisionPackage.
"""
from .models import (FurnitureTemplate, TemplateParameter, TemplateComponent, TemplateConstraint,
                     TemplateInstance, CADSceneNode, CADViewSpec, ParametricCADSceneGraph,
                     EngineeringDecisionPackage)
from .template_library import TemplateLibrary
from .template_instantiator import TemplateInstantiator
from .scene_graph_builder import TemplateSceneGraphBuilder
from .pipeline import TemplateGraphPipeline
