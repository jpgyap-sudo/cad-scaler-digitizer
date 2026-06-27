from .models import SheetItem
class RevisionTable:
    def build(self):
        return SheetItem(kind="revision",name="Revision Table",x=950,y=20,width=180,height=120)
