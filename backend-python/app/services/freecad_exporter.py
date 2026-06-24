"""FreeCAD parametric model export (requires FreeCAD headless)."""
from pathlib import Path
import subprocess, json, os


def export_freecad_fcstd(dxf_path: Path, fcstd_path: Path, dimensions: dict = None, furniture_type: str = "furniture"):
    """
    Convert DXF to FreeCAD FCStd parametric model.
    Uses FreeCAD's headless mode via subprocess.
    """
    dims = dimensions or {}
    
    # Create a FreeCAD Python macro
    macro = f'''
import FreeCAD, Draft, Part
import ImportGui, importDXF

doc = FreeCAD.newDocument("{furniture_type}")

# Import DXF as base geometry
ImportGui.insert("{dxf_path}", doc.name)

# Add parametric dimensions
D = float({dims.get("diameter", dims.get("width", 80))})
H = float({dims.get("height", 70)})

# Create parametric spreadsheet
sheet = doc.addObject("Spreadsheet::Sheet", "Dimensions")
sheet.set("A1", "Diameter")
sheet.set("B1", str(D))
sheet.set("A2", "Height")
sheet.set("B2", str(H))

doc.recompute()
doc.saveAs("{fcstd_path}")
'''
    
    macro_path = dxf_path.parent / f"{dxf_path.stem}_macro.py"
    macro_path.write_text(macro)
    
    try:
        result = subprocess.run(
            ["freecad", "--headless", "--run", str(macro_path)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            print(f"[FreeCAD] Error: {result.stderr[:500]}")
            return False
        return fcstd_path.exists()
    except FileNotFoundError:
        print("[FreeCAD] FreeCAD not installed. Install: apt-get install freecad")
        return False
    except Exception as e:
        print(f"[FreeCAD] Exception: {e}")
        return False
    finally:
        try: os.unlink(str(macro_path))
        except: pass
