from .models import Annotation
class MaterialNotes:
    def build(self, scene):
        mat = scene.get("materials", {})
        anns = []
        for k, v in mat.items():
            anns.append(Annotation(kind="material", text=f"{k.upper()}: {v}", anchor={"x":-800,"y":-200}, layer="TEXT"))
        if not anns:
            anns.append(Annotation(kind="material", text="MATERIAL: MARBLE TOP / BRUSHED METAL BASE", anchor={"x":-800,"y":-200}, layer="TEXT"))
        return anns
