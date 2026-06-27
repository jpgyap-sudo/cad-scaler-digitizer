from .detector import GeometryDetector
from .strategies import DimensionStrategies
from .placement import DimensionPlacement
from .validator import DimensionValidator
from .models import DimensionSet

class Phase3E4Pipeline:
    def run(self,scene):
        nodes=GeometryDetector().detect(scene)
        dims=DimensionStrategies().build(nodes)
        dims=DimensionPlacement().arrange(dims)
        return DimensionSet(dimensions=dims,completeness=DimensionValidator().score(dims))
