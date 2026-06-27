from .models import DetailViewSet
from .detector import DetailCandidateDetector
from .builder import DetailViewBuilder
from .labeler import DetailLabeler
from .quality import DetailQualityScorer

class Phase3E6Pipeline:
    def run(self, scene, sections=None):
        candidates = DetailCandidateDetector().detect(scene, sections)
        builder = DetailViewBuilder()
        details = [builder.build(c, scene) for c in candidates]
        details = DetailLabeler().assign_labels(details)
        result = DetailViewSet(details=details)
        return DetailQualityScorer().score(result)
