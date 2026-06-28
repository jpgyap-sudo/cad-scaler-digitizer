# CFG — Canonical Furniture Graph package
# Everything reads from and writes to CFG. No more ad-hoc dicts.

from .models import (
    FurnitureGraph,
    ComponentNode,
    ComponentRelation,
    ComponentGeometry,
    JointSpec,
    MaterialSpec,
    HardwareSpec,
    BillOfMaterials,
    ProvenanceEntry,
    ScaleInfo,
    CorrectionRecord,
    BBox,
    ViewSpec,
)
from .canonical_furniture_graph import CanonicalFurnitureGraph

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
