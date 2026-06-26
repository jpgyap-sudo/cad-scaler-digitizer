"""API routes for CAD digitizer."""
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, Response, HTMLResponse
from typing import List
from pathlib import Path
import shutil, uuid, os, tempfile

from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles, normalize_lines
from app.backend.ocr import ocr_dimensions
from app.backend.geometry_cleanup import process_constraints
from app.backend.dimension_validator import autocorrect_dimensions, validate_scale
from app.backend.furniture_classifier import classify_furniture, normalize_furniture_type
from app.backend.leader_dimension_classifier import classify_drawing_annotations
from app.backend.furniture_component_segmenter import segment_furniture
from app.backend.dxf_exporter import (
    save_generic, save_round_pedestal_table, save_rectangular_table,
    save_cabinet, save_sofa, save_coffee_table, save_dining_chair,
    save_wardrobe, save_reception_counter, save_bed_headboard
)

router = APIRouter()

OUT = Path(tempfile.gettempdir()) / "cad_digitizer_outputs"
OUT.mkdir(exist_ok=True)
UPLOAD = Path(tempfile.gettempdir()) / "cad_digitizer_uploads"
UPLOAD.mkdir(exist_ok=True)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def _save_drawing_model(f_type, dxf_path, width_cm, height_cm, base_dia_cm=None, neck_dia_cm=None):
    """Save DrawingModel JSON alongside DXF for parametric adjustment."""
    if f_type != 'round_pedestal_table':
        return
    try:
        from app.backend.drawing_model import build_round_pedestal_model
        kwargs = {}
        if base_dia_cm is not None:
            kwargs['base_dia_cm'] = base_dia_cm
        if neck_dia_cm is not None:
            kwargs['neck_dia_cm'] = neck_dia_cm
        model = build_round_pedestal_model(float(width_cm), float(height_cm), **kwargs)
        json_path = Path(str(dxf_path).replace('.dxf', '.json'))
        import json as j
        with open(json_path, 'w') as f:
            j.dump(model.to_dict(), f, indent=2)
    except Exception as e:
        print(f"[DrawingModel] JSON save failed: {e}")


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


def _extract_pedestal_dims(corrected_dims):
    """Pull explicitly-labeled top/base/neck diameters for a round pedestal table.

    The drawing geometry always renders the pedestal body as a trapezoid
    (neck_dia -> base_dia). When a drawing explicitly labels the base/neck
    diameter (e.g. "Dia 44cm base plate"), those values must override the
    hardcoded 0.55/0.28 ratio defaults -- otherwise a straight cylindrical
    base (base_dia == neck_dia) gets drawn as a cone.
    """
    top_dia = base_dia = neck_dia = None
    for d in corrected_dims:
        tag = (d.get('tag') or '').lower().strip()
        val = d.get('value_cm')
        if not val:
            continue
        if tag == 'base_dia' and base_dia is None:
            base_dia = val
        elif tag == 'neck_dia' and neck_dia is None:
            neck_dia = val
        elif tag == 'collar_dia' and neck_dia is None:
            neck_dia = val
        elif tag in ('top_dia', 'dia', 'diameter') and top_dia is None:
            top_dia = val
    # A single explicitly-labeled base/neck diameter (no taper labeled) means
    # the pedestal is a straight cylinder, not a cone -- use it for both ends.
    if base_dia is not None and neck_dia is None:
        neck_dia = base_dia
    elif neck_dia is not None and base_dia is None:
        base_dia = neck_dia
    return top_dia, base_dia, neck_dia


