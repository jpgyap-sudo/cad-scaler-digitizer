from .models import SheetItem
class ViewPlacer:
    def place(self,views):
        out=[];x=50;y=200
        for k in views:
            out.append(SheetItem(kind="view",name=k,x=x,y=y,width=220,height=160))
            x+=240
            if x>700:
                x=50;y+=190
        return out
