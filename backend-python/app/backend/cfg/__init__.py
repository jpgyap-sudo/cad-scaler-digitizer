# CFG — Canonical Furniture Graph package
# Everything reads from and writes to CFG. No more ad-hoc dicts.

from .canonical_furniture_graph import CanonicalFurnitureGraph
from .models import (
    BBox,
    BillOfMaterials,
    ComponentGeometry,
    ComponentNode,
    ComponentRelation,
    CorrectionRecord,
    FurnitureGraph,
    HardwareSpec,
    JointSpec,
    MaterialSpec,
    ProvenanceEntry,
    ScaleInfo,
    ViewSpec,
)

__all__ = [
    "FurnitureGraph",
    "ComponentNode",
    "ComponentRelation",
    "ComponentGeometry",
    "JointSpec",
    "MaterialSpec",
    "HardwareSpec",
    "BillOfMaterials",
    "ProvenanceEntry",
    "ScaleInfo",
    "CorrectionRecord",
    "BBox",
    "ViewSpec",
    "CanonicalFurnitureGraph",
]
