"""
CAD Scaler Digitizer — Python FastAPI Backend
Uses modular backend/ package for all processing.
"""
import os, tempfile, uuid, shutil, asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Load .env for OPENAI_API_KEY
_env_path = Path(__file__).parent.parent / '.env'
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                if not os.environ.get(_k):
                    os.environ[_k] = _v.strip().strip('"').strip("'")

from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles, normalize_lines
from app.backend.ocr import ocr_dimensions
from app.backend.geometry_cleanup import process_constraints
from app.backend.vision import normalize_lines
from app.backend.dimension_validator import autocorrect_dimensions, validate_scale
from app.backend.furniture_classifier import classify_furniture
from app.backend.dxf_exporter import save_generic, save_round_pedestal_table, save_rectangular_table, save_cabinet, save_sofa

app = FastAPI(title="CAD Scaler Digitizer", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

OUT = Path(tempfile.gettempdir()) / "cad_digitizer_outputs"
OUT.mkdir(exist_ok=True)
UPLOAD = Path(tempfile.gettempdir()) / "cad_digitizer_uploads"
UPLOAD.mkdir(exist_ok=True)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


@app.get("/health")
def health():
    return {"ok": True, "engine": "opencv+ocr+ezdxf+v2", "version": "2.0.0", "hybrid": bool(OPENAI_API_KEY)}


def _process_opencv(image_path, job_id, real_width_cm=None, real_height_cm=None, furniture_override=None):
    """Standard OpenCV pipeline."""
    img, gray = load_image(str(image_path))
    binary = preprocess(gray)
    lines_raw = detect_lines(binary)
    lines = normalize_lines(lines_raw)
    circles = detect_circles(gray)
    rects = detect_rectangles(binary)
    ocr_lines, dims = ocr_dimensions(str(image_path))

    constrained = process_constraints(lines, circles, dims, rects)

    pixel_measurements = {}
    if constrained['circles']:
        pixel_measurements['diameter'] = constrained['circles'][0][2] * 2
    if constrained['lines']:
        xs = [p[0] for ln in constrained['lines'] for p in ln]
        if xs:
            pixel_measurements['width'] = max(xs) - min(xs)
    corrected_dims = autocorrect_dimensions(dims, pixel_measurements)

    if furniture_override:
        furniture = {"type": furniture_override, "confidence": 1.0}
    else:
        furniture = classify_furniture(ocr_lines, constrained['circles'], constrained['lines'], constrained.get('rects'))

    dxf_name = f'{job_id}_digitized.dxf'
    dxf_path = OUT / dxf_name
    warnings = []
    scale, scale_conf, scale_warnings = validate_scale(corrected_dims, constrained['lines'])
    warnings.extend(scale_warnings)

    ftype = furniture['type']
    if ftype == 'round_pedestal_table':
        from app.backend.dxf_exporter import save_round_pedestal_table as sfn
        dia = real_width_cm or next((d['value_cm'] for d in corrected_dims if any(t in d.get('tag','') for t in ['dia','diameter','w','width'])), 80.0)
        height = real_height_cm or next((d['value_cm'] for d in corrected_dims if any(t in d.get('tag','') for t in ['h','height'])), 70.0)
        sfn(str(dxf_path), top_dia_cm=dia, height_cm=height)
        warnings.append(f"Reconstructed: Round Table O{dia:.0f}xH{height:.0f}cm")
    elif ftype == 'rectangular_table':
        w = real_width_cm or next((d['value_cm'] for d in corrected_dims if 'w' in d.get('tag','')), 120.0)
        h = real_height_cm or next((d['value_cm'] for d in corrected_dims if 'h' in d.get('tag','')), 70.0)
        save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=w*0.67, height_cm=h)
        warnings.append(f"Reconstructed: Rect Table {w:.0f}x{h:.0f}cm")
    elif ftype == 'cabinet':
        save_cabinet(str(dxf_path))
        warnings.append("Reconstructed: Cabinet")
    elif ftype == 'sofa':
        save_sofa(str(dxf_path))
        warnings.append("Reconstructed: Sofa")
    else:
        save_generic(str(dxf_path), constrained['lines'], constrained['circles'], constrained.get('rects'))
        warnings.append(f"Generic tracing at scale {scale:.4f}")

    return {'job_id': job_id, 'download': f'/api/download/{dxf_name}', 'dxf_file': dxf_name,
            'furniture': furniture, 'warnings': warnings,
            'detected': {'lines': len(constrained['lines']), 'circles': len(constrained['circles']),
                        'rectangles': len(constrained.get('rects', [])), 'dimensions': corrected_dims,
                        'scale': round(scale, 4)},
            'constraint_engine': {'enabled': True, 'circles_rebuilt': constrained.get('rebuilt_circles', 0)}}


