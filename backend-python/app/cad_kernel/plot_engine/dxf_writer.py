from pathlib import Path
import ezdxf
from .sheet_sizes import SHEET_SIZES_MM

class DXFPlotWriter:
    def write(self, sheet, path):
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()

        for layer in ["SHEET", "VIEWPORT", "TEXT", "TITLEBLOCK", "BOM", "NOTES", "REVISION"]:
            if layer not in doc.layers:
                doc.layers.new(layer)

        w, h = SHEET_SIZES_MM.get(sheet.size, SHEET_SIZES_MM["A1"])

        # sheet border
        msp.add_lwpolyline([(0,0),(w,0),(w,h),(0,h)], close=True, dxfattribs={"layer":"SHEET"})

        for item in sheet.items:
            layer = {
                "titleblock": "TITLEBLOCK",
                "bom": "BOM",
                "notes": "NOTES",
                "revision": "REVISION",
                "view": "VIEWPORT",
            }.get(item.kind, "VIEWPORT")

            x, y = item.x, item.y
            ww, hh = item.width, item.height
            msp.add_lwpolyline([(x,y),(x+ww,y),(x+ww,y+hh),(x,y+hh)], close=True, dxfattribs={"layer":layer})
            msp.add_text(item.name, dxfattribs={"height":8, "layer":"TEXT"}).set_placement((x+5, y+hh-15))

        msp.add_text(sheet.title, dxfattribs={"height":12, "layer":"TEXT"}).set_placement((20, h-25))

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(path)
        return path
