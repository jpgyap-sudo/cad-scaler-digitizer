"""Engineering agents — geometry, dimension, material, joinery, validation.
Each agent runs with rule-based fallback and optional cloud reasoning.
"""
import json
from typing import Any, Dict, Optional
from .base_agent import BaseAgent
from .models import EngineeringContext
from .memory import SharedMemory, MessageBus


class GeometryAgent(BaseAgent):
    name = "geometry_agent"
    category = "geometry"

    def run(self, context: EngineeringContext, memory: SharedMemory,
            bus: MessageBus) -> dict:
        f = context.features
        return self.cloud_or_rules(self.context_json(context, memory), lambda: {
            "summary": f"Determined geometry for {f.product_type}",
            "decisions": {
                "top_shape": f.top_shape or "rectangular",
                "support_type": f.support_type or "four_leg",
                "product_type": f.product_type,
                "subtype": f.subtype or "",
            },
            "confidence": f.confidence or 0.6,
            "evidence": [f"Detected top shape: {f.top_shape}", f"Detected support type: {f.support_type}"],
        })


class DimensionAgent(BaseAgent):
    name = "dimension_agent"
    category = "dimension"

    def run(self, context: EngineeringContext, memory: SharedMemory,
            bus: MessageBus) -> dict:
        f = context.features
        dims = f.approximate_dimensions_mm or {}
        return self.cloud_or_rules(self.context_json(context, memory), lambda: {
            "summary": "Estimated product dimensions",
            "decisions": {
                "length_mm": dims.get("length_mm", 1800),
                "depth_mm": dims.get("depth_mm", 900),
                "height_mm": dims.get("height_mm", 750),
                "top_thickness_mm": dims.get("top_thickness_mm", 30),
            },
            "confidence": 0.7 if dims else 0.4,
            "evidence": [f"From vision features: {dims}"] if dims else ["No dimensions detected, using defaults"],
        })


class MaterialAgent(BaseAgent):
    name = "material_agent"
    category = "material"

    def run(self, context: EngineeringContext, memory: SharedMemory,
            bus: MessageBus) -> dict:
        f = context.features
        return self.cloud_or_rules(self.context_json(context, memory), lambda: {
            "summary": "Inferred materials and finishes",
            "decisions": {
                "top_material": f.material_top or "unknown",
                "base_material": f.material_base or "unknown",
                "upholstery_type": f.upholstery_type or "none",
            },
            "confidence": f.confidence or 0.5,
            "evidence": [f"Detected: top={f.material_top}, base={f.material_base}"],
        })


class JoineryAgent(BaseAgent):
    name = "joinery_agent"
    category = "joinery"

    def run(self, context: EngineeringContext, memory: SharedMemory,
            bus: MessageBus) -> dict:
        f = context.features
        hidden = f.inferred_hidden_parts or []
        return self.cloud_or_rules(self.context_json(context, memory), lambda: {
            "summary": "Inferred hidden joinery and construction",
            "decisions": {
                "has_hidden_steel_frame": "hidden frame" in " ".join(hidden).lower() if hidden else True,
                "joinery_type": "hidden_steel_frame",
                "notes": hidden if hidden else ["Assume hidden steel frame for stone/composite top"],
            },
            "confidence": 0.6 if hidden else 0.4,
            "evidence": [f"Inferred hidden parts: {hidden}"] if hidden else ["No hidden parts detected"],
        })


class ValidationAgent(BaseAgent):
    name = "validation_agent"
    category = "validation"

    def run(self, context: EngineeringContext, memory: SharedMemory,
            bus: MessageBus) -> dict:
        # Read all previous findings
        all_findings = memory.findings
        warnings = []
        for af in all_findings:
            if af.warnings:
                warnings.extend(af.warnings)
        return self.cloud_or_rules(self.context_json(context, memory), lambda: {
            "summary": f"Validated {len(all_findings)} agent findings",
            "decisions": {},
            "confidence": 0.8,
            "warnings": warnings,
            "evidence": [f"Collected {len(warnings)} warnings from {len(all_findings)} agents"],
        })
