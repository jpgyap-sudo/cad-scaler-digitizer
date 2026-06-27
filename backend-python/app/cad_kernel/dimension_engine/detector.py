from .models import DimensionNode
class GeometryDetector:
    def detect(self,scene):
        nodes=[]
        for c in scene.get('nodes',[]):
            p=c.get('parameters',{})
            L=p.get('length_mm',1800); D=p.get('depth_mm',900); H=p.get('height_mm',750)
            nodes.append(DimensionNode(id=c['id'],desc=f'{c["role"]} length',value=L))
            nodes.append(DimensionNode(id=c['id'],desc=f'{c["role"]} depth',value=D))
            nodes.append(DimensionNode(id=c['id'],desc=f'{c["role"]} height',value=H))
        return nodes
