from .models import AnnotationSet
from .leaders import LeaderGenerator
from .materials import MaterialNotes
from .bom import BOMBalloons
from .layout import AnnotationLayout

class Phase3E7Pipeline:
    def run(self, scene):
        anns = []
        anns += LeaderGenerator().build(scene)
        anns += MaterialNotes().build(scene)
        anns += BOMBalloons().build(scene)
        anns = AnnotationLayout().arrange(anns)
        score = min(1.0, 0.5 + 0.05 * len(anns))
        return AnnotationSet(annotations=anns, score=score)
