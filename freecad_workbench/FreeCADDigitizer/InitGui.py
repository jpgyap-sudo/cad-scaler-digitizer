import FreeCADGui

class FreeCADDigitizerWorkbench(FreeCADGui.Workbench):
    MenuText = "AI Furniture Digitizer"
    ToolTip = "Convert furniture drawings into CAD sketches and shop drawings"

    def Initialize(self):
        import FreeCADDigitizer.commands
        self.appendToolbar("AI Digitizer", ["Digitizer_ImportImage", "Digitizer_GenerateSketch"])
        self.appendMenu("AI Digitizer", ["Digitizer_ImportImage", "Digitizer_GenerateSketch"])

    def Activated(self):
        pass

    def Deactivated(self):
        pass

FreeCADGui.addWorkbench(FreeCADDigitizerWorkbench())
