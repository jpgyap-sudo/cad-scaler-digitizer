from app.productionization.models import GenerateRequest, GenerateResponse, PipelineStageResult
from app.productionization.pipeline.adapters import (
    VisionAdapter,
    RetrievalAdapter,
    EngineeringAdapter,
    TemplateGraphAdapter,
    DrawingEngineAdapter,
    QualityAdapter,
)
from app.productionization.review.review_service import ReviewService


class ShopDrawingOrchestrator:
    def __init__(self):
        self.vision = VisionAdapter()
        self.retrieval = RetrievalAdapter()
        self.engineering = EngineeringAdapter()
        self.template_graph = TemplateGraphAdapter()
        self.drawing = DrawingEngineAdapter()
        self.quality = QualityAdapter()
        self.review = ReviewService()

    def run(self, job_id: str, request: GenerateRequest):
        stages = []

        vision = self.vision.run(request)
        stages.append(PipelineStageResult(stage="vision", output=vision))

        retrieval = self.retrieval.run(vision)
        stages.append(PipelineStageResult(stage="retrieval", output=retrieval))

        engineering = self.engineering.run(vision, retrieval, request)
        stages.append(PipelineStageResult(stage="engineering", output=engineering))

        scene = self.template_graph.run(engineering)
        stages.append(PipelineStageResult(stage="template_graph", output=scene))

        case_id = f"case_{job_id}"
        artifacts = self.drawing.run(case_id, scene, engineering)
        stages.append(PipelineStageResult(stage="drawing_engine", output={"artifacts": [a.model_dump() for a in artifacts]}))

        quality = self.quality.run(artifacts, engineering)
        stages.append(PipelineStageResult(stage="quality", output=quality, warnings=quality.get("issues", [])))

        review_case = self.review.create_from_generation(
            case_id=case_id,
            request=request,
            engineering=engineering,
            artifacts=artifacts,
            quality=quality,
            resource_ids=retrieval.get("resource_ids", []),
        )

        response = GenerateResponse(
            job_id=job_id,
            case_id=review_case["id"],
            status="generated",
            artifacts=artifacts,
            quality_score=quality["score"],
            warnings=quality.get("issues", []),
        )
        return response, stages
