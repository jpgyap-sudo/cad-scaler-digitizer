# FreeCADDigitizer Workbench — AI Furniture Digitizer for FreeCAD
# Converts furniture drawing images into parametric CAD sketches and shop drawings.

__title__   = "AI Furniture Digitizer"
__author__  = "CAD Scaler Digitizer"
__url__     = "https://cad.abcx124.xyz"
__version__ = "1.0.0"
__date__    = "2026-06-25"
__license__ = "MIT"
__comment__ = "Import furniture drawings and generate CAD sketches via the CAD engine API."

# Expose key symbols for FreeCAD workbench discovery
from FreeCADDigitizer.commands import ImportImageCommand, GenerateSketchCommand
