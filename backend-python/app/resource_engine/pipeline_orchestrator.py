"""Phase3Pipeline — orchestrates Cloud Vision → RI Engine → Template Resolver → Validation → Fusion → Handoff.

This is the Phase 3a-b pipeline that connects CloudVisionFeatureSet (from VLM)
through the ResourceIntelligenceEngine scene graph builder and TemplateResolver
to produce an EngineeringDecisionPackage ready for CAD drafting.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cloud_vision import (
    CloudVisionFeatureSet, CloudVisionClient,
    make_cloud_vision_client, FURNITURE_FEATURE_PROMPT,
)
from .schema import VisionFeatureSet, ParametricSceneGraph
from .matcher import ResourceIntelligenceEngine, build_scene_graph
from .library import ResourceLibrary
from .template_loader import TemplateGraphLoader
from .template_resolver import TemplateResolver
from .quality import QualityValidator
from .validation.pipeline import ValidationPipeline
from .fusion.models import (
    AgentOutput, EngineeringDecisionPackage, CADSceneNode,
    CADViewSpec, ParametricCADSceneGraph, AuditTrail,
)
from .fusion.pipeline import FusionPipeline
from .handoff.pipeline import OutputPipeline
from .handoff.models import ProductionPacket


# How CloudVisionFeatureSet fields map to VisionFeatureSet fields
FEATURE_MAP: Dict[str, str] = {
    "product_type": "product_type",
    "top_shape": "top_shape",
    "support_type": "support_type",
    "material_top": "material_top",
    "material_base": "material_base",
    "style_keywords": "style_keywords",
    "confidence": "confidence",
}


class Phase3PipelineResult:
    """Structured result from Phase3Pipeline run."""

    def __init__(self):
        self.vision_features: Optional[CloudVisionFeatureSet] = None
        self.scene_graph: Optional[ParametricSceneGraph] = None
        self.template: Optional[Dict[str, Any]] = None
        self.resolved_parameters_mm: Dict[str, float] = {}
        self.fusion_package: Optional[EngineeringDecisionPackage] = None
        self.cad_scene: Optional[ParametricCADSceneGraph] = None
        self.production_packet: Optional[ProductionPacket] = None
        self.validation_report: Any = None
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def to_api_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API response."""
        result: Dict[str, Any] = {}

        if self.vision_features:
            result["vision_features"] = self.vision_features.model_dump()

        if self.scene_graph:
            result["scene_graph"] = json.loads(self.scene_graph.model_dump_json())

        if self.template:
            t = self.template
            result["template_graph"] = {
                "template_id": t.get("id"),
                "template_name": t.get("name"),
                "product_type": t.get("product_type"),
                "family": t.get("family"),
                "resolved_parameters_mm": self.resolved_parameters_mm,
                "required_views": t.get("required_views", []),
                "required_details": t.get("required_details", []),
                "drawing_notes": t.get("drawing_notes", []),
            }

        if self.validation_report:
            result["validation"] = json.loads(self.validation_report.model_dump_json())

        if self.production_packet:
            result["production"] = json.loads(self.production_packet.model_dump_json())

        result["warnings"] = self.warnings
        result["errors"] = self.errors
        return result


