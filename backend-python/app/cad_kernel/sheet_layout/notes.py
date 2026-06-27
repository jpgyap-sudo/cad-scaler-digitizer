from .models import SheetItem
class NotesPlacer:
    def build(self):
        return SheetItem(kind="notes",name="General Notes",x=900,y=500,width=250,height=220)
