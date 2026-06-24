"""API routes for CAD digitizer."""
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import shutil, uuid, os, tempfile

from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles, normalize_lines
from app.backend.ocr import ocr_dimensions
from app.backend.geometry_cleanup import process_constraints, snap_line_angle, snap_endpoints, merge_collinear
from app.backend.dimension_validator import autocorrect_dimensions, validate_scale
from app.backend.furniture_classifier import classify_furniture, normalize_furniture_type
from app.backend.semantic_proportion_validator import validate_furniture_proportions
from app.backend.dxf_exporter import (
    save_generic, save_round_pedestal_table, save_rectangular_table,
    save_cabinet, save_sofa, save_coffee_table, save_dining_chair,
    save_wardrobe, save_reception_counter
)

router = APIRouter()

OUT = Path(tempfile.gettempdir()) / "cad_digitizer_outputs"
OUT.mkdir(exist_ok=True)
UPLOAD = Path(tempfile.gettempdir()) / "cad_digitizer_uploads"
UPLOAD.mkdir(exist_ok=True)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def _parse_float(val, default=None):
    if val is None:
        return default
    try:
        return float(val)
    except Exception:
        return default


def count_feedback() -> int:
    """Count feedback JSONL entries."""
    from app.services.ml_engine import get_feedback_count
    return get_feedback_count()