async def _process_hybrid(image_path, job_id, real_width_cm=None, real_height_cm=None, furniture_override=None):
    """Hybrid: OpenCV + OpenAI Vision."""
    if not OPENAI_API_KEY:
        return {"error": "Hybrid mode requires OPENAI_API_KEY in backend-python/.env"}

    from app.backend.vision import load_image as li, preprocess as pp, detect_lines as dl, detect_circles as dc, detect_rectangles as dr, normalize_lines as nl
    from app.backend.ocr import ocr_dimensions as od
    from app.backend.furniture_classifier import classify_furniture as cf

    img, gray = li(str(image_path))
    binary = pp(gray)
    from app.backend.geometry_cleanup import snap_line_angle, snap_endpoints, merge_collinear
    lines_raw = dl(binary)
    lines = snap_endpoints(merge_collinear([snap_line_angle(l) for l in lines_raw]))
    circles = dc(gray)
    rects = dr(binary)
    ocr_lines, dims = od(str(image_path))

    # OpenAI analysis
    import httpx, base64, json
    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    ext = os.path.splitext(str(image_path))[1].lower()
    mime = {'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp'}.get(ext, 'image/png')

    ai_result = {"furniture_type": "", "confidence": 0, "dimensions": [], "views_detected": []}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model": "gpt-4o", "messages": [
                    {"role": "system", "content": "Analyze this furniture drawing. Return JSON with furniture_type, confidence, dimensions array, views_detected array."},
                    {"role": "user", "content": [{"type":"text","text":"Identify this furniture and extract dimensions."},
                        {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}","detail":"high"}}]}
                ], "max_tokens": 2000, "response_format": {"type": "json_object"}})
            if r.status_code == 200:
                data = r.json()
                ai_result = json.loads(data['choices'][0]['message']['content'])
    except Exception as e:
        print(f"[Hybrid] OpenAI error: {e}")

    # Merge AI + OpenCV
    ftype = furniture_override or ai_result.get('furniture_type', '')
    ai_conf = ai_result.get('confidence', 0)
    if not ftype or ai_conf < 0.5:
        cv = cf(ocr_lines, circles, lines, rects)
        ftype = cv['type']

    furniture = {"type": ftype, "confidence": max(ai_conf, 0.5), "hybrid": True}

    dxf_name = f'{job_id}_hybrid.dxf'
    dxf_path = OUT / dxf_name
    warnings = [f"Hybrid mode: AI identified as {ftype}"]

    if ftype == 'round_pedestal_table':
        dia = real_width_cm or next((d.get('value_cm',0) for d in ai_result.get('dimensions',[]) if 'dia' in str(d).lower()), 80.0)
        height = real_height_cm or next((d.get('value_cm',0) for d in ai_result.get('dimensions',[]) if 'height' in str(d).lower()), 70.0)
        save_round_pedestal_table(str(dxf_path), top_dia_cm=dia, height_cm=height)
    else:
        save_generic(str(dxf_path), lines, circles, rects)

    return {'job_id': job_id, 'download': f'/api/download/{dxf_name}', 'dxf_file': dxf_name,
            'furniture': furniture, 'warnings': warnings,
            'detected': {'lines': len(lines), 'circles': len(circles), 'rectangles': len(rects),
                        'dimensions': dims, 'ai_analysis': ai_result}}


@app.post("/api/digitize")
async def digitize(file: UploadFile = File(...), real_width_cm: float = Form(None),
                   real_height_cm: float = Form(None), furniture_type: str = Form(None)):
    try:
        ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
        job_id = str(uuid.uuid4())
        safe = f"{job_id}_{uuid.uuid4().hex[:8]}"
        img_path = UPLOAD / f"{safe}{ext}"
        with img_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        result = _process_opencv(str(img_path), job_id, real_width_cm, real_height_cm, furniture_type)
        try: os.remove(str(img_path))
        except: pass
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/digitize/hybrid")
async def digitize_hybrid(file: UploadFile = File(...), real_width_cm: float = Form(None),
                          real_height_cm: float = Form(None), furniture_type: str = Form(None)):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "Hybrid requires OPENAI_API_KEY in backend-python/.env"}, status_code=400)
    try:
        ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
        job_id = str(uuid.uuid4())
        safe = f"{job_id}_{uuid.uuid4().hex[:8]}"
        img_path = UPLOAD / f"{safe}{ext}"
        with img_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        result = await _process_hybrid(str(img_path), job_id, real_width_cm, real_height_cm, furniture_type)
        try: os.remove(str(img_path))
        except: pass
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": f"Hybrid failed: {e}"}, status_code=500)


@app.get("/api/download/{filename}")
def download(filename: str):
    safe = os.path.basename(filename)
    path = OUT / safe
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(path, filename=safe, media_type="application/dxf")
