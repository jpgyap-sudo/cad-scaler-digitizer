"""Phase 3E-1 CAD Kernel — geometric kernel for parametric CAD document generation.
Entity types → CADDocument → ConstraintEngine → Evaluator → JSON/DXF export.
"""
from .document import CADDocument
from .entities.primitives import (
    LineEntity, PolylineEntity, CircleEntity, RectangleEntity, TextEntity, BoxEntity, CylinderEntity,
)
from .entities.base import BaseEntity
from .layers import LayerManager, Layer
from .constraints import ConstraintEngine
from .evaluator import SceneEvaluator
from .exporters.dxf_exporter import DXFExporter
from .exporters.json_exporter import JSONExporter
from .importers.scene_graph_importer import SceneGraphImporter
from .pipeline import Phase3E1CADKernelPipeline as CADKernelPipeline