def _dispatch_furniture(f_type, dxf_path, corrected_dims, real_w, real_h):
    """Route furniture type to the correct DXF template, applying user-overridden dimensions."""

    def _dim(tags, default):
        """Pull first matching dimension from corrected_dims."""
        for d in corrected_dims:
            if any(t in d.get('tag', '') for t in tags):
                return d['value_cm']
        return default

    if f_type == 'round_pedestal_table':
        dia = real_w or _dim(['dia', 'diameter', 'w', 'width'], 80.0)
        height = real_h or _dim(['h', 'height'], 70.0)
        save_round_pedestal_table(str(dxf_path), top_dia_cm=dia, height_cm=height)

    elif f_type == 'rectangular_table':
        w = real_w or _dim(['w', 'width'], 120.0)
        h = real_h or _dim(['h', 'height'], 70.0)
        d = _dim(['d', 'depth'], 80.0)
        save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)

    elif f_type == 'cabinet':
        w = real_w or _dim(['w', 'width'], 100.0)
        h = real_h or _dim(['h', 'height'], 180.0)
        d = _dim(['d', 'depth'], 50.0)
        save_cabinet(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)

    elif f_type == 'sofa':
        w = real_w or _dim(['w', 'width'], 200.0)
        h = real_h or _dim(['h', 'height'], 85.0)
        d = _dim(['d', 'depth'], 80.0)
        save_sofa(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)

    elif f_type == 'coffee_table':
        w = real_w or _dim(['w', 'width', 'dia', 'diameter'], 100.0)
        h = real_h or _dim(['h', 'height'], 45.0)
        save_coffee_table(str(dxf_path), width_cm=w, height_cm=h)

    elif f_type in ('dining_chair', 'chair'):
        w = real_w or _dim(['w', 'width', 'seat'], 45.0)
        h = real_h or _dim(['h', 'height'], 90.0)
        save_dining_chair(str(dxf_path), width_cm=w, height_cm=h)

    elif f_type == 'wardrobe':
        w = real_w or _dim(['w', 'width'], 120.0)
        h = real_h or _dim(['h', 'height'], 200.0)
        save_wardrobe(str(dxf_path), width_cm=w, height_cm=h)

    elif f_type == 'reception_counter':
        w = real_w or _dim(['w', 'width'], 180.0)
        h = real_h or _dim(['h', 'height'], 110.0)
        save_reception_counter(str(dxf_path), width_cm=w, height_cm=h)

    elif f_type == 'bed_headboard':
        w = real_w or _dim(['w', 'width'], 160.0)
        h = real_h or _dim(['h', 'height'], 120.0)
        # Fall through to generic until bed template is added
        save_generic(str(dxf_path), [], [], [])

    else:
        # True generic fallback
        save_generic(str(dxf_path), [], [], [])


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
            if xs:
                pixel_measurements['width'] = max(xs) - min(xs)
            ys = [p[1] for ln in constrained['lines'] for p in ln]
            if ys:
                pixel_measurements['height'] = max(ys) - min(ys)

        corrected_dims = autocorrect_dimensions(dims, pixel_measurements)

        # Furniture classification
        classifier_result = classify_furniture(
            ocr_lines, constrained['circles'], constrained['lines'], constrained.get('rects')
        )
        f_type = normalize_furniture_type(furniture_type or classifier_result['type'])
        confidence = classifier_result.get('confidence', 0.5)

        dxf_name = f'{job_id}_digitized.dxf'
        dxf_path = OUT / dxf_name
        scale, _, warns = validate_scale(corrected_dims, constrained['lines'])

        real_w = _parse_float(real_width_cm)
        real_h = _parse_float(real_height_cm)
        _dispatch_furniture(f_type, dxf_path, corrected_dims, real_w, real_h)

        try:
            os.remove(str(img_path))
        except Exception:
            pass

        return JSONResponse({
            'job_id': job_id,
            'dxf_file': dxf_name,
            'download': f'/api/download/{dxf_name}',
            'furniture': {
                'type': f_type,
                'confidence': confidence,
                'required_dimensions': classifier_result.get('required_dimensions', []),
                'recommended_template': classifier_result.get('recommended_template', ''),
            },
            'detected': {
                'lines': len(constrained['lines']),
                'circles': len(constrained['circles']),
                'rectangles': len(constrained.get('rects', [])),
                'dimensions': corrected_dims,
                'ocr_lines': ocr_lines[:20],  # limit payload
            },
            'warnings': warns
        })
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


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
                        {"role": "system", "content": "Analyze furniture drawing. Return JSON with furniture_type (string), confidence (0-1 float), dimensions array [{tag, value_cm}]."},
                        {"role": "user", "content": [{"type": "text", "text": "Identify furniture and extract all dimensions."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}}]}
                    ], "max_tokens": 2000, "response_format": {"type": "json_object"}})
                if r.status_code == 200:
                    ai_result = json.loads(r.json()['choices'][0]['message']['content'])
        except Exception as e:
            print(f"[Hybrid] OpenAI error: {e}")

        # Also run OpenCV pipeline for geometry
        img, gray = load_image(str(img_path))
        binary = preprocess(gray)
        lines_raw = detect_lines(binary)
        lines = normalize_lines(lines_raw)
        circles = detect_circles(gray)
        rects = detect_rectangles(binary)
        ocr_lines, dims = ocr_dimensions(str(img_path))
        constrained = process_constraints(lines, circles, dims, rects)
        corrected_dims = autocorrect_dimensions(dims, {})

        try:
            os.remove(str(img_path))
        except Exception:
            pass

        ftype = normalize_furniture_type(furniture_type or ai_result.get('furniture_type', '') or 'generic_2d_furniture')
        try:
            conf = float(ai_result.get('confidence', 0) or 0)
        except Exception:
            conf = 0.5

        # Merge AI dimensions with OCR dims
        ai_dims = ai_result.get('dimensions', []) or []
        merged_dims = corrected_dims + [
            {'tag': d.get('tag', ''), 'value_cm': float(d.get('value_cm', 0)), 'raw': str(d)}
            for d in ai_dims if isinstance(d, dict)
        ]

        dxf_name = f'{job_id}_hybrid.dxf'
        dxf_path = OUT / dxf_name

        real_w = _parse_float(real_width_cm)
        real_h = _parse_float(real_height_cm)
        _dispatch_furniture(ftype, dxf_path, merged_dims, real_w, real_h)

        return JSONResponse({
            'job_id': job_id,
            'dxf_file': dxf_name,
            'download': f'/api/download/{dxf_name}',
            'furniture': {'type': ftype, 'confidence': max(conf, 0.5), 'hybrid': True},
            'detected': {
                'lines': len(constrained['lines']),
                'circles': len(constrained['circles']),
                'rectangles': len(constrained.get('rects', [])),
                'dimensions': merged_dims,
                'ocr_lines': ocr_lines[:20],
            },
            'ai_analysis': ai_result,
            'warnings': [],
        })
    except Exception as e:
        import traceback
        return JSONResponse({"error": f"Hybrid failed: {e}", "trace": traceback.format_exc()}, status_code=500)


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
            export_pdf_shop_drawing(dxf_path, pdf_path,
                furniture_type=safe.replace('_digitized.dxf', '').replace('_hybrid.dxf', '')
                               .replace('_', ' ').title())
        except Exception as e:
            return JSONResponse({"error": f"PDF failed: {e}"}, status_code=500)
    return FileResponse(pdf_path, filename=pdf_name, media_type="application/pdf")


