from .models import PlotSheet, SheetItem
from .dxf_writer import DXFPlotWriter
from .pdf_writer import PDFPlotWriter
from .manifest import PlotManifestWriter

class Phase3E9PlotPipeline:
    def run(self, sheet_data, dxf_path, pdf_path, manifest_path):
        sheet = PlotSheet(**sheet_data)
        DXFPlotWriter().write(sheet, dxf_path)
        PDFPlotWriter().write(sheet, pdf_path)
        return PlotManifestWriter().write(dxf_path, pdf_path, sheet, manifest_path)
