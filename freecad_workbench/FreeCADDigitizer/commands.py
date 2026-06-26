"""
FreeCADDigitizer Commands — Real implementations for the AI Furniture Digitizer workbench.

Commands:
    ImportImageCommand   — Import a furniture drawing image into the active FreeCAD document.
    GenerateSketchCommand — Send the imported image to the CAD engine API and import the resulting DXF.
"""

import os
import json
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

import FreeCAD
import FreeCADGui


# ─── Configuration ──────────────────────────────────────────────────────────────

# Try the production engine first, fall back to localhost.
# Users can override by running in FreeCAD Python console:
#   import FreeCADDigitizer.commands as cmd
#   cmd.CAD_ENGINE_URL = "http://my-server:8000"
CAD_ENGINE_URL = os.environ.get("CAD_ENGINE_URL", "https://cad.abcx124.xyz")
LOCAL_ENGINE_URL = "http://localhost:8000"
ENGINE_TIMEOUT = 120  # seconds


def _find_engine():
    """Return the first reachable engine URL, preferring localhost for speed."""
    urls = [LOCAL_ENGINE_URL, CAD_ENGINE_URL]
    for url in urls:
        try:
            req = urllib.request.Request(f"{url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("ok"):
                    FreeCAD.Console.PrintMessage(f"[Digitizer] Engine found at {url}\n")
                    return url
        except Exception:
            continue
    return None


def _build_api_url(engine_url, path):
    """Build a full API URL, handling both localhost and HTTPS endpoints."""
    base = engine_url.rstrip("/")
    if base.startswith("http://localhost") or base.startswith("http://127."):
        # Local: direct to Python engine
        return f"{base}/api{path}"
    else:
        # Production: goes through nginx proxy at /py-api/
        return f"{base}/py-api{path}"


# ─── Import Image Command ──────────────────────────────────────────────────────

class ImportImageCommand:
    """Open a file dialog and import a furniture drawing image into FreeCAD."""

    def GetResources(self):
        return {
            "MenuText": "Import Drawing Image",
            "ToolTip": "Import a furniture drawing (PNG, JPEG, PDF) into the active document",
            "Pixmap": "",
        }

    def Activated(self):
        try:
            from PySide2 import QtWidgets
        except ImportError:
            try:
                from PySide import QtGui as QtWidgets
            except ImportError:
                FreeCAD.Console.PrintError(
                    "[Digitizer] PySide not available. Cannot open file dialog.\n"
                )
                return

        # Ensure there is an active document
        doc = FreeCAD.ActiveDocument
        if not doc:
            doc = FreeCAD.newDocument("FurnitureDrawing")
            FreeCAD.Console.PrintMessage("[Digitizer] Created new document: FurnitureDrawing\n")

        # Open file dialog
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Select Furniture Drawing",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;PDF Files (*.pdf);;All Files (*.*)",
        )

        if not filename:
            FreeCAD.Console.PrintMessage("[Digitizer] Import cancelled.\n")
            return

        FreeCAD.Console.PrintMessage(f"[Digitizer] Importing: {filename}\n")

        # Try Image workbench import (ImagePlane)
        imported = self._import_as_image_plane(filename, doc)
        if imported:
            FreeCAD.Console.PrintMessage(
                f"[Digitizer] Image imported as ImagePlane. Ready for 'Generate CAD Sketch'.\n"
            )
            doc.recompute()
            FreeCADGui.SendMsgToActiveView("ViewFit")
        else:
            FreeCAD.Console.PrintWarning(
                "[Digitizer] Could not import as ImagePlane. File selected but not loaded.\n"
                "Install the Image workbench (Tools → Addon Manager → Image) and try again.\n"
            )

    def _import_as_image_plane(self, filepath, doc):
        """Import an image file as an ImagePlane in the active document."""
        # Method 1: Use the Image workbench (FreeCAD 0.20+)
        try:
            import importlib
            spec = importlib.util.find_spec("ImageGui")
            if spec:
                import ImageGui
                ImageGui.open(filepath)
                FreeCAD.Console.PrintMessage("[Digitizer] Imported via Image workbench.\n")
                return True
        except Exception:
            pass

        # Method 2: Use ImportGui (may be available)
        try:
            import ImportGui
            ImportGui.insert(filepath, doc.Name)
            FreeCAD.Console.PrintMessage("[Digitizer] Imported via ImportGui.\n")
            return True
        except Exception:
            pass

        # Method 3: Load image manually as a texture on a plane (fallback)
        try:
            import Part
            import FreeCAD as App

            # Create a rectangle face sized to the image aspect ratio
            # We'll create a default plane; user scales later
            plane = doc.addObject("Part::Plane", "DrawingImage")
            plane.Length = 297  # A4 landscape mm
            plane.Width = 210

            # Position in the XY plane
            plane.Placement.Base = App.Vector(0, 0, 0)

            doc.recompute()
            FreeCAD.Console.PrintMessage(
                "[Digitizer] Created reference plane. Use Image workbench for proper image import.\n"
            )
            return True
        except Exception as e:
            FreeCAD.Console.PrintError(f"[Digitizer] All import methods failed: {e}\n")
            return False


