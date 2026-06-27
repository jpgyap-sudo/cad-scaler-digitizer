from .models import SectionSet
class SectionQualityScorer:
    def score(self, result):
        score = min(1.0, len(result.sections) * 0.25)
        result.quality_score = round(score, 2)
        return result
