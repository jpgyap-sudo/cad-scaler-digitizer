"""Phase 3C-3 — Production notes, BOM, material/joinery/hardware planning.
Takes CADParameterPack + material hints → MaterialPlan → JoineryPlan → HardwarePlan → BOM + NotePack.
"""
from .models import (
    CADParameterPack, MaterialSpec, MaterialPlan, JoinerySpec, JoineryPlan,
    HardwareItem, HardwarePlan, BOMItem, BOM, ShopDrawingNotePack,
)
from .agents import MaterialProductionAgent, JoineryProductionAgent, HardwareSelectionAgent, ManufacturingAgent
from .pipeline import ProductionPipeline
