from .models import DetailView
class DetailViewBuilder:
    def build(self, candidate, scene):
        return DetailView(detail_id=candidate.id, detail_type=candidate.detail_type, label="", note=candidate.reason, priority=candidate.priority)
