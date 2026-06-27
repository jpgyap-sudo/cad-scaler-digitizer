"""Phase 3C-2 integration — Parameter Pack pipeline.
Produces a clean CADParameterPack from VisionFeatures.

Flow: VisionFeatures → GeometryDecomposer → GeometryPlan
                                     ↓
                           DimensionEstimator → DimensionPlan
                                     ↓
                           ParameterPackBuilder → CADParameterPack
                                     ↓
                           DXF Generator
"""
from .models import VisionFeatures, ComponentNode, GeometryPlan, DimensionPlan, CADParameterPack
from .decomposer import GeometryDecomposer
from .estimator import DimensionEstimator
from .pack_builder import ParameterPackBuilder
from .pipeline import ParameterPackPipeline