class Phase3Pipeline:
    """End-to-end pipeline: Cloud Vision → RI Engine → Template → Validation → Fusion → Handoff.

    Designed to be called from /digitize/hybrid after the existing CV-based
    detection runs, providing a structured VLM-backed parallel analysis track.
    """

    def __init__(
        self,
        cloud_client: Optional[CloudVisionClient] = None,
        resource_library: Optional[ResourceLibrary] = None,
        template_loader: Optional[TemplateGraphLoader] = None,
    ):
        self.cloud_client = cloud_client or make_cloud_vision_client()
        self.resource_library = resource_library or ResourceLibrary().load()
        self.ri_engine = ResourceIntelligenceEngine(self.resource_library)
        self.template_loader = template_loader or TemplateGraphLoader().load()
        self.template_resolver = TemplateResolver(self.template_loader)
        self.validator = QualityValidator()
        self.validation_pipeline = ValidationPipeline()
        self.fusion_pipeline = FusionPipeline()
        self.output_pipeline = OutputPipeline()

    def run(
        self,
        image_path: str,
        product_type_override: Optional[str] = None,
        known_dims_cm: Optional[Dict[str, float]] = None,
        materials_override: Optional[Dict[str, str]] = None,
        cad_intel_result: Optional[Dict[str, Any]] = None,
        component_graph_result: Optional[Dict[str, Any]] = None,
    ) -> Phase3PipelineResult:
        """Run the full Phase 3a-b pipeline on a single image.

        Args:
            image_path: Path to the furniture photo
            product_type_override: Optional forced product type (skip VLM)
            known_dims_cm: Optional known dimensions in cm
            materials_override: Optional material overrides

        Returns:
            Phase3PipelineResult with all pipeline outputs
        """
        result = Phase3PipelineResult()

        # ===== Phase 3a: Cloud Vision Feature Extraction =====
        try:
            cloud_features: CloudVisionFeatureSet = (
                self.cloud_client.extract_furniture_features(image_path)
            )
            result.vision_features = cloud_features
        except Exception as e:
            result.errors.append(f"CloudVision failed: {e}")
            cloud_features = CloudVisionFeatureSet()

        # ===== Bridge: CloudVisionFeatureSet → VisionFeatureSet =====
        vfs = self._cloud_to_vision_features(cloud_features)

        # Apply overrides
        if product_type_override:
            vfs.product_type = product_type_override

        # ===== Phase 3b-1: ResourceIntelligenceEngine → Scene Graph =====
        try:
            scene_graph = self.ri_engine.build_scene(vfs)
            result.scene_graph = scene_graph
        except Exception as e:
            result.errors.append(f"RIEngine failed: {e}")
            scene_graph = ParametricSceneGraph(product_type=vfs.product_type)

        # ===== Phase 3b-2: Template Resolver =====
        try:
            detected_dims = self._extract_dims_from_sources(
                cloud_features, known_dims_cm
            )
            template_result = self.template_resolver.resolve(
                vfs.product_type,
                detected_dims,
                materials=materials_override,
            )
            result.template = template_result.get("template")
            result.resolved_parameters_mm = template_result.get("resolved_parameters", {})
            result.warnings.extend(template_result.get("warnings", []))
        except Exception as e:
            result.errors.append(f"TemplateResolver failed: {e}")

        # ===== Phase 3c: Validation Pipeline =====
        try:
            validation_package = self._build_validation_package(
                vfs.product_type,
                template_result if 'template_result' in dir() else {},
                scene_graph,
            )
            validation_report, corrected_package = (
                self.validation_pipeline.run(validation_package)
            )
            result.validation_report = validation_report
        except Exception as e:
            result.errors.append(f"Validation failed: {e}")
            validation_report, corrected_package = None, None

        # ===== Phase 3c: Fusion Pipeline =====
        try:
            agent_outputs = self._build_agent_outputs(
                cloud_features, scene_graph,
                template_result if 'template_result' in dir() else {},
                cad_intel_result=cad_intel_result,
                component_graph=component_graph_result,
            )
            template_id = (
                template_result.get("template", {}).get("id", "unknown")
                if 'template_result' in dir() else "unknown"
            )
            fusion_package, cad_scene, audit = self.fusion_pipeline.run(
                product_type=vfs.product_type,
                template_id=template_id,
                outputs=agent_outputs,
                validation=validation_report,
                output_prefix="phase3_",
            )
            result.fusion_package = fusion_package
            result.cad_scene = cad_scene
        except Exception as e:
            result.errors.append(f"Fusion failed: {e}")

        # ===== Phase 3e: Handoff / Output Pipeline =====
        try:
            if result.fusion_package and result.cad_scene:
                packet = self.output_pipeline.run(
                    result.fusion_package, result.cad_scene
                )
                result.production_packet = packet
        except Exception as e:
            result.errors.append(f"Handoff failed: {e}")

        return result

    # ---- Private helpers ----

    def _cloud_to_vision_features(
        self, cf: CloudVisionFeatureSet
    ) -> VisionFeatureSet:
        """Convert CloudVisionFeatureSet → VisionFeatureSet for RI Engine."""
        return VisionFeatureSet(
            product_type=cf.product_type or "unknown",
            top_shape=cf.top_shape,
            support_type=cf.support_type,
            material_top=cf.material_top,
            material_base=cf.material_base,
            symmetry=None,
            style_keywords=cf.style_keywords or [],
            confidence=cf.confidence or 0.0,
        )

    def _extract_dims_from_sources(
        self,
        cloud_features: CloudVisionFeatureSet,
        known_dims_cm: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Combine approximate VLM dimensions with known overrides."""
        dims: Dict[str, float] = dict(known_dims_cm or {})

        # Extract from CloudVision approximate_dimensions_mm
        approx = cloud_features.approximate_dimensions_mm or {}
        if approx.get("length_mm") and "length_cm" not in dims:
            dims["length_cm"] = approx["length_mm"] / 10.0
        if approx.get("depth_mm") and "depth_cm" not in dims:
            dims["depth_cm"] = approx["depth_mm"] / 10.0
        if approx.get("height_mm") and "overall_height_cm" not in dims:
            dims["overall_height_cm"] = approx["height_mm"] / 10.0
        if approx.get("top_thickness_mm") and "top_thickness_cm" not in dims:
            dims["top_thickness_cm"] = approx["top_thickness_mm"] / 10.0

        return dims

    def _build_validation_package(
        self,
        product_type: str,
        template_result: Dict[str, Any],
        scene_graph: ParametricSceneGraph,
    ) -> Any:
        """Build a simple dict for the validation pipeline."""
        return {
            "product_type": product_type,
            "template_id": (template_result.get("template", {}) or {}).get("id", "unknown")
                if template_result else "unknown",
            "resolved_parameters": (
                template_result.get("resolved_parameters", {}) if template_result else {}
            ),
            "scene_graph": scene_graph,
            "constraints": (
                template_result.get("constraints", []) if template_result else []
            ),
        }

    def _build_agent_outputs(
        self,
        cloud_features: CloudVisionFeatureSet,
        scene_graph: ParametricSceneGraph,
        template_result: Dict[str, Any],
        cad_intel_result: Optional[Dict[str, Any]] = None,
        component_graph: Optional[Dict[str, Any]] = None,
    ) -> List[AgentOutput]:
        """Build AgentOutput list for the fusion pipeline."""
        outputs: List[AgentOutput] = []

        # Vision agent output
        vision_values: Dict[str, Any] = {
            "product_type": cloud_features.product_type or "unknown",
            "top_shape": cloud_features.top_shape or "unknown",
            "support_type": cloud_features.support_type or "unknown",
        }
        if cloud_features.material_top:
            vision_values["material_top"] = cloud_features.material_top
        if cloud_features.material_base:
            vision_values["material_base"] = cloud_features.material_base

        outputs.append(AgentOutput(
            source="cloud_vision",
            category="vision",
            values=vision_values,
            confidence=cloud_features.confidence or 0.7,
            priority=30,
        ))

        # Scene graph agent output
        outputs.append(AgentOutput(
            source="resource_intelligence_engine",
            category="scene_graph",
            values={"component_count": len(scene_graph.components),
                    "rule_count": len(scene_graph.rules)},
            confidence=0.8,
            priority=50,
        ))

        # Template agent output
        tpl = template_result.get("template", {}) if template_result else {}
        if tpl:
            outputs.append(AgentOutput(
                source="template_resolver",
                category="parameters",
                values=template_result.get("resolved_parameters", {}),
                confidence=0.85,
                priority=40,
            ))

        # ===== CAD Intelligence entity agent (pixel-detected geometry) =====
        if cad_intel_result:
            ent_count = len(cad_intel_result.get("entities", []))
            assoc_count = len(cad_intel_result.get("associations", []))
            scale_info = cad_intel_result.get("scale", {})
            conf_summ = cad_intel_result.get("debug", {}).get("confidence_summary", {})
            outputs.append(AgentOutput(
                source="cad_intelligence",
                category="geometry",
                values={
                    "entity_count": ent_count,
                    "association_count": assoc_count,
                    "scale_mm_per_px": scale_info.get("mm_per_px"),
                    "scale_confidence": scale_info.get("confidence", 0),
                    "confidence_summary": conf_summ,
                    "dimension_count": cad_intel_result.get("dimension_count", 0),
                    "line_count": cad_intel_result.get("line_count", 0),
                },
                confidence=scale_info.get("confidence", 0.5),
                priority=25,  # Slightly below vision (30), above defaults
                warnings=[] if scale_info.get("mm_per_px") else ["Scale could not be solved from OCR data"],
            ))

        # ===== Component Graph agent (spatial grouping of entities) =====
        if component_graph:
            outputs.append(AgentOutput(
                source="component_graph",
                category="structure",
                values=component_graph,
                confidence=0.55,  # Lower — heuristic-based grouping
                priority=20,
            ))

        return outputs
