from .models import DrawingSheet
from .titleblock import TitleBlock
from .revision import RevisionTable
from .placer import ViewPlacer
from .bom import BOMPlacer
from .notes import NotesPlacer

class Phase3E8Pipeline:
    def run(self,views,title='Furniture Shop Drawing',size='A1'):
        sheet=DrawingSheet(size=size,title=title)
        sheet.items.extend(ViewPlacer().place(views))
        sheet.items.append(BOMPlacer().build())
        sheet.items.append(NotesPlacer().build())
        sheet.items.append(RevisionTable().build())
        sheet.items.append(TitleBlock().build(size))
        sheet.metadata={'plot_scale':'1:10','units':'mm'}
        return sheet
