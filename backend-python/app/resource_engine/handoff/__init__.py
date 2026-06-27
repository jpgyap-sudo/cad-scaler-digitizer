"""Phase 3C-4D — Manufacturing Output + CAD Handoff.
Bridges engineering intelligence → CAD drafting engine.

Generates: BOM, Cutting List, Hardware/Finish/Fabrication Schedules, 
Drawing Notes, CADHandoffManifest → ProductionPacket.
"""
from .models import (
    EngineeringDecisionPackage, CADSceneNode, ParametricCADSceneGraph,
    BOMLine, CuttingLine, ScheduleLine, DrawingNotes,
    CADHandoffManifest, ProductionPacket,
)
from .generators import BOMGenerator, CuttingListGenerator, ScheduleGenerator, DrawingNotesGenerator, CADHandoffManifestGenerator
from .pipeline import OutputPipeline
