"""Production pipeline — material plan → joinery plan → hardware → BOM → note pack."""
from typing import Dict, Optional
from .models import CADParameterPack
from .agents import MaterialProductionAgent, JoineryProductionAgent, HardwareSelectionAgent, ManufacturingAgent


class ProductionPipeline:
    """Runs the full production planning chain."""

    def __init__(self):
        self.material_agent = MaterialProductionAgent()
        self.joinery_agent = JoineryProductionAgent()
        self.hardware_agent = HardwareSelectionAgent()
        self.mfg_agent = ManufacturingAgent()

    def run(self, pack: CADParameterPack, material_hints: Optional[Dict[str, str]] = None):
        material_plan = self.material_agent.run(pack, material_hints or {})
        joinery_plan = self.joinery_agent.run(pack, material_plan)
        hardware_plan = self.hardware_agent.run(pack, joinery_plan)
        bom = self.mfg_agent.make_bom(pack, material_plan, joinery_plan, hardware_plan)
        note_pack = self.mfg_agent.make_note_pack(pack, material_plan, joinery_plan, hardware_plan)
        return material_plan, joinery_plan, hardware_plan, bom, note_pack
