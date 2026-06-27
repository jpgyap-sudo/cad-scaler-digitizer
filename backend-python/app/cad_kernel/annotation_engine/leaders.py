from .models import Annotation
class LeaderGenerator:
    def build(self, scene):
        anns = []
        for n in scene.get("nodes", []):
            if n.get("role") == "top":
                anns.append(Annotation(kind="leader", text="TABLE TOP (SEE MATERIAL NOTE)", anchor={"x":0,"y":100}, layer="LEADER"))
            if n.get("role") == "support" and "cylinder" in (n.get("shape","") or ""):
                anns.append(Annotation(kind="leader", text="CYLINDRICAL PEDESTAL BASE", anchor={"x":100,"y":0}, layer="LEADER"))
        return anns
