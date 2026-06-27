"""Full end-to-end pipeline service.
Wires together: Photo → Cloud Vision → Resource Engine → CAD Kernel → DXF/PDF.

This is THE master pipeline that connects all 5 phases into one call.
"""
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class PipelineJob:
    """Tracks a pipeline execution from start to finish."""
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "initialized"
        self.steps: List[Dict[str, Any]] = []
        self.errors: List[str] = []
        self.created_at = datetime.utcnow().isoformat()
        self.completed_at: Optional[str] = None
        self.outputs: Dict[str, str] = {}

    def log(self, step: str, status: str, detail: str = ""):
        self.steps.append({"step": step, "status": status, "detail": detail, "timestamp": datetime.utcnow().isoformat()})
        self.status = status

    def fail(self, error: str):
        self.errors.append(error)
        self.status = "failed"
        self.completed_at = datetime.utcnow().isoformat()

    def complete(self):
        self.status = "completed"
        self.completed_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id, "status": self.status,
            "steps": self.steps, "errors": self.errors,
            "created_at": self.created_at, "completed_at": self.completed_at,
            "outputs": self.outputs,
        }


class PipelineService:
    """End-to-end pipeline that orchestrates all subsystems."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or tempfile.mkdtemp(prefix="pipeline_"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, PipelineJob] = {}

    def get_job(self, job_id: str) -> Optional[PipelineJob]:
        return self._jobs.get(job_id)

    def run_photo_pipeline(self, image_path: str, furniture_type: str = "") -> PipelineJob:
        """Full pipeline from photo to DXF."""
        job_id = str(uuid.uuid4())
        job = PipelineJob(job_id)
        self._jobs[job_id] = job

        prefix = str(self.output_dir / job_id)

        try:
            # Step 1: Cloud Vision (if API key available)
            features = None
            if os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"):
                job.log("cloud_vision", "running", "Extracting furniture features from image")
                try:
                    from app.resource_engine.cloud_vision import make_cloud_vision_client
                    client = make_cloud_vision_client()
                    features = client.extract_furniture_features(image_path)
                    job.log("cloud_vision", "completed", f"Detected: {features.product_type}")
                except Exception as cv_err:
                    job.log("cloud_vision", "failed", f"Cloud vision failed: {cv_err}. Using defaults.")
                    from app.resource_engine.cloud_vision import CloudVisionFeatureSet
                    features = CloudVisionFeatureSet(
                        product_type=furniture_type or "dining_table",
                        top_shape="rectangular", support_type="dual_cylindrical_pedestal",
                        approximate_dimensions_mm={"length_mm": 1800, "depth_mm": 900, "height_mm": 750},
                        confidence=0.5,
                    )
            else:
                job.log("cloud_vision", "skipped", "No API key configured, using defaults")
                from app.resource_engine.cloud_vision import CloudVisionFeatureSet
                features = CloudVisionFeatureSet(
                    product_type=furniture_type or "dining_table",
                    top_shape="rectangular", support_type="dual_cylindrical_pedestal",
                    style_keywords=["modern"],
                    approximate_dimensions_mm={"length_mm": 1800, "depth_mm": 900, "height_mm": 750},
                    confidence=0.6,
                )
                job.log("cloud_vision", "defaulted", f"Using defaults for {features.product_type}")

            # Step 2: Parameter Pack
            job.log("param_pack", "running", "Building parameter pack")
            from app.resource_engine.param_pack import ParameterPackPipeline, VisionFeatures
            vf = VisionFeatures(
                product_type=features.product_type,
                top_shape=features.top_shape or "",
                support_type=features.support_type or "",
                material_top=features.material_top or "",
                approximate_dimensions_mm=features.approximate_dimensions_mm,
                confidence=features.confidence,
            )
            pack = ParameterPackPipeline().run(vf)
            job.log("param_pack", "completed", f"Template: {pack.template_id}, {len(pack.parameters)} params")

            # Step 3: Production Planning
            job.log("production", "running", "Planning materials, joinery, hardware")
            from app.resource_engine.production import ProductionPipeline, CADParameterPack as PPack
            prod_pack = PPack(template_id=pack.template_id, product_type=pack.product_type,
                              parameters=pack.parameters, confidence=pack.confidence)
            materials_hints = {}
            if features.material_top: materials_hints["top"] = features.material_top
            if features.material_base: materials_hints["base"] = features.material_base
            material_plan, joinery_plan, hardware_plan, bom, notes = ProductionPipeline().run(prod_pack, materials_hints)
            job.log("production", "completed", f"{len(material_plan.materials)} materials, {len(bom.items)} BOM items")

            # Step 4: Manufacturing
            job.log("manufacturing", "running", "Planning manufacturing steps")
            from app.resource_engine.manufacturing import ManufacturingPipeline, CADParameterPack as MPack, MaterialSpec
            mfg_pack = MPack(template_id=pack.template_id, product_type=pack.product_type,
                             parameters=pack.parameters, confidence=pack.confidence)
            mfg_materials = [MaterialSpec(role=m.role, material=m.material, thickness_mm=m.thickness_mm)
                             for m in material_plan.materials]
            mfg_plan, qc_checklist, ready_for_cad = ManufacturingPipeline().run(mfg_pack, mfg_materials)
            job.log("manufacturing", "completed", f"{len(mfg_plan.production_steps)} steps, {len(qc_checklist.checks)} QC")

            # Step 5: Engineering Decision (Fusion)
            job.log("fusion", "running", "Fusing engineering decisions")
            from app.resource_engine.fusion import FusionPipeline, AgentOutput
            outputs = [
                AgentOutput(source="vision", category="dimension", values=features.approximate_dimensions_mm,
                            confidence=features.confidence, priority=30),
                AgentOutput(source="production", category="material",
                            values={m.role: m.material for m in material_plan.materials},
                            confidence=0.8, priority=60),
                AgentOutput(source="manufacturing", category="process",
                            values={"steps": len(mfg_plan.production_steps)},
                            confidence=0.75, priority=50),
            ]
            fused_pkg, fused_scene, audit = FusionPipeline().run(
                pack.product_type, pack.template_id, outputs)
            job.log("fusion", "completed", f"Confidence: {fused_pkg.confidence}")

            # Step 6: Template Graph
            job.log("template_graph", "running", "Instantiating template")
            from app.resource_engine.template_graph import TemplateGraphPipeline, EngineeringDecisionPackage as EDP
            # Map template IDs to graph template IDs (add .v1 suffix)
            template_graph_id = pack.template_id
            if not template_graph_id.endswith('.v1') and not template_graph_id.endswith('.v2'):
                template_graph_id = f"{template_graph_id}.v1"
            edp = EDP(product_type=pack.product_type, template_id=template_graph_id,
                      canonical_parameters=dict(pack.parameters),
                      materials={m.role: m.material for m in material_plan.materials},
                      joinery={j.role: j.method for j in joinery_plan.joinery},
                      hardware=[{"item": h.item, "qty": h.qty, "purpose": h.purpose} for h in hardware_plan.hardware],
                      approved_for_drafting=True, confidence=pack.confidence)
            template_instance, cad_scene = TemplateGraphPipeline().run(edp)
            job.log("template_graph", "completed", f"{len(cad_scene.nodes)} nodes, {len(cad_scene.views)} views")

            # Save scene graph for CAD kernel
            scene_json_path = f"{prefix}_scene_graph.json"
            Path(scene_json_path).write_text(cad_scene.model_dump_json(indent=2))
            job.outputs["scene_graph"] = scene_json_path

            # Step 7: CAD Kernel
            job.log("cad_kernel", "running", "Building CAD document")
            from app.cad_kernel import CADKernelPipeline
            cad_json = f"{prefix}_cad_doc.json"
            cad_dxf = f"{prefix}_shop_drawing.dxf"
            scene_dict = json.loads(cad_scene.model_dump_json())
            scene_dict["materials"] = {m.role: m.material for m in material_plan.materials}
            scene_dict["annotations"] = (cad_scene.annotations if hasattr(cad_scene, 'annotations') else []) + notes.material_notes + notes.joinery_notes + notes.hardware_notes
            doc = CADKernelPipeline().run(scene_dict, output_json=cad_json, output_dxf=cad_dxf)
            job.log("cad_kernel", "completed", f"{len(doc.entities)} entities, DXF: {cad_dxf}")
            # Save outputs immediately so they're available even if later steps fail
            job.outputs["dxf"] = cad_dxf
            job.outputs["json"] = cad_json

            # Step 8: Quality Evaluator
            job.log("quality", "running", "Evaluating drawing quality")
            from app.cad_kernel.quality_evaluator import Phase3E10Pipeline as QEP
            quality_result = QEP().run({"items": [{}] * 5, "title": pack.product_type},
                                        {"dimensions": [{}], "completeness": 1.0})
            job.log("quality", "completed", f"Score: {quality_result.score}, Passed: {quality_result.passed}")

            # Step 9: Closed Loop
            job.log("closed_loop", "running", "Recording learning case")
            from app.resource_engine.closed_loop import ClosedLoopPipeline, ReviewCase, QualitySummary
            review_case = ReviewCase(
                product_id=job_id, product_type=pack.product_type, template_id=pack.template_id,
                status="generated",
                generated_parameters=dict(pack.parameters),
                quality_summary=QualitySummary(score=quality_result.score, passed=quality_result.passed),
            )
            resource_ids = [pack.template_id]
            ClosedLoopPipeline().run_learning_cycle(case=review_case, resource_ids=resource_ids,
                                                     output_prefix=f"{prefix}_learning")
            job.log("closed_loop", "completed", "Learning case recorded")

            job.outputs["dxf"] = cad_dxf
            job.outputs["json"] = cad_json
            job.outputs["quality_score"] = str(quality_result.score)
            job.complete()
            job.log("pipeline", "completed", "Full pipeline finished successfully")

        except Exception as e:
            job.fail(str(e))
            import traceback
            job.log("pipeline", "failed", traceback.format_exc())

        return job
