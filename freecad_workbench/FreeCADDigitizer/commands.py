import FreeCAD, FreeCADGui

class ImportImageCommand:
    def GetResources(self):
        return {"MenuText": "Import Drawing Image", "ToolTip": "Import furniture drawing image"}
    def Activated(self):
        FreeCAD.Console.PrintMessage("Import image command placeholder\n")

class GenerateSketchCommand:
    def GetResources(self):
        return {"MenuText": "Generate CAD Sketch", "ToolTip": "Generate parametric sketch from detected furniture"}
    def Activated(self):
        FreeCAD.Console.PrintMessage("Generate sketch command placeholder\n")

FreeCADGui.addCommand("Digitizer_ImportImage", ImportImageCommand())
FreeCADGui.addCommand("Digitizer_GenerateSketch", GenerateSketchCommand())
