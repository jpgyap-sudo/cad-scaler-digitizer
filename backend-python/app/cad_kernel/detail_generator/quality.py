from .models import DetailViewSet
class DetailQualityScorer:
    def score(self, result):
        result.quality_score = round(min(1.0, len(result.details) * 0.25), 2)
        return result
