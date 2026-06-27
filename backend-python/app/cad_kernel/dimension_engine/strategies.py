from .models import DimensionNode
class DimensionStrategies:
    def build(self,nodes):
        return [{'source':n.id,'desc':n.desc,'value_mm':n.value,'placement':'auto'} for n in nodes]