@router.post("/export/freecad")
async def export_freecad(file: UploadFile = File(...)):
    """Convert DXF to FreeCAD FCStd parametric model."""
    job_id = str(uuid.uuid4())
    dxf_path = OUT / f"{job_id}_input.dxf"
    fcstd_path = OUT / f"{job_id}_model.FCStd"
    with dxf_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    from app.services.freecad_exporter import export_freecad_fcstd
    ok = export_freecad_fcstd(dxf_path, fcstd_path, furniture_type="furniture")
    try:
        os.unlink(str(dxf_path))
    except Exception:
        pass
    if not ok:
        return JSONResponse({"error": "FreeCAD export failed. Install: apt-get install freecad"}, status_code=500)
    return FileResponse(fcstd_path, filename=f"{job_id}_model.FCStd", media_type="application/octet-stream")


# ========= ML ENDPOINTS (Phases 1-3) =========

@router.post("/ml/feedback")
async def ml_feedback(session_id: str = Form(...), predicted_type: str = Form(None),
                      corrected_type: str = Form(None), confidence: float = Form(0),
                      verified: bool = Form(False)):
    """Phase 1: Store user corrections for ML retraining."""
    from app.services.ml_engine import store_feedback
    predicted = {"type": predicted_type, "confidence": confidence}
    corrected = {"type": corrected_type or predicted_type}
    ok = store_feedback(session_id, predicted, corrected, verified)
    return JSONResponse({"stored": ok, "total_feedback": count_feedback()})


@router.get("/ml/status")
async def ml_status():
    """Get ML system status."""
    from app.services.ml_engine import get_ml_status, get_feedback_count, should_retrain
    return JSONResponse({
        "feedback_samples": get_feedback_count(),
        "should_retrain": should_retrain(),
        "status": get_ml_status()
    })


@router.post("/ml/predict")
async def ml_predict(file: UploadFile = File(...)):
    """Phase 2: ML prediction with ONNX model (falls back to rule-based)."""
    from app.services.ml_engine import furniture_classifier, dimension_predictor
    from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles
    from app.backend.ocr import ocr_dimensions

    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
    img_path = UPLOAD / f"{job_id}{ext}"
    with img_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Extract features
    ocr_lines, ocr_dims = ocr_dimensions(str(img_path))
    img, gray = load_image(str(img_path))
    binary = preprocess(gray)
    geometry = {
        "lines": detect_lines(binary),
        "circles": detect_circles(gray),
        "rects": detect_rectangles(binary)
    }

    # Predict
    furn_pred = furniture_classifier.predict(str(img_path), "\n".join(ocr_lines), geometry)
    dim_pred = dimension_predictor.predict(geometry, ocr_dims, furn_pred["type"])

    try:
        os.unlink(str(img_path))
    except Exception:
        pass

    return JSONResponse({
        "job_id": job_id,
        "furniture": furn_pred,
        "dimensions": dim_pred,
        "ml_available": furn_pred.get("ml", False)
    })


@router.post("/ml/retrain")
async def ml_retrain():
    """Phase 3: Trigger retraining (admin)."""
    from app.services.ml_engine import retrain_models
    result = retrain_models()
    return JSONResponse(result)
