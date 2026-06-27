from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from .sheet_sizes import SHEET_SIZES_MM

class PDFPlotWriter:
    def write(self, sheet, path):
        sw, sh = SHEET_SIZES_MM.get(sheet.size, SHEET_SIZES_MM["A1"])
        c = canvas.Canvas(path, pagesize=(sw*mm, sh*mm))

        c.setLineWidth(0.5)
        c.rect(0, 0, sw*mm, sh*mm)

        c.setFont("Helvetica-Bold", 12)
        c.drawString(20*mm, (sh-25)*mm, sheet.title)

        c.setFont("Helvetica", 7)

        for item in sheet.items:
            x, y, w, h = item.x*mm, item.y*mm, item.width*mm, item.height*mm
            c.rect(x, y, w, h)
            c.drawString(x+4*mm, y+h-8*mm, f"{item.kind.upper()}: {item.name}")

            if item.kind == "view":
                c.line(x+10*mm, y+10*mm, x+w-10*mm, y+h-10*mm)
                c.line(x+10*mm, y+h-10*mm, x+w-10*mm, y+10*mm)

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        c.save()
        return path
