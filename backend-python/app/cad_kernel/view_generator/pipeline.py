from .view_generator import ViewGenerator
from .viewport_layout import ViewportLayout
class Phase3E2Pipeline:
    def run(self,doc):
        views=ViewGenerator().generate(doc)
        return {'views':views,'layout':ViewportLayout().layout(views)}
