"""Parameter Pack Pipeline — VisionFeatures → CADParameterPack."""
from typing import Optional, Any
from .models import VisionFeatures, CADParameterPack
from .decomposer import GeometryDecomposer
from .estimator import DimensionEstimator
from .pack_builder import ParameterPackBuilder


class ParameterPackPipeline:
    """End-to-end pipeline: features → geometry → dimensions → parameter pack."""

    def __init__(self):
        self.decomposer = GeometryDecomposer()
        self.estimator = DimensionEstimator()
        self.builder = ParameterPackBuilder()

    def run(self, features: VisionFeatures) -> CADParameterPack:
        geometry = self.decomposer.decompose(features)
        dimensions = self.estimator.estimate(features, geometry)
        pack = self.builder.build(geometry, dimensions)
        return pack

    def run_from_dict(self, features_dict: dict) -> CADParameterPack:
        features = VisionFeatures(**features_dict)
        return self.run(features)
