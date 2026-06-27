from .projection import OrthographicProjector
class ViewGenerator:
    def generate(self,doc):
        p=OrthographicProjector();return {k:p.project(doc,k) for k in ['top','front','side','rear','bottom','isometric']}