# ─── Generate Sketch Command ───────────────────────────────────────────────────

class GenerateSketchCommand:
    """Send the imported image to the CAD engine and import the resulting DXF into FreeCAD."""

    def GetResources(self):
        return {
            "MenuText": "Generate CAD Sketch",
            "ToolTip": "Send drawing to CAD engine (OpenCV + AI) and generate a parametric DXF sketch",
            "Pixmap": "",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        if not doc:
            FreeCAD.Console.PrintError(
                "[Digitizer] No active document. Create a new document and import a drawing first.\n"
            )
            return

        # Find image objects in the document
        image_objects = _find_image_objects(doc)
        if not image_objects:
            FreeCAD.Console.PrintError(
                "[Digitizer] No image found in document.\n"
                "Use 'Import Drawing Image' first, or insert an image manually.\n"
            )
            return

        # Get the image file path
        img_path = _get_image_path(image_objects[0])
        if not img_path:
            FreeCAD.Console.PrintError(
                "[Digitizer] Cannot determine image file path. The image may be embedded.\n"
            )
            return

        if not Path(img_path).exists():
            FreeCAD.Console.PrintError(
                f"[Digitizer] Image file not found on disk: {img_path}\n"
                "The original file may have been moved or deleted.\n"
            )
            return

        # Find a reachable engine
        FreeCAD.Console.PrintMessage("[Digitizer] Searching for CAD engine...\n")
        engine_url = _find_engine()
        if not engine_url:
            FreeCAD.Console.PrintError(
                "[Digitizer] CAD engine not reachable.\n"
                f"Checked: {LOCAL_ENGINE_URL} and {CAD_ENGINE_URL}\n"
                "Start the Python engine:\n"
                "  cd backend-python && uvicorn app.main:app --port 8000\n"
            )
            return

        # Upload image to engine
        FreeCAD.Console.PrintMessage(f"[Digitizer] Uploading to {engine_url}...\n")
        result = self._upload_and_digitize(img_path, engine_url)
        if not result:
            return  # Error already printed

        # Report what was detected
        furniture = result.get("furniture", {})
        detected = result.get("detected", {})
        FreeCAD.Console.PrintMessage(
            f"[Digitizer] Furniture: {furniture.get('type', 'unknown')} "
            f"(confidence: {int(furniture.get('confidence', 0) * 100)}%)\n"
        )
        FreeCAD.Console.PrintMessage(
            f"[Digitizer] Detected: {detected.get('lines', 0)} lines, "
            f"{detected.get('circles', 0)} circles, "
            f"{detected.get('rectangles', 0)} rectangles, "
            f"{len(detected.get('dimensions', []))} dimensions\n"
        )

        # Download DXF
        dxf_file = result.get("dxf_file", "")
        if not dxf_file:
            FreeCAD.Console.PrintError("[Digitizer] Engine returned no DXF file.\n")
            return

        FreeCAD.Console.PrintMessage(f"[Digitizer] Downloading DXF: {dxf_file}...\n")
        dxf_content = self._download_dxf(dxf_file, engine_url)
        if not dxf_content:
            return  # Error already printed

        # Save DXF to temp file and import into FreeCAD
        self._import_dxf_into_freecad(dxf_content, dxf_file, doc)

        # Show warnings if any
        warnings = result.get("warnings", [])
        if warnings:
            FreeCAD.Console.PrintWarning("[Digitizer] Warnings:\n")
            for w in warnings:
                FreeCAD.Console.PrintWarning(f"  • {w}\n")

        FreeCAD.Console.PrintMessage("[Digitizer] Done! DXF imported into current document.\n")

    def _upload_and_digitize(self, img_path, engine_url):
        """Upload image to CAD engine and return the digitization result."""
        boundary = "----FreeCADDigitizerBoundary"
        filename = Path(img_path).name

        # Build multipart form data
        with open(img_path, "rb") as f:
            file_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        api_url = _build_api_url(engine_url, "/digitize")

        try:
            req = urllib.request.Request(api_url, data=body, method="POST")
            req.add_header(
                "Content-Type", f"multipart/form-data; boundary={boundary}"
            )
            with urllib.request.urlopen(req, timeout=ENGINE_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                if "error" in data:
                    FreeCAD.Console.PrintError(
                        f"[Digitizer] Engine error: {data['error']}\n"
                    )
                    return None
                return data
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode()[:500]
            except Exception:
                pass
            FreeCAD.Console.PrintError(
                f"[Digitizer] Engine HTTP {e.code}: {e.reason}\n{body_text}\n"
            )
            return None
        except urllib.error.URLError as e:
            FreeCAD.Console.PrintError(
                f"[Digitizer] Cannot reach engine at {api_url}: {e.reason}\n"
            )
            return None
        except Exception as e:
            FreeCAD.Console.PrintError(f"[Digitizer] Upload failed: {e}\n")
            return None

    def _download_dxf(self, dxf_filename, engine_url):
        """Download the DXF file from the CAD engine."""
        api_url = _build_api_url(engine_url, f"/download/{dxf_filename}")

        try:
            req = urllib.request.Request(api_url, method="GET")
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            FreeCAD.Console.PrintError(
                f"[Digitizer] DXF download HTTP {e.code}: {e.reason}\n"
            )
            return None
        except Exception as e:
            FreeCAD.Console.PrintError(f"[Digitizer] DXF download failed: {e}\n")
            return None

    def _import_dxf_into_freecad(self, dxf_content, dxf_filename, doc):
        """Save DXF to temp file and import into the active FreeCAD document."""
        try:
            # Save DXF to temp file
            tmp_path = Path(tempfile.gettempdir()) / f"freecad_digitizer_{dxf_filename}"
            with open(tmp_path, "wb") as f:
                f.write(dxf_content)

            FreeCAD.Console.PrintMessage(
                f"[Digitizer] DXF saved to temp: {tmp_path}\n"
            )

            # Try importing via importDXF module
            imported = False
            try:
                import importDXF
                importDXF.open(str(tmp_path))
                FreeCAD.Console.PrintMessage(
                    "[Digitizer] DXF imported via importDXF.\n"
                )
                imported = True
            except ImportError:
                pass
            except Exception as e:
                FreeCAD.Console.PrintWarning(
                    f"[Digitizer] importDXF failed: {e}\n"
                )

            # Fallback: try Draft workbench
            if not imported:
                try:
                    import Draft
                    Draft.importDXF.insert(str(tmp_path), doc.Name)
                    FreeCAD.Console.PrintMessage(
                        "[Digitizer] DXF imported via Draft workbench.\n"
                    )
                    imported = True
                except ImportError:
                    pass
                except Exception as e:
                    FreeCAD.Console.PrintWarning(
                        f"[Digitizer] Draft import failed: {e}\n"
                    )

            # Fallback: try ezdxf to extract entities manually
            if not imported:
                try:
                    self._import_via_ezdxf(tmp_path, doc)
                    imported = True
                except ImportError:
                    FreeCAD.Console.PrintWarning(
                        "[Digitizer] ezdxf not available in FreeCAD Python. "
                        "Install it: pip install ezdxf\n"
                    )
                except Exception as e:
                    FreeCAD.Console.PrintWarning(
                        f"[Digitizer] ezdxf import failed: {e}\n"
                    )

            if not imported:
                FreeCAD.Console.PrintError(
                    "[Digitizer] Could not import DXF automatically.\n"
                    f"DXF saved to: {tmp_path}\n"
                    "Import manually: File → Import → select the DXF file.\n"
                )
            else:
                doc.recompute()
                FreeCADGui.SendMsgToActiveView("ViewFit")

            # Don't delete temp file in case manual import is needed
            # tmp_path.unlink(missing_ok=True)

        except Exception as e:
            FreeCAD.Console.PrintError(
                f"[Digitizer] Failed to save/import DXF: {e}\n"
            )

    def _import_via_ezdxf(self, dxf_path, doc):
        """Import DXF entities into FreeCAD using ezdxf to read + Part/Draft to create."""
        import ezdxf
        import Part
        import FreeCAD as App

        dxf_doc = ezdxf.readfile(str(dxf_path))
        msp = dxf_doc.modelspace()

        entity_count = 0

        for entity in msp:
            etype = entity.dxftype()

            if etype == "LINE":
                start = entity.dxf.start
                end = entity.dxf.end
                line = Part.LineSegment(
                    App.Vector(start.x, start.y, 0),
                    App.Vector(end.x, end.y, 0),
                )
                obj = doc.addObject("Part::Feature", "Line")
                obj.Shape = line.toShape()
                entity_count += 1

            elif etype == "CIRCLE":
                center = entity.dxf.center
                radius = entity.dxf.radius
                circle = Part.Circle(
                    App.Vector(center.x, center.y, 0),
                    App.Vector(0, 0, 1),
                    radius,
                )
                obj = doc.addObject("Part::Feature", "Circle")
                obj.Shape = circle.toShape()
                entity_count += 1

            elif etype == "ARC":
                center = entity.dxf.center
                radius = entity.dxf.radius
                start_angle = entity.dxf.start_angle
                end_angle = entity.dxf.end_angle
                arc = Part.ArcOfCircle(
                    Part.Circle(
                        App.Vector(center.x, center.y, 0),
                        App.Vector(0, 0, 1),
                        radius,
                    ),
                    start_angle * 0.0174533,  # degrees to radians
                    end_angle * 0.0174533,
                )
                obj = doc.addObject("Part::Feature", "Arc")
                obj.Shape = arc.toShape()
                entity_count += 1

            elif etype == "LWPOLYLINE":
                points = entity.get_points()
                if len(points) >= 2:
                    vectors = [
                        App.Vector(p[0], p[1], 0) for p in points
                    ]
                    if entity.closed and len(vectors) > 2:
                        vectors.append(vectors[0])  # close the polygon
                    wire = Part.makePolygon(vectors)
                    obj = doc.addObject("Part::Feature", "Polyline")
                    obj.Shape = wire
                    entity_count += 1

        FreeCAD.Console.PrintMessage(
            f"[Digitizer] ezdxf: imported {entity_count} entities.\n"
        )


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _find_image_objects(doc):
    """Return all image-like objects in the document."""
    image_types = [
        "Image::ImagePlane",
        "App::ImagePlane",
        "Image::ImageFile",
    ]
    results = []
    for obj in doc.Objects:
        if obj.TypeId in image_types:
            results.append(obj)
    if not results:
        # Fallback: look for objects with ImageFile property
        for obj in doc.Objects:
            if hasattr(obj, "ImageFile") and obj.ImageFile:
                results.append(obj)
    return results


def _get_image_path(image_obj):
    """Extract the file path from a FreeCAD image object."""
    if hasattr(image_obj, "ImageFile") and image_obj.ImageFile:
        return image_obj.ImageFile
    if hasattr(image_obj, "SourceFile") and image_obj.SourceFile:
        return image_obj.SourceFile
    return None


# ─── Register Commands with FreeCAD ────────────────────────────────────────────

FreeCADGui.addCommand("Digitizer_ImportImage", ImportImageCommand())
FreeCADGui.addCommand("Digitizer_GenerateSketch", GenerateSketchCommand())
