"""
CAD Scaler Digitizer — Python FastAPI Backend
Provides OpenCV primitive detection, OCR dimension extraction,
furniture classification, and ezdxf DXF generation.

Endpoints:
- GET  /health
- POST /api/digitize  (upload image/PDF, get DXF download link)
- POST /api/digitize/hybrid (OpenCV + OpenAI Vision cross-validation)
- GET  /api/download/<filename>
"""
import os
import tempfile
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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

ALLOWED_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg',
    'image/webp', 'image/bmp', 'image/tiff',
    'application/pdf'
}

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


@app.get("/health")
def health():
    return {
        "ok": True,
        "engine": "opencv+ocr+ezdxf+furniture_templates",
        "version": "2.0.0",
        "hybrid": bool(OPENAI_API_KEY)
    }


async def _save_upload(file: UploadFile, job_id: str) -> Path:
    """Save uploaded file, handling PDF conversion."""
    ext = os.path.splitext(file.filename or 'image.png')[1] or '.png'
    safe_name = f"{job_id}_{uuid.uuid4().hex[:8]}"
    img_path = UPLOAD / f"{safe_name}{ext}"

    with img_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Convert PDF to image
    if file.content_type == 'application/pdf' or ext == '.pdf':
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(str(img_path), dpi=200, first_page=1, last_page=1)
            if not images:
                raise ValueError("PDF is empty")
            png_path = UPLOAD / f"{safe_name}.png"
            images[0].save(str(png_path), 'PNG')
            os.remove(str(img_path))
            return png_path
        except ImportError:
            raise ValueError("PDF support requires pdf2image: pip install pdf2image")
        except Exception as e:
            raise ValueError(f"PDF conversion failed: {e}")

    return img_path


def _validate_file(file: UploadFile) -> None:
    """Validate file type."""
    ext = os.path.splitext(file.filename or '')[1].lower()
    allowed_exts = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.pdf'}
    if file.content_type not in ALLOWED_TYPES and ext not in allowed_exts:
        raise ValueError(f"Unsupported file type: {file.content_type}. Use PNG, JPEG, or PDF.")


@app.post("/api/digitize")
async def digitize(
    file: UploadFile = File(...),
    real_width_cm: float = Form(None),
    real_height_cm: float = Form(None),
    furniture_type: str = Form(None)
):
    """
    Process a drawing using OpenCV + OCR + template reconstruction.
    Fast and free — runs entirely on your machine.
    """
    try:
        _validate_file(file)
        job_id = str(uuid.uuid4())
        img_path = await _save_upload(file, job_id)

        result = process_image(
            str(img_path),
            out_dir=str(OUT),
            job_id=job_id,
            real_width_cm=real_width_cm,
            real_height_cm=real_height_cm,
            furniture_override=furniture_type
        )

        try:
            os.remove(str(img_path))
        except Exception:
            pass

        return JSONResponse(result)

    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Processing failed: {str(e)}"}, status_code=500)


@app.post("/api/digitize/hybrid")
async def digitize_hybrid(
    file: UploadFile = File(...),
    real_width_cm: float = Form(None),
    real_height_cm: float = Form(None),
    furniture_type: str = Form(None)
):
    """
    PROCESS WITH MAXIMUM ACCURACY — Hybrid Mode.

    Combines:
    1. OpenCV — exact line/circle/rectangle geometry detection
    2. Tesseract + PaddleOCR — dual OCR for text/dimensions
    3. OpenAI GPT-4o Vision — semantic understanding of furniture type
    4. Cross-validation — merges all sources for best result

    Requires OPENAI_API_KEY environment variable.
    """
    if not OPENAI_API_KEY:
        return JSONResponse(
            {"error": "Hybrid mode requires OPENAI_API_KEY environment variable. Set it in backend-python/.env"},
            status_code=400
        )

    try:
        _validate_file(file)
        job_id = str(uuid.uuid4())
        img_path = await _save_upload(file, job_id)

        from app.engine.hybrid import process_hybrid
        result = await process_hybrid(
            str(img_path),
            out_dir=str(OUT),
            job_id=job_id,
            openai_api_key=OPENAI_API_KEY,
            real_width_cm=real_width_cm,
            real_height_cm=real_height_cm,
            furniture_override=furniture_type
        )

        try:
            os.remove(str(img_path))
        except Exception:
            pass

        return JSONResponse(result)

    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Hybrid processing failed: {str(e)}"}, status_code=500)


@app.get("/api/download/{filename}")
def download(filename: str):
    """Download a generated DXF file by filename."""
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
