"""
CAD Scaler Digitizer — Python FastAPI Backend
Provides OpenCV primitive detection, OCR dimension extraction,
furniture classification, and ezdxf DXF generation.

Endpoints:
- GET  /health
- POST /api/digitize  (upload image/PDF, get DXF download link)
- GET  /api/download/<filename>
"""
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile
import uuid
import shutil
import os
from app.engine.pipeline import process_image

app = FastAPI(
    title="CAD Scaler Digitizer Furniture Engine",
    version="2.0.0",
    description="Upload furniture drawings → get scaled DXF with editable polylines"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUT = Path(tempfile.gettempdir()) / "cad_digitizer_outputs"
OUT.mkdir(exist_ok=True)

UPLOAD = Path(tempfile.gettempdir()) / "cad_digitizer_uploads"
UPLOAD.mkdir(exist_ok=True)

# Allowed image/PDF types
ALLOWED_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg',
    'image/webp', 'image/bmp', 'image/tiff',
    'application/pdf'
}


@app.get("/health")
def health():
    return {
        "ok": True,
        "engine": "opencv+ocr+ezdxf+furniture_templates",
        "version": "2.0.0"
    }


@app.post("/api/digitize")
async def digitize(
    file: UploadFile = File(...),
    real_width_cm: float = Form(None),
    real_height_cm: float = Form(None),
    furniture_type: str = Form(None)
):
    """
    Upload a furniture drawing (PNG, JPEG, PDF) and get a scaled DXF back.

    Args:
        file: The image or PDF file.
        real_width_cm: Optional known width in cm for scale calibration.
        real_height_cm: Optional known height in cm for scale calibration.
        furniture_type: Optional override furniture type.

    Returns:
        JSON with job_id, download URL, furniture classification, and detected features.
    """
    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        # Check extension as fallback
        ext = os.path.splitext(file.filename or '')[1].lower()
        if ext not in {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.pdf'}:
            return JSONResponse(
                {"error": f"Unsupported file type: {file.content_type}. Use PNG, JPEG, or PDF."},
                status_code=400
            )

    job_id = str(uuid.uuid4())
    safe_name = f"{job_id}_{uuid.uuid4().hex[:8]}"
    ext = os.path.splitext(file.filename or 'image.png')[1] or '.png'
    img_path = UPLOAD / f"{safe_name}{ext}"

    # Save uploaded file
    with img_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Handle PDF: convert first page to image
    if file.content_type == 'application/pdf' or ext == '.pdf':
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(str(img_path), dpi=200, first_page=1, last_page=1)
            if images:
                png_path = UPLOAD / f"{safe_name}.png"
                images[0].save(str(png_path), 'PNG')
                img_path = png_path
            else:
                return JSONResponse({"error": "PDF is empty"}, status_code=400)
        except ImportError:
            return JSONResponse(
                {"error": "PDF support requires pdf2image. Install: pip install pdf2image"},
                status_code=500
            )
        except Exception as e:
            return JSONResponse(
                {"error": f"PDF conversion failed: {str(e)}"},
                status_code=400
            )

    # Run the pipeline
    try:
        result = process_image(
            str(img_path),
            out_dir=str(OUT),
            job_id=job_id,
            real_width_cm=real_width_cm,
            real_height_cm=real_height_cm,
            furniture_override=furniture_type
        )
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": f"Processing failed: {str(e)}"}, status_code=500)
    finally:
        # Clean up upload
        try:
            os.remove(str(img_path))
        except Exception:
            pass


@app.get("/api/download/{filename}")
def download(filename: str):
    """Download a generated DXF file by filename."""
    # Security: prevent path traversal
    safe_name = os.path.basename(filename)
    path = OUT / safe_name
    if not path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(path, filename=safe_name, media_type="application/dxf")


@app.get("/api/download/raw/{filename}")
def download_raw(filename: str):
    """Download raw upload file (for debugging)."""
    safe_name = os.path.basename(filename)
    path = UPLOAD / safe_name
    if not path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(path, filename=safe_name)
