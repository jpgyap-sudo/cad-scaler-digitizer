"""Output pipeline — generates ProductionPacket from EngineeringDecisionPackage + Scene."""
from typing import Any, Tuple
from .models import EngineeringDecisionPackage, ParametricCADSceneGraph, ProductionPacket
from .generators import (BOMGenerator, CuttingListGenerator, ScheduleGenerator,
                          DrawingNotesGenerator, CADHandoffManifestGenerator)


class OutputPipeline:
    def run(self, package: EngineeringDecisionPackage, scene: ParametricCADSceneGraph) -> ProductionPacket:
        bom = BOMGenerator().generate(package, scene)
        cutting = CuttingListGenerator().generate(package, scene)
        sched = ScheduleGenerator()
        handoff = CADHandoffManifestGenerator().generate(package, scene)
        notes = DrawingNotesGenerator().generate(package)
        packet = ProductionPacket(
            product_type=package.product_type, template_id=package.template_id,
            bom=bom, cutting_list=cutting,
            hardware_schedule=sched.hardware(package),
            finish_schedule=sched.finish(package, scene),
            fabrication_schedule=sched.fabrication(package),
            drawing_notes=notes, cad_handoff=handoff,
            warnings=sorted(set(package.warnings + scene.warnings)),
            confidence=package.confidence,
        )
        return packet
