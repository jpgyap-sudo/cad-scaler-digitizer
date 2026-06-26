"""
FreeCADDigitizer Workbench — GUI Initialization.

Registers the AI Furniture Digitizer workbench with FreeCAD's GUI,
creating toolbar buttons and menu entries for importing drawings and
generating CAD sketches via the CAD engine API.
"""

import FreeCAD
import FreeCADGui


class FreeCADDigitizerWorkbench(FreeCADGui.Workbench):
    """AI Furniture Digitizer — Convert furniture drawings to parametric CAD."""

    MenuText = "AI Digitizer"
    ToolTip = (
        "Convert furniture drawings into parametric CAD sketches and shop drawings.\n"
        "1. Import a drawing image (PNG/JPEG/PDF)\n"
        "2. Generate CAD Sketch — sends to OpenCV+AI engine\n"
        "3. DXF is imported into the active document"
    )
    Icon = ""  # Can be set to an XPM icon path

    def Initialize(self):
        """Set up toolbar and menu when workbench is activated."""
        import FreeCADDigitizer.commands  # noqa: F401 — registers commands

        commands = [
            "Digitizer_ImportImage",
            "Digitizer_GenerateSketch",
        ]

        self.appendToolbar("AI Digitizer", commands)
        self.appendMenu("AI Digitizer", commands)

        FreeCAD.Console.PrintMessage(
            "[Digitizer] Workbench loaded. "
            "Use 'Import Drawing Image' then 'Generate CAD Sketch'.\n"
        )

    def Activated(self):
        """Called when the workbench is selected."""
        # Check engine health on activation (non-blocking)
        try:
            from FreeCADDigitizer.commands import CAD_ENGINE_URL, LOCAL_ENGINE_URL
            import urllib.request, json

            for url in [LOCAL_ENGINE_URL, CAD_ENGINE_URL]:
                try:
                    req = urllib.request.Request(f"{url}/health", method="GET")
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        data = json.loads(resp.read().decode())
                        if data.get("ok"):
                            FreeCAD.Console.PrintMessage(
                                f"[Digitizer] Engine online: {url}\n"
                            )
                            return
                except Exception:
                    continue

            FreeCAD.Console.PrintWarning(
                "[Digitizer] CAD engine not reachable. Start the Python backend first.\n"
            )
        except Exception:
            pass  # Silently skip if network check fails

    def Deactivated(self):
        """Called when switching away from this workbench."""
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(FreeCADDigitizerWorkbench())
