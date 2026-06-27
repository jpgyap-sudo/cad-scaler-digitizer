from .models import Annotation
class BOMBalloons:
    def build(self, scene):
        return [Annotation(kind="bom_balloon", text=f"ITEM {i+1}", anchor={"x":i*100,"y":-400}, layer="BOM") for i in range(3)]