def _dispatch_furniture(f_type, dxf_path, corrected_dims, real_w, real_h, visual_base_estimate=None):
    """Route furniture type to the correct DXF template, applying user-overridden dimensions.

    visual_base_estimate: optional {"profile", "neck_ratio", "base_ratio"} from GPT-4o
    visually inspecting the pedestal's silhouette. Used only when no explicit base/neck
    dimension TEXT was found -- it takes priority over the blind 0.55/0.28 ratio default,
    since most real photos have no printed dimension labels at all.
    """
    print(f"[DISPATCH] Exporter: {f_type}")

    def _dim(tags, default):
        """Pull first matching dimension from corrected_dims using word boundaries."""
        for d in corrected_dims:
            tag = d.get('tag', '').lower().strip()
            for t in tags:
                # Word-boundary match: 'h' matches 'h' or 'height_cm' but NOT 'thickness'
                if tag == t or tag.startswith(t + '_') or tag.startswith(t + ' ') or f'_{t}' in tag:
                    return d['value_cm']
        return default

    extra = {}
    if f_type == 'round_pedestal_table':
        print("EXPORTER USED: save_round_pedestal_table")
        labeled_top, base_dia, neck_dia = _extract_pedestal_dims(corrected_dims)
        dia = real_w or labeled_top or _dim(['dia', 'diameter', 'w', 'width'], 80.0)
        height = real_h or _dim(['h', 'height'], 70.0)

        if (base_dia is None or neck_dia is None) and isinstance(visual_base_estimate, dict):
            try:
                base_ratio = float(visual_base_estimate.get('base_ratio') or 0) or None
                neck_ratio = float(visual_base_estimate.get('neck_ratio') or 0) or None
                if base_dia is None and base_ratio:
                    base_dia = round(dia * base_ratio, 1)
                if neck_dia is None and neck_ratio:
                    neck_dia = round(dia * neck_ratio, 1)
                print(f"[DISPATCH] Visual base estimate applied: profile="
                      f"{visual_base_estimate.get('profile')} base_dia={base_dia} neck_dia={neck_dia}")
            except (TypeError, ValueError):
                pass

        extra = {'base_dia_cm': base_dia, 'neck_dia_cm': neck_dia}
        try:
            save_round_pedestal_table(str(dxf_path), top_dia_cm=dia, height_cm=height,
                                       base_dia_cm=base_dia, neck_dia_cm=neck_dia)
        except Exception as e:
            print(f"[DISPATCH] save_round_pedestal_table FAILED: {e} -- falling back to generic")
            save_generic(str(dxf_path), [], [], [])

        # Surface the dimensions actually used (including ratio-estimated ones)
        # so the frontend's Adjust Dimensions sliders start from real values
        # instead of generic hardcoded defaults.
        try:
            from app.backend.visual_ratio_scaler import estimate_proportions
            ocr_components = {k: v for k, v in
                              {"pedestal_diameter_cm": base_dia, "neck_diameter_cm": neck_dia}.items()
                              if v is not None}
            sr = estimate_proportions("round_pedestal_table",
                                       {"top_diameter_cm": dia, "overall_height_cm": height},
                                       ocr_components or None)
            extra['resolved_dimensions'] = {
                'top_diameter_cm': round(dia, 1),
                'overall_height_cm': round(height, 1),
                'base_diameter_cm': round(sr.get('pedestal_diameter_cm', dia * 0.55), 1),
                'neck_diameter_cm': round(sr.get('neck_diameter_cm', dia * 0.28), 1),
                'top_thickness_cm': round(sr.get('top_thickness_cm', 4.0), 1),
            }
        except Exception as e:
            print(f"[DISPATCH] resolved_dimensions failed: {e}")

    elif f_type == 'rectangular_table':
        print("EXPORTER USED: save_rectangular_table")
        w = real_w or _dim(['w', 'width'], 120.0)
        h = real_h or _dim(['h', 'height'], 70.0)
        d = _dim(['d', 'depth'], 80.0)
        lt = _dim(['leg', 'thickness'], 6.0)
        try:
            save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, leg_thickness_cm=lt)
        except Exception as e:
            print(f"[DISPATCH] save_rectangular_table FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'width_cm': round(w, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h, 1), 'leg_thickness_cm': round(lt, 1),
        }

    elif f_type == 'cabinet':
        print("EXPORTER USED: save_cabinet")
        w = real_w or _dim(['w', 'width'], 100.0)
        h = real_h or _dim(['h', 'height'], 180.0)
        d = _dim(['d', 'depth'], 50.0)
        try:
            save_cabinet(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
        except Exception as e:
            print(f"[DISPATCH] save_cabinet FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])

    elif f_type == 'sofa':
        print("EXPORTER USED: save_sofa")
        w = real_w or _dim(['w', 'width'], 200.0)
        h = real_h or _dim(['h', 'height'], 85.0)
        d = _dim(['d', 'depth'], 80.0)
        try:
            save_sofa(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
        except Exception as e:
            print(f"[DISPATCH] save_sofa FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])

    elif f_type == 'coffee_table':
        print("EXPORTER USED: save_coffee_table")
        w = real_w or _dim(['w', 'width', 'dia', 'diameter'], 100.0)
        h = real_h or _dim(['h', 'height'], 45.0)
        try:
            save_coffee_table(str(dxf_path), width_cm=w, height_cm=h)
        except Exception as e:
            print(f"[DISPATCH] save_coffee_table FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])

    elif f_type in ('dining_chair', 'chair'):
        print("EXPORTER USED: save_dining_chair")
        w = real_w or _dim(['w', 'width', 'seat'], 45.0)
        h = real_h or _dim(['h', 'height'], 90.0)
        try:
            save_dining_chair(str(dxf_path), width_cm=w, height_cm=h)
        except Exception as e:
            print(f"[DISPATCH] save_dining_chair FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])

    elif f_type == 'wardrobe':
        print("EXPORTER USED: save_wardrobe")
        w = real_w or _dim(['w', 'width'], 120.0)
        h = real_h or _dim(['h', 'height'], 200.0)
        try:
            save_wardrobe(str(dxf_path), width_cm=w, height_cm=h)
        except Exception as e:
            print(f"[DISPATCH] save_wardrobe FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])

    elif f_type == 'reception_counter':
        print("EXPORTER USED: save_reception_counter")
        w = real_w or _dim(['w', 'width'], 180.0)
        h = real_h or _dim(['h', 'height'], 110.0)
        try:
            save_reception_counter(str(dxf_path), width_cm=w, height_cm=h)
        except Exception as e:
            print(f"[DISPATCH] save_reception_counter FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])

    elif f_type == 'bed_headboard':
        print("EXPORTER USED: save_bed_headboard")
        w = real_w or _dim(['w', 'width'], 160.0)
        h = real_h or _dim(['h', 'height'], 120.0)
        try:
            save_bed_headboard(str(dxf_path), width_cm=w, height_cm=h)
        except Exception as e:
            print(f"[DISPATCH] save_bed_headboard FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])

    else:
        print(f"EXPORTER USED: save_generic (unknown type: {f_type})")
        save_generic(str(dxf_path), [], [], [])

    # Generate DrawingModel JSON alongside DXF for parametric adjustment + validation
    _save_drawing_model(f_type, dxf_path, real_w or 80.0, real_h or 70.0,
                         base_dia_cm=extra.get('base_dia_cm'), neck_dia_cm=extra.get('neck_dia_cm'))
    return extra


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

        # Parse user-provided dimensions early (used by Echo Drafter + dispatch)
        real_w = _parse_float(real_width_cm)
        real_h = _parse_float(real_height_cm)

        # Echo Drafter: record user correction if furniture_type was explicitly overridden
        if furniture_type and furniture_type.strip():
            from app.backend.feedback_learner import record_correction
            record_correction(
                job_id, "furniture_type",
                classifier_result.get('type', ''), f_type,
                context={"confidence": confidence, "endpoint": "digitize"},
            )
            if real_w:
                record_correction(job_id, "top_diameter_cm", None, real_w)
            if real_h:
                record_correction(job_id, "overall_height_cm", None, real_h)

        print(f"[DIGITIZE] RAW furniture_type form param: '{furniture_type}'")
        print(f"[DIGITIZE] Classifier type: '{classifier_result['type']}'")
        print(f"[DIGITIZE] NORMALIZED: '{f_type}'")
        print(f"[DIGITIZE] EXPORTER USED: {'save_round_pedestal_table' if f_type == 'round_pedestal_table' else 'OTHER'}")

        dxf_name = f'{job_id}_digitized.dxf'
        dxf_path = OUT / dxf_name
        scale, _, warns = validate_scale(corrected_dims, constrained['lines'])

        dispatch_extra = _dispatch_furniture(f_type, dxf_path, corrected_dims, real_w, real_h)

        # Generate SVG preview alongside DXF
        try:
            from app.backend.drawing_model import build_round_pedestal_model
            from app.backend.svg_exporter import drawing_to_svg
            svg_name = f'{job_id}_digitized.svg'
            svg_path = OUT / svg_name
            svg_kwargs = {k: v for k, v in (dispatch_extra or {}).items()
                          if k in ('base_dia_cm', 'neck_dia_cm') and v is not None}
            model = build_round_pedestal_model(float(real_w or 80), float(real_h or 70), **svg_kwargs)
            with open(str(svg_path), 'w') as f2:
                f2.write(drawing_to_svg(model))
        except Exception:
            svg_name = None

        # Central Brain: record drawing + proportions
        try:
            from app.backend.brain_sync import record_drawing, record_proportion
            record_drawing(job_id, f_type, dxf_name,
                           entity_counts={}, dimensions_used={"w": real_w, "h": real_h},
                           preview_urls={"svg": f"/api/preview/svg/{dxf_name}"})
            if real_w and real_w > 0:
                record_proportion(f_type, "top_diameter_cm", float(real_w or 80),
                                  "pedestal_diameter_cm", float(real_w or 80) * 0.55)
        except Exception:
            pass

        try:
            os.remove(str(img_path))
        except Exception:
            pass

        return JSONResponse({
            'job_id': job_id,
            'dxf_file': dxf_name,
            'download': f'/api/download/{dxf_name}',
            'preview_svg': f'/api/preview/svg/{dxf_name}' if svg_name else None,
            'resolved_dimensions': (dispatch_extra or {}).get('resolved_dimensions'),
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
                        {"role": "system", "content": "Analyze furniture drawing. Identify the SPECIFIC furniture type from this list: round_pedestal_table, rectangular_table, cabinet, sofa, coffee_table, dining_chair, wardrobe, reception_counter, bed_headboard. For each dimension label, use nearby text to tag it precisely: 'top_dia' (tabletop diameter), 'base_dia' (base plate / pedestal foot / glide diameter), 'neck_dia' (narrowest point of pedestal), 'collar_dia' (metal collar plate just under the top), 'height', 'width', 'depth', 'thickness'. If a pedestal/leg base is the SAME width top-to-bottom (a straight cylinder/column, not visibly tapering), set base_dia and neck_dia to the SAME value -- do not assume it narrows toward the top. If the furniture is a round_pedestal_table, ALSO visually inspect the pedestal's actual silhouette in the photo (regardless of whether any text labels are visible) and return a 'visual_base_estimate' object: {\"profile\":\"cylinder|tapered|flared|unknown\", \"neck_ratio\": neck-diameter-divided-by-top-diameter as seen in the photo (0-1, use ~1.0 if it looks like a straight cylinder), \"base_ratio\": foot-diameter-divided-by-top-diameter as seen in the photo (0-1)}. This visual estimate is used whenever no explicit base/neck dimension text exists, so look carefully at the actual shape rather than guessing a generic taper. Return JSON with furniture_type (one of those exact strings), confidence (0-1 float), dimensions array [{tag, value_cm}], visual_base_estimate."},
                        {"role": "user", "content": [{"type": "text", "text": "Identify furniture and extract all dimensions."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}}]}
                    ], "max_tokens": 2000, "response_format": {"type": "json_object"}})
                if r.status_code == 200:
                    raw_content = r.json()['choices'][0]['message']['content']
                    try:
                        ai_result = json.loads(raw_content)
                    except (json.JSONDecodeError, ValueError):
                        # Strip markdown code fences (GPT-4o sometimes wraps JSON)
                        cleaned = raw_content.strip()
                        if cleaned.startswith('```'):
                            cleaned = cleaned.split('\n', 1)[-1] if '\n' in cleaned else cleaned[3:]
                        if cleaned.rstrip().endswith('```'):
                            cleaned = cleaned.rstrip()[:-3]
                        ai_result = json.loads(cleaned.strip())
        except Exception as e:
            print(f"[Hybrid] OpenAI error: {e}")

        # Also run OpenCV pipeline for geometry + classification
        img, gray = load_image(str(img_path))
        binary = preprocess(gray)
        lines_raw = detect_lines(binary)
        lines = normalize_lines(lines_raw)
        circles = detect_circles(gray)
        rects = detect_rectangles(binary)
        ocr_lines, dims = ocr_dimensions(str(img_path))
        constrained = process_constraints(lines, circles, dims, rects)
        corrected_dims = autocorrect_dimensions(dims, {})

        # Run OpenCV classifier as fallback for AI
        opencv_classifier = classify_furniture(ocr_lines, constrained['circles'], constrained['lines'], constrained.get('rects'))
        opencv_type = opencv_classifier.get('type', 'generic_2d_furniture')
        opencv_conf = opencv_classifier.get('confidence', 0.3)

        try:
            os.remove(str(img_path))
        except Exception:
            pass

        # Priority: user override > AI result > OpenCV classifier > generic fallback
        raw_ai_type = (ai_result.get('furniture_type', '') or '').strip()
        KNOWN_TYPES = {'round_pedestal_table', 'rectangular_table', 'cabinet', 'sofa',
                       'coffee_table', 'dining_chair', 'chair', 'wardrobe',
                       'reception_counter', 'bed_headboard'}
        if furniture_type:
            ftype = normalize_furniture_type(furniture_type)
            print(f"[HYBRID] Using user override: {furniture_type} → {ftype}")
        elif raw_ai_type:
            ftype = normalize_furniture_type(raw_ai_type)
            print(f"[HYBRID] Using AI: '{raw_ai_type}' → '{ftype}'")
            # If AI returned a vague type not matching any template, try OpenCV
            if ftype not in KNOWN_TYPES:
                opencv_ftype = normalize_furniture_type(opencv_type)
                if opencv_ftype in KNOWN_TYPES:
                    print(f"[HYBRID] AI '{raw_ai_type}' too vague, using OpenCV: '{opencv_type}' → '{opencv_ftype}'")
                    ftype = opencv_ftype
        else:
            ftype = normalize_furniture_type(opencv_type)
            print(f"[HYBRID] AI empty, using OpenCV classifier: '{opencv_type}' → '{ftype}'")

        try:
            conf = float(ai_result.get('confidence', 0) or 0)
        except Exception:
            conf = 0.5
        # Use max confidence from both engines
        conf = max(conf, opencv_conf)

        # Merge AI dimensions with OCR dims (must happen BEFORE annotation/segmentation)
        ai_dims = ai_result.get('dimensions', []) or []
        merged_dims = corrected_dims + [
            {'tag': d.get('tag', ''), 'value_cm': float(d.get('value_cm', 0)), 'raw': str(d)}
            for d in ai_dims if isinstance(d, dict)
        ]

        # --- Annotation classification: separate dimensions from leaders ---
        annotation_result = classify_drawing_annotations(ocr_lines, merged_dims)
        print(f"[HYBRID] Annotations: {len(annotation_result.dimensions)} dims, "
              f"{len(annotation_result.leaders)} leaders, "
              f"{len(annotation_result.centerlines)} centerlines, "
              f"{len(annotation_result.notes)} notes")

        # --- Component segmentation: identify visible vs estimated sub-components ---
        known_dims = {}
        for d in merged_dims:
            tag = d.get('tag', '').lower()
            val = float(d.get('value_cm', 0))
            if val > 0:
                if tag in ('top_dia', 'dia', 'diameter'):
                    known_dims['top_diameter_cm'] = val
                elif any(k in tag for k in ['h', 'height']):
                    known_dims['overall_height_cm'] = val
                elif any(k in tag for k in ['w', 'width']):
                    known_dims['top_width_cm'] = val
        segmentation = segment_furniture(ftype, ocr_lines, ai_result, known_dims)
        print(f"[HYBRID] Components: {len(segmentation.present_components())} present, "
              f"{len(segmentation.estimated_components())} estimated")

        dxf_name = f'{job_id}_hybrid.dxf'
        dxf_path = OUT / dxf_name

        real_w = _parse_float(real_width_cm)
        real_h = _parse_float(real_height_cm)
        print("RAW furniture_type:", furniture_type)
        print("AI furniture_type:", ai_result.get("furniture_type"))
        print("NORMALIZED:", ftype)
        print("EXPORTER USED:", "save_round_pedestal_table" if ftype == "round_pedestal_table" else "OTHER")
        print(f"[HYBRID] Dispatch: ftype='{ftype}' w={real_w} h={real_h}")
        visual_base_estimate = ai_result.get('visual_base_estimate') if isinstance(ai_result, dict) else None
        dispatch_extra = _dispatch_furniture(ftype, dxf_path, merged_dims, real_w, real_h, visual_base_estimate)

        # Generate SVG preview alongside DXF
        try:
            from app.backend.drawing_model import build_round_pedestal_model
            from app.backend.svg_exporter import drawing_to_svg
            svg_name = f'{job_id}_hybrid.svg'
            svg_path = OUT / svg_name
            svg_kwargs = {k: v for k, v in (dispatch_extra or {}).items()
                          if k in ('base_dia_cm', 'neck_dia_cm') and v is not None}
            model = build_round_pedestal_model(float(real_w or 80), float(real_h or 70), **svg_kwargs)
            with open(str(svg_path), 'w') as f2:
                f2.write(drawing_to_svg(model))
        except Exception:
            svg_name = None

        return JSONResponse({
            'job_id': job_id,
            'dxf_file': dxf_name,
            'download': f'/api/download/{dxf_name}',
            'preview_svg': f'/api/preview/svg/{dxf_name}' if svg_name else None,
            'resolved_dimensions': (dispatch_extra or {}).get('resolved_dimensions'),
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


@router.get("/preview/svg/{filename}")
def preview_svg(filename: str):
    """Serve pre-generated SVG preview (generated alongside DXF)."""
    safe = os.path.basename(filename)
    svg_path = OUT / safe.replace('.dxf', '.svg')

    if svg_path.exists():
        return FileResponse(svg_path, media_type="image/svg+xml")

    # Try generate from DXF
    dxf_path = OUT / safe
    if dxf_path.exists():
        import ezdxf, re
        try:
            doc = ezdxf.readfile(str(dxf_path))
            from app.backend.drawing_model import build_round_pedestal_model
            from app.backend.svg_exporter import drawing_to_svg
            top_dia, height = 80.0, 70.0
            for e in doc.modelspace():
                if e.dxftype() == "DIMENSION":
                    txt = (e.dxf.text if hasattr(e.dxf, "text") else "") or ""
                    nums = re.findall(r'(\d+(?:\.\d+)?)', txt)
                    val = float(nums[0]) if nums else None
                    if val and ("%%c" in txt or "dia" in txt.lower()):
                        top_dia = val
                    if val and ("H" in txt or "height" in txt.lower()):
                        height = val
            model = build_round_pedestal_model(top_dia, height)
            svg = drawing_to_svg(model)
            with open(str(svg_path), 'w') as f:
                f.write(svg)
            return FileResponse(svg_path, media_type="image/svg+xml")
        except Exception as e:
            return JSONResponse({"error": f"SVG failed: {e}"}, status_code=500)

    return JSONResponse({"error": "DXF not found — re-upload image to generate a new drawing"}, status_code=404)


# ========= PARAMETRIC ADJUSTMENT =========

@router.post("/adjust")
async def adjust_dimensions(
    dxf_file: str = Form(...),
    top_diameter_cm: float = Form(None),
    overall_height_cm: float = Form(None),
    base_diameter_cm: float = Form(None),
    neck_diameter_cm: float = Form(None),
    top_thickness_cm: float = Form(None),
    width_cm: float = Form(None),
    depth_cm: float = Form(None),
    leg_thickness_cm: float = Form(None),
):
    """
    Adjust dimensions of an existing DXF and regenerate SVG+DXF preview.
    Supports round_pedestal_table and rectangular_table.
    """
    safe = os.path.basename(dxf_file)
    dxf_path = OUT / safe
    if not dxf_path.exists():
        return JSONResponse({"error": "DXF not found"}, status_code=404)

    try:
        import ezdxf, re
        doc = ezdxf.readfile(str(dxf_path))
        from app.backend.svg_exporter import drawing_to_svg

        # Detect furniture type from DXF content
        ftype = "round_pedestal_table"  # default
        has_circle = any(e.dxftype() == "CIRCLE" for e in doc.modelspace())
        dim_texts = []
        for e in doc.modelspace():
            if e.dxftype() == "DIMENSION":
                txt = (e.dxf.text if hasattr(e.dxf, "text") else "") or ""
                dim_texts.append(txt)
        all_txt = " ".join(dim_texts).lower()
        if not has_circle and any(k in all_txt for k in ["w =", "width"]):
            ftype = "rectangular_table"

        if ftype == "rectangular_table":
            # Rectangular table adjustment
            w, h, d, lt = 120.0, 70.0, 80.0, 6.0
            for txt in dim_texts:
                nums = re.findall(r'(\d+(?:\.\d+)?)', txt)
                val = float(nums[0]) if nums else None
                if val:
                    if "w =" in txt.lower() or "width" in txt.lower():
                        w = val
                    elif "h =" in txt.lower() or "height" in txt.lower():
                        h = val
                    elif "d =" in txt.lower() or "depth" in txt.lower():
                        d = val
            if width_cm is not None: w = width_cm
            if overall_height_cm is not None: h = overall_height_cm
            if depth_cm is not None: d = depth_cm
            if leg_thickness_cm is not None: lt = leg_thickness_cm

            from app.backend.dxf_exporter import save_rectangular_table
            try:
                save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, leg_thickness_cm=lt)
            except Exception as e:
                print(f"[Adjust] Rect DXF regen failed: {e}")

            from app.backend.drawing_model import build_rectangular_table_model
            model = build_rectangular_table_model(w, d, h, lt)
            svg = drawing_to_svg(model)
            svg_path = OUT / safe.replace('.dxf', '.svg')
            with open(str(svg_path), 'w') as f:
                f.write(svg)

            return JSONResponse({
                "furniture_type": "rectangular_table",
                "dxf_file": safe,
                "preview_svg": f"/api/preview/svg/{safe}",
                "dimensions": {"width_cm": w, "depth_cm": d, "overall_height_cm": h, "leg_thickness_cm": lt},
            })

        # Round pedestal table (original flow)
        top_dia, height = 80.0, 70.0
        base_dia, neck_dia, top_thick = 44.0, 22.4, 4.0
        for txt in dim_texts:
            nums = re.findall(r'(\d+(?:\.\d+)?)', txt)
            val = float(nums[0]) if nums else None
            if val:
                if "%%c" in txt or "dia" in txt.lower():
                    if val > 50:
                        top_dia = val
                    else:
                        base_dia = val
                if "h =" in txt.lower() or "height" in txt.lower():
                    height = val

        # Apply adjustments
        if top_diameter_cm is not None:
            top_dia = top_diameter_cm
        if overall_height_cm is not None:
            height = overall_height_cm
        if base_diameter_cm is not None:
            base_dia = base_diameter_cm
        if neck_diameter_cm is not None:
            neck_dia = neck_diameter_cm
        if top_thickness_cm is not None:
            top_thick = top_thickness_cm

        # Regenerate DXF + SVG with new dimensions
        from app.backend.dxf_exporter import save_round_pedestal_table
        try:
            save_round_pedestal_table(
                str(dxf_path), top_dia_cm=top_dia, height_cm=height,
                base_dia_cm=base_dia, neck_dia_cm=neck_dia,
                top_thick_cm=top_thick,
            )
        except Exception as e:
            print(f"[Adjust] DXF regen failed: {e}")

        model = build_round_pedestal_model(
            top_dia_cm=top_dia, height_cm=height,
            base_dia_cm=base_dia, neck_dia_cm=neck_dia,
            top_thick_cm=top_thick,
        )
        svg = drawing_to_svg(model)
        svg_path = OUT / safe.replace('.dxf', '.svg')
        with open(str(svg_path), 'w') as f:
            f.write(svg)

        return JSONResponse({
            "dxf_file": safe,
            "preview_svg": f"/api/preview/svg/{safe}",
            "dimensions": {
                "top_diameter_cm": round(top_dia, 1),
                "overall_height_cm": round(height, 1),
                "base_diameter_cm": round(base_dia, 1),
                "neck_diameter_cm": round(neck_dia, 1),
                "top_thickness_cm": round(top_thick, 1),
            },
        })
    except Exception as e:
        return JSONResponse({"error": f"Adjust failed: {e}"}, status_code=500)


@router.get("/preview/{filename}")
def preview_dxf(filename: str):
    """Render DXF as PNG preview image."""
    safe = os.path.basename(filename)
    path = OUT / safe
    if not path.exists():
        return JSONResponse({"error": "DXF not found"}, status_code=404)

    png_name = safe.replace('.dxf', '.png')
    png_path = OUT / png_name

    if not png_path.exists():
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import ezdxf

            doc = ezdxf.readfile(str(path))
            fig = plt.figure(figsize=(11.7, 8.3), dpi=100)
            ax = fig.add_axes([0, 0, 1, 1])
            ctx = RenderContext(doc)
            backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
            ax.set_xlim(-10, 440)
            ax.set_ylim(-10, 310)
            ax.axis('off')
            fig.savefig(str(png_path), dpi=100, facecolor='white', bbox_inches='tight', pad_inches=0.1)
            plt.close(fig)
        except Exception as e:
            return JSONResponse({"error": f"Preview failed: {e}"}, status_code=500)

    return FileResponse(png_path, media_type="image/png")


@router.get("/preview/pdf/{filename}")
def preview_pdf(filename: str):
    """
    Generate and return a print-ready PDF shop drawing.
    Uses matplotlib + ezdxf to render the DXF as a styled PDF.
    """
    safe = os.path.basename(filename)
    dxf_path = OUT / safe
    if not dxf_path.exists():
        return JSONResponse({"error": "DXF not found"}, status_code=404)

    pdf_name = safe.replace('.dxf', '.pdf')
    pdf_path = OUT / pdf_name

    if not pdf_path.exists():
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import ezdxf

            doc = ezdxf.readfile(str(dxf_path))
            fig = plt.figure(figsize=(16.54, 11.69), dpi=150)  # A3
            ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
            ctx = RenderContext(doc)
            backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
            ax.set_xlim(-10, 440)
            ax.set_ylim(-10, 310)
            ax.set_aspect('equal')
            ax.axis('off')
            fig.savefig(str(pdf_path), dpi=150, facecolor='white')
            plt.close(fig)
        except Exception as e:
            # Fallback to simple PDF
            from app.services.pdf_exporter import export_pdf_shop_drawing
            export_pdf_shop_drawing(dxf_path, pdf_path,
                furniture_type=safe.replace('_digitized.dxf','').replace('_hybrid.dxf','')
                              .replace('_',' ').title())

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


# ========= CENTRAL BRAIN (Postgres Intelligence) =========

@router.get("/brain/report")
async def brain_report():
    """Get Central Brain intelligence report."""
    from app.backend.brain_sync import get_intelligence_report
    return JSONResponse(get_intelligence_report())


@router.get("/brain/proportions")
async def brain_proportions(
    furniture_type: str = "round_pedestal_table",
    anchor_dimension: str = "top_diameter_cm",
    anchor_value: float = 80.0,
    component: str = "pedestal_diameter_cm",
):
    """Get proportion estimate from the brain."""
    from app.backend.brain_sync import get_proportion_estimate
    est = get_proportion_estimate(furniture_type, anchor_dimension, anchor_value, component)
    return JSONResponse({"estimate": est} if est else {"estimate": None, "note": "Not enough data yet"})


@router.get("/brain/materials")
async def brain_materials(component: str = "tabletop", furniture_type: str = None):
    """Get material suggestions from the brain."""
    from app.backend.brain_sync import get_material_suggestions
    suggestions = get_material_suggestions(component, furniture_type)
    return JSONResponse({"component": component, "suggestions": suggestions})


# ========= BATCH CONVERT =========

@router.post("/batch")
async def batch_convert(files: List[UploadFile] = File(...)):
    """Upload multiple images, generate DXF+SVG for each, return ZIP."""
    import zipfile, io, uuid
    buf = io.BytesIO()
    results = []
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            try:
                job_id = str(uuid.uuid4())
                img_path = UPLOAD / f"{job_id}_{file.filename}"
                with img_path.open("wb") as f:
                    f.write(await file.read())
                # Quick digitize (OpenCV only for batch — fast)
                img, gray = load_image(str(img_path))
                binary = preprocess(gray)
                lines = normalize_lines(detect_lines(binary))
                circles = detect_circles(gray)
                rects = detect_rectangles(binary)
                ocr_lines, ocr_dims = ocr_dimensions(str(img_path))
                constrained = process_constraints(lines, circles, ocr_dims, rects)
                classifier = classify_furniture(ocr_lines, constrained["circles"], constrained["lines"], constrained.get("rects"))
                ftype = normalize_furniture_type(classifier["type"])
                corrected_dims = autocorrect_dimensions(ocr_dims, {})

                dxf_name = f"{job_id}_batch.dxf"
                dxf_path = OUT / dxf_name
                _dispatch_furniture(ftype, dxf_path, corrected_dims, 0.0, 0.0)
                # Add DXF to ZIP
                if dxf_path.exists():
                    zf.write(str(dxf_path), dxf_name)
                # Cleanup
                try: os.unlink(str(img_path))
                except: pass
                results.append({"file": file.filename, "furniture_type": ftype, "dxf": dxf_name, "status": "ok"})
            except Exception as e:
                results.append({"file": file.filename, "status": "error", "error": str(e)[:100]})

    buf.seek(0)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename=batch_convert_{len(files)}_files.zip"})


# ========= SHARE LINK =========

@router.get("/view/{filename}")
def view_drawing(filename: str):
    """View a drawing as SVG — shareable URL."""
    safe = os.path.basename(filename)
    svg_path = OUT / safe.replace('.dxf', '.svg').replace('.json', '.svg')

    if not svg_path.exists():
        # Try generate from DXF
        dxf_path = OUT / safe.replace('.svg', '.dxf')
        if dxf_path.exists():
            from app.backend.drawing_model import build_round_pedestal_model
            from app.backend.svg_exporter import drawing_to_svg
            import ezdxf, re
            doc = ezdxf.readfile(str(dxf_path))
            top_dia, height = 80.0, 70.0
            for e in doc.modelspace():
                if e.dxftype() == "DIMENSION":
                    txt = (e.dxf.text if hasattr(e.dxf, "text") else "") or ""
                    nums = re.findall(r'(\d+(?:\.\d+)?)', txt)
                    val = float(nums[0]) if nums else None
                    if val and ("%%c" in txt or "dia" in txt.lower()): top_dia = val
                    if val and ("H" in txt or "height" in txt.lower()): height = val
            model = build_round_pedestal_model(top_dia, height)
            svg = drawing_to_svg(model)
            with open(str(svg_path), 'w') as f:
                f.write(svg)

    if not svg_path.exists():
        return JSONResponse({"error": "Drawing not found"}, status_code=404)

    svg = svg_path.read_text()
    # Embed SVG directly as HTML for instant viewing
    return HTMLResponse(f"""<!DOCTYPE html><html><head><title>CAD Drawing — {safe}</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>body{{margin:0;display:flex;justify-content:center;background:#f0f0f0}}</style></head>
<body>{svg}</body></html>""")


# ========= STYLE PRESETS (Scan2CAD-inspired) =========

@router.get("/presets")
async def list_presets_endpoint():
    """List all saved style presets."""
    from app.backend.style_presets import list_presets as lp
    presets = lp()
    return JSONResponse({"presets": [p.to_dict() for p in presets], "count": len(presets)})


@router.post("/presets/save")
async def save_preset_endpoint(
    name: str = Form(...),
    session_id: str = Form(None),
    furniture_type: str = Form(None),
):
    """Save current chat state as a named style preset."""
    from app.backend.style_presets import StylePreset, preset_from_chat_state, save_preset as sp
    state = CHAT_SESSIONS.get(session_id or "default", {})
    preset = preset_from_chat_state(state, name)
    if furniture_type:
        preset.furniture_type = furniture_type
    filename = sp(preset)
    return JSONResponse({"saved": filename, "preset": preset.to_dict()})


@router.post("/presets/apply")
async def apply_preset_endpoint(name: str = Form(...)):
    """Apply a style preset to pre-fill materials and dimensions."""
    from app.backend.style_presets import load_preset, apply_preset_to_template
    preset = load_preset(name)
    if not preset:
        return JSONResponse({"error": "Preset not found"}, status_code=404)
    params = apply_preset_to_template(preset)
    return JSONResponse({"preset": preset.to_dict(), "params": params})


@router.delete("/presets/{name}")
async def delete_preset_endpoint(name: str):
    """Delete a style preset."""
    from app.backend.style_presets import delete_preset as dp
    ok = dp(name)
    return JSONResponse({"deleted": ok})


# ========= CHAT ENDPOINT =========

CHAT_SESSIONS: dict = {}  # session_id -> DrawingState dict


@router.post("/chat")
async def chat_message(
    message: str = Form(...),
    session_id: str = Form(None),
    image_id: str = Form(None),
):
    """
    Conversational chatbox for refining furniture drawings.

    Accepts natural language messages about materials, dimensions,
    component visibility, and furniture type corrections.
    Returns structured state updates that feed into the DXF pipeline.
    """
    from app.backend.chat_agent import chat_with_agent
    from app.backend.feedback_learner import learn_from_chat, get_adjustment_hints, load_preferences, apply_preferences

    sid = session_id or "default"
    prev_state = CHAT_SESSIONS.get(sid)

    result = chat_with_agent(message, prev_state)
    CHAT_SESSIONS[sid] = result["state"]

    # Echo Drafter: learn from user corrections in this message
    corrections = learn_from_chat(sid, prev_state or {}, result["state"], user_id=session_id or "default")

    # Central Brain: record corrections + materials to Postgres
    try:
        from app.backend.brain_sync import record_correction as brc, record_material as brm
        for c in corrections:
            brc(sid, result["state"].get("furniture_type", ""),
                c.field, c.old_value, c.new_value,
                correction_type="dimension" if c.field.endswith("_cm") else "material")
        # Record material choices
        for comp, mat in result["state"].get("materials", {}).items():
            brm(comp, str(mat))
    except Exception as e:
        print(f"[BrainSync] Record failed: {e}")

    # If model has enough confidence, include adjustment hints
    hints = get_adjustment_hints(user_id=session_id or "default") if len(corrections) > 0 else []

    return JSONResponse({
        "session_id": sid,
        "response": result["response"],
        "action": result["action"],
        "render_hint": result["render_hint"],
        "state": result["state"],
        "image_id": image_id,
        "corrections_learned": len(corrections),
        "adjustment_hints": hints[:5] if hints else [],
    })


@router.get("/chat/state")
async def chat_state(session_id: str = "default"):
    """Get current drawing state for a chat session."""
    state = CHAT_SESSIONS.get(session_id, {})
    return JSONResponse({
        "session_id": session_id,
        "state": state,
    })


@router.get("/chat/sessions")
async def chat_sessions():
    """List active chat sessions."""
    return JSONResponse({
        "sessions": list(CHAT_SESSIONS.keys()),
        "count": len(CHAT_SESSIONS),
    })


# ========= ECHO DRAFTER — Learning Endpoints =========

@router.get("/learn/preferences")
async def get_preferences(user_id: str = "default"):
    """Get learned user preferences from Echo Drafter."""
    from app.backend.feedback_learner import load_preferences, get_adjustment_hints
    model = load_preferences(user_id)
    return JSONResponse({
        "user_id": user_id,
        "preferences": model.to_dict(),
        "hints": get_adjustment_hints(user_id),
        "model_active": model.correction_count >= 3,
    })


@router.get("/learn/users")
async def list_learned_users():
    """List all users with stored preference models."""
    from app.backend.feedback_learner import get_all_users, load_preferences
    users = get_all_users()
    result = {}
    for uid in users:
        model = load_preferences(uid)
        result[uid] = {
            "corrections": model.correction_count,
            "confidence": round(model.confidence, 2),
            "last_updated": model.last_updated,
        }
    return JSONResponse({"users": result, "total": len(users)})


@router.post("/learn/apply")
async def apply_learned_preferences(
    user_id: str = Form("default"),
    session_id: str = Form(None),
):
    """
    Apply learned preferences to pre-adjust current drawing session.
    Returns adjusted parameters that anticipate user corrections.
    """
    from app.backend.feedback_learner import apply_preferences, load_preferences, get_adjustment_hints
    state = CHAT_SESSIONS.get(session_id or "default", {})
    adjusted = apply_preferences(state, user_id)
    hints = get_adjustment_hints(user_id)
    return JSONResponse({
        "user_id": user_id,
        "adjusted_params": adjusted,
        "hints": hints,
    })
