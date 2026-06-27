from .models import SheetItem
class TitleBlock:
    def build(self,size):
        return SheetItem(kind="titleblock",name="ISO Title Block",x=0,y=0,width=180,height=55)
