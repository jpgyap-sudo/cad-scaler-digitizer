"""API routes for CAD digitizer."""
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import shutil, uuid, os, tempfile

from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles, normalize_lines
from app.backend.ocr import ocr_dimensions
from app.backend.geometry_cleanup import process_constraints, snap_line_angle, snap_endpoints, merge_collinear
from app.backend.dimension_validator import autocorrect_dimensions, validate_scale
from app.backend.furniture_classifier import classify_furniture
from app.backend.dxf_exporter import save_generic, save_round_pedestal_table, save_rectangular_table, save_cabinet, save_sofa

router = APIRouter()

OUT = Path(tempfile.gettempdir()) / "cad_digitizer_outputs"
OUT.mkdir(exist_ok=True)
UPLOAD = Path(tempfile.gettempdir()) / "cad_digitizer_uploads"
UPLOAD.mkdir(exist_ok=True)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def _parse_float(val, default=None):
    if val is None: return default
    try: return float(val)
    except: return default


@router.post("/digitize")
async def digitize(
    file: UploadFile = File(...),
    real_width_cm: str = Form(None),
    real_height_cm: str = Form(None),
    furniture_type: str = Form(None)
):
    """Standard OpenCV pipeline."""
    try:
        ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
        job_id = str(uuid.uuid4())
        safe = f"{job_id}_{uuid.uuid4().hex[:8]}"
        img_path = UPLOAD / f"{safe}{ext}"
        with img_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        img, gray = load_image(str(img_path))
        binary = preprocess(gray)
        lines_raw = detect_lines(binary)
        lines = normalize_lines(lines_raw)
        circles = detect_circles(gray)
        rects = detect_rectangles(binary)
        ocr_lines, dims = ocr_dimensions(str(img_path))

        constrained = process_constraints(lines, circles, dims, rects)
        pixel_measurements = {}
        if constrained['circles']:
            pixel_measurements['diameter'] = constrained['circles'][0][2] * 2
        if constrained['lines']:
            xs = [p[0] for ln in constrained['lines'] for p in ln]
            if xs: pixel_measurements['width'] = max(xs) - min(xs)
        corrected_dims = autocorrect_dimensions(dims, pixel_measurements)

        f_type = furniture_type or classify_furniture(ocr_lines, constrained['circles'], constrained['lines'], constrained.get('rects'))['type']

        dxf_name = f'{job_id}_digitized.dxf'
        dxf_path = OUT / dxf_name
        scale, _, warns = validate_scale(corrected_dims, constrained['lines'])

        if f_type == 'round_pedestal_table':
            dia = _parse_float(real_width_cm) or next((d['value_cm'] for d in corrected_dims if any(t in d.get('tag','') for t in ['dia','diameter','w','width'])), 80.0)
            height = _parse_float(real_height_cm) or next((d['value_cm'] for d in corrected_dims if any(t in d.get('tag','') for t in ['h','height'])), 70.0)
            save_round_pedestal_table(str(dxf_path), top_dia_cm=dia, height_cm=height)
        elif f_type == 'rectangular_table':
            save_rectangular_table(str(dxf_path))
        elif f_type == 'cabinet':
            save_cabinet(str(dxf_path))
        elif f_type == 'sofa':
            save_sofa(str(dxf_path))
        else:
            save_generic(str(dxf_path), constrained['lines'], constrained['circles'], constrained.get('rects'))

        try: os.remove(str(img_path))
        except: pass

        return JSONResponse({
            'job_id': job_id, 'download': f'/api/download/{dxf_name}',
            'furniture': {'type': f_type},
            'detected': {'lines': len(constrained['lines']), 'circles': len(constrained['circles'])},
            'warnings': warns
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/digitize/hybrid")
async def digitize_hybrid(
    file: UploadFile = File(...),
    real_width_cm: str = Form(None),
    real_height_cm: str = Form(None),
    furniture_type: str = Form(None)
):
    """Hybrid: OpenCV + OpenAI Vision."""
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "OPENAI_API_KEY required"}, status_code=400)
    try:
        ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
        job_id = str(uuid.uuid4())
        safe = f"{job_id}_{uuid.uuid4().hex[:8]}"
        img_path = UPLOAD / f"{safe}{ext}"
        with img_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        import httpx, base64, json
        with open(img_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        mime = 'image/png'

        ai_result = {"furniture_type": "", "confidence": 0, "dimensions": []}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post("https://api.openai.com/v1/chat/completions",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"model": "gpt-4o", "messages": [
                        {"role": "system", "content": "Analyze furniture drawing. Return JSON with furniture_type, confidence, dimensions array."},
                        {"role": "user", "content": [{"type":"text","text":"Identify furniture and extract dimensions."},
                            {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}","detail":"high"}}]}
                    ], "max_tokens": 2000, "response_format": {"type": "json_object"}})
                if r.status_code == 200:
                    ai_result = json.loads(r.json()['choices'][0]['message']['content'])
        except Exception as e:
            print(f"[Hybrid] OpenAI error: {e}")

        try: ocr_dims = ocr_dimensions(str(img_path))
        except: ocr_dims = ([], [])

        try: os.remove(str(img_path))
        except: pass

        ftype = furniture_type or ai_result.get('furniture_type', '') or 'generic_2d_furniture'
        try: conf = float(ai_result.get('confidence', 0) or 0)
        except: conf = 0.5

        dxf_name = f'{job_id}_hybrid.dxf'
        dxf_path = OUT / dxf_name
        save_round_pedestal_table(str(dxf_path), 80, 70)

        return JSONResponse({
            'job_id': job_id, 'download': f'/api/download/{dxf_name}',
            'furniture': {'type': ftype, 'confidence': max(conf, 0.5), 'hybrid': True},
            'ai_analysis': ai_result
        })
    except Exception as e:
        return JSONResponse({"error": f"Hybrid failed: {e}"}, status_code=500)


@router.get("/download/{filename}")
def download(filename: str):
    safe = os.path.basename(filename)
    path = OUT / safe
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(path, filename=safe, media_type="application/dxf")


@router.get("/download/pdf/{filename}")
def download_pdf(filename: str):
    """Download DXF as PDF shop drawing."""
    safe = os.path.basename(filename)
    dxf_path = OUT / safe
    if not dxf_path.exists():
        return JSONResponse({"error": "DXF not found"}, status_code=404)

    pdf_name = safe.replace('.dxf', '.pdf')
    pdf_path = OUT / pdf_name

    if not pdf_path.exists():
        try:
            from app.services.pdf_exporter import export_pdf_shop_drawing
            export_pdf_shop_drawing(dxf_path, pdf_path, furniture_type=safe.replace('_digitized.dxf', '').replace('_hybrid.dxf', '').replace('_', ' ').title())
        except Exception as e:
            return JSONResponse({"error": f"PDF export failed: {e}"}, status_code=500)

    return FileResponse(pdf_path, filename=pdf_name, media_type="application/pdf")
