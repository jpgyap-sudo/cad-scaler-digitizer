from .models import SectionSet
from .locator import SectionLocator
from .cutter import SectionCutter
from .detail_builder import SectionDetailBuilder
from .quality import SectionQualityScorer

class Phase3E5Pipeline:
    def run(self, scene):
        planes = SectionLocator().suggest_planes(scene)
        cutter = SectionCutter()
        builder = SectionDetailBuilder()
        details = []
        for plane in planes:
            cut = cutter.cut(scene, plane)
            details.append(builder.build(scene, plane, cut))
        result = SectionSet(sections=planes, details=details)
        return SectionQualityScorer().score(result)
