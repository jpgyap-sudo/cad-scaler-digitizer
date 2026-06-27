"""Template Graph Pipeline — loads template → instantiates → builds scene graph."""
from typing import Tuple
from .models import EngineeringDecisionPackage, TemplateInstance, ParametricCADSceneGraph
from .template_library import TemplateLibrary
from .template_instantiator import TemplateInstantiator
from .scene_graph_builder import TemplateSceneGraphBuilder


class TemplateGraphPipeline:
    def __init__(self, template_root: str = "resources/furniture_template_graphs"):
        self.library = TemplateLibrary(template_root).load()

    def run(self, package: EngineeringDecisionPackage) -> Tuple[TemplateInstance, ParametricCADSceneGraph]:
        instance = TemplateInstantiator(self.library).instantiate(package)
        scene = TemplateSceneGraphBuilder().build(instance)
        return instance, scene
