from .projection import OrthographicProjector
class ViewportLayout:
    def layout(self,views):
        return {v:{"x":i*200,"y":0,"width":200,"height":200} for i,v in enumerate(views.keys())}
