from .models import SheetItem
class BOMPlacer:
    def build(self):
        return SheetItem(kind="bom",name="Bill of Materials",x=900,y=180,width=250,height=300)
