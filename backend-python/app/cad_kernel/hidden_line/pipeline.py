from app.cad_kernel.hidden_line.models import DrawingView, HiddenLineResult
from app.cad_kernel.hidden_line.centerline_generator import CenterlineGenerator
from app.cad_kernel.hidden_line.occlusion_heuristics import OcclusionHeuristics
from app.cad_kernel.hidden_line.classifier import EdgeClassifier
from app.cad_kernel.hidden_line.quality import HiddenLineQualityScorer


class Phase3E3HiddenLinePipeline:
    def run_view(self, view: DrawingView) -> HiddenLineResult:
        view = CenterlineGenerator().generate_for_view(view)
        edges = OcclusionHeuristics().apply(view.edges)

        classifier = EdgeClassifier()
        classified = [classifier.classify(e) for e in edges]

        result = HiddenLineResult(
            view_id=view.view_id,
            view_type=view.view_type,
            classified_edges=classified,
        )
        return HiddenLineQualityScorer().score(result)
