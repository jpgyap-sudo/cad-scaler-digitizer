"""Phase 3C-4A — Manufacturing Planner. Assembly, cutting, welding, finishing, QC, packaging.
Takes CADParameterPack + MaterialSpecs → ManufacturingPlan → ReadyForCADPackage.
"""
from .models import (
    CADParameterPack, MaterialSpec, JoinerySpec, HardwareItem,
    ProductionStep, CuttingItem, WeldItem, FinishItem, PackagingItem,
    ManufacturingPlan, QCCheck, QCChecklist, ReadyForCADPackage,
)
from .agents import AssemblyPlanner, CuttingPlanner, WeldFinishPackagingPlanner, QCAgent
from .pipeline import ManufacturingPipeline
