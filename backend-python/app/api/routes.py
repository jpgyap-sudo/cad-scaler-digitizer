"""API routes for CAD digitizer with accuracy core pipeline."""

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, Response, HTMLResponse
from typing import List
from pathlib import Path
import shutil, uuid, os, tempfile, json, traceback

from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles, normalize_lines
from app.backend.ocr import ocr_dimensions
from app.backend.ocr_layout_parser import extract_layout
from app.backend.dimension_associator import associate_dimension_text
from app.backend.line_role_classifier import classify_line_roles
from app.backend.scale_solver import compute_scale
from app.backend.geometry_reconstructor import reconstruct_geometry, reconstruct
from app.backend.geometry_cleanup import process_constraints
from app.backend.dimension_validator import autocorrect_dimensions, validate_scale
from app.backend.furniture_classifier import classify_furniture, normalize_furniture_type
from app.backend.leader_dimension_classifier import classify_drawing_annotations
from app.backend.furniture_component_segmenter import segment_furniture
from app.backend.correction_api import submit_corrections, get_corrections, reset_corrections
from app.backend.accuracy_benchmark import run_accuracy_benchmark, load_fixtures
from app.backend.section_predictor import predict_drawing_sections
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

# Below this confidence, the classifier guess is unreliable enough that the
# UI should ask the user to confirm/correct the furniture type rather than
# silently rendering a possibly-wrong template.
CLASSIFIER_CONFIRM_THRESHOLD = 0.55


def _save_drawing_model(f_type, dxf_path, width_cm, height_cm, base_dia_cm=None, neck_dia_cm=None,
                        depth_cm=None, leg_thickness_cm=None, materials=None):
    """Save per-furniture-type DrawingModel JSON alongside the DXF file."""
    try:
        from app.backend.drawing_model import build_round_pedestal_model, build_rectangular_table_model
        json_path = Path(str(dxf_path).replace('.dxf', '.json'))

        if f_type == 'round_pedestal_table':
            kwargs = {}
            if base_dia_cm is not None: kwargs['base_dia_cm'] = base_dia_cm
            if neck_dia_cm is not None: kwargs['neck_dia_cm'] = neck_dia_cm
            model = build_round_pedestal_model(float(width_cm), float(height_cm), **kwargs)
        elif f_type == 'rectangular_table':
            model = build_rectangular_table_model(
                float(width_cm), float(depth_cm or 80),
                float(height_cm), float(leg_thickness_cm or 6))
        else:
            return  # Other types don't have DrawingModel builders yet

        data = model.to_dict()
        if materials:
            data['materials'] = materials
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[DrawingModel] JSON save failed: {e}")


def _parse_float(val, default=None):
    if val is None: return default
    try: return float(val)
    except Exception: return default


def count_feedback() -> int:
    from app.services.ml_engine import get_feedback_count
    return get_feedback_count()


def _extract_pedestal_dims(corrected_dims):
    top_dia = base_dia = neck_dia = None
    for d in corrected_dims:
        tag = (d.get('tag') or '').lower().strip()
        val = d.get('value_cm')
        if not val: continue
        if tag == 'base_dia' and base_dia is None: base_dia = val
        elif tag == 'neck_dia' and neck_dia is None: neck_dia = val
        elif tag == 'collar_dia' and neck_dia is None: neck_dia = val
        elif tag in ('top_dia', 'dia', 'diameter') and top_dia is None: top_dia = val
    if base_dia is not None and neck_dia is None: neck_dia = base_dia
    elif neck_dia is not None and base_dia is None: base_dia = neck_dia
    return top_dia, base_dia, neck_dia


def _component_schema(f_type):
    if f_type == 'round_pedestal_table':
        return [
            {"name": "tabletop", "label": "Tabletop", "dims": [
                {"key": "top_diameter_cm", "label": "Diameter", "min": 40, "max": 160, "step": 1, "unit": "cm"},
                {"key": "top_thickness_cm", "label": "Thickness", "min": 2, "max": 12, "step": 0.5, "unit": "cm"}]},
            {"name": "collar_plate", "label": "Collar Plate", "dims": [
                {"key": "collar_diameter_cm", "label": "Diameter", "min": 20, "max": 100, "step": 1, "unit": "cm"}]},
            {"name": "neck_ring", "label": "Neck", "dims": [
                {"key": "neck_diameter_cm", "label": "Diameter", "min": 10, "max": 60, "step": 0.5, "unit": "cm"}]},
            {"name": "pedestal_body", "label": "Pedestal Column", "dims": [
                {"key": "neck_diameter_cm", "label": "Top Width", "min": 10, "max": 60, "step": 0.5, "unit": "cm"},
                {"key": "base_diameter_cm", "label": "Base Width", "min": 20, "max": 100, "step": 1, "unit": "cm"}]},
            {"name": "base_plate", "label": "Base Plate", "dims": [
                {"key": "base_diameter_cm", "label": "Diameter", "min": 20, "max": 100, "step": 1, "unit": "cm"}]},
            {"name": "overall", "label": "Overall", "dims": [
                {"key": "overall_height_cm", "label": "Height", "min": 30, "max": 150, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'rectangular_table':
        return [
            {"name": "tabletop", "label": "Tabletop", "dims": [
                {"key": "width_cm", "label": "Width", "min": 60, "max": 300, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 40, "max": 150, "step": 1, "unit": "cm"}]},
            {"name": "legs", "label": "Legs", "dims": [
                {"key": "leg_thickness_cm", "label": "Thickness", "min": 3, "max": 15, "step": 0.5, "unit": "cm"}]},
            {"name": "overall", "label": "Overall", "dims": [
                {"key": "overall_height_cm", "label": "Height", "min": 30, "max": 150, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'sofa':
        return [
            {"name": "body", "label": "Body", "dims": [
                {"key": "width_cm", "label": "Width", "min": 80, "max": 350, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 60, "max": 150, "step": 1, "unit": "cm"},
                {"key": "overall_height_cm", "label": "Height", "min": 50, "max": 120, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'cabinet':
        return [
            {"name": "body", "label": "Cabinet Body", "dims": [
                {"key": "width_cm", "label": "Width", "min": 40, "max": 250, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 30, "max": 80, "step": 1, "unit": "cm"},
                {"key": "overall_height_cm", "label": "Height", "min": 60, "max": 250, "step": 1, "unit": "cm"}]},
        ]
    if f_type in ('dining_chair', 'chair'):
        return [
            {"name": "seat", "label": "Seat", "dims": [
                {"key": "width_cm", "label": "Width", "min": 30, "max": 70, "step": 1, "unit": "cm"}]},
            {"name": "overall", "label": "Overall", "dims": [
                {"key": "overall_height_cm", "label": "Height", "min": 50, "max": 130, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'wardrobe':
        return [
            {"name": "body", "label": "Wardrobe Body", "dims": [
                {"key": "width_cm", "label": "Width", "min": 60, "max": 300, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 40, "max": 80, "step": 1, "unit": "cm"},
                {"key": "overall_height_cm", "label": "Height", "min": 120, "max": 260, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'bed_headboard':
        return [
            {"name": "headboard", "label": "Headboard", "dims": [
                {"key": "width_cm", "label": "Width", "min": 80, "max": 250, "step": 1, "unit": "cm"},
                {"key": "overall_height_cm", "label": "Height", "min": 60, "max": 180, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'coffee_table':
        return [
            {"name": "tabletop", "label": "Tabletop", "dims": [
                {"key": "width_cm", "label": "Width", "min": 40, "max": 180, "step": 1, "unit": "cm"}]},
            {"name": "overall", "label": "Overall", "dims": [
                {"key": "overall_height_cm", "label": "Height", "min": 20, "max": 60, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'reception_counter':
        return [
            {"name": "counter", "label": "Counter", "dims": [
                {"key": "width_cm", "label": "Width", "min": 80, "max": 400, "step": 1, "unit": "cm"},
                {"key": "overall_height_cm", "label": "Height", "min": 80, "max": 140, "step": 1, "unit": "cm"}]},
        ]
    return None


def _dispatch_furniture(f_type, dxf_path, corrected_dims, real_w, real_h, visual_base_estimate=None,
                         materials=None):
    print(f"[DISPATCH] Exporter: {f_type}")

    def _dim(tags, default):
        for d in corrected_dims:
            tag = d.get('tag', '').lower().strip()
            for t in tags:
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
                if base_dia is None and base_ratio: base_dia = round(dia * base_ratio, 1)
                if neck_dia is None and neck_ratio: neck_dia = round(dia * neck_ratio, 1)
            except (TypeError, ValueError): pass

        extra = {'base_dia_cm': base_dia, 'neck_dia_cm': neck_dia, 'materials': materials or {}}
        try:
            save_round_pedestal_table(str(dxf_path), top_dia_cm=dia, height_cm=height,
                                       base_dia_cm=base_dia, neck_dia_cm=neck_dia, materials=materials)
        except Exception as e:
            print(f"[DISPATCH] save_round_pedestal_table FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])

        try:
            from app.backend.scale_solver import compute_scale
            # Use the newer scale_solver for proportion resolution instead of
            # the deprecated visual_ratio_scaler.estimate_proportions.
            # Fallback to ratio-based defaults when scale solver lacks data.
            sr = {
                'pedestal_diameter_cm': base_dia if base_dia else dia * 0.55,
                'neck_diameter_cm': neck_dia if neck_dia else dia * 0.28,
                'top_thickness_cm': 4.0,
            }
            extra['resolved_dimensions'] = {
                'top_diameter_cm': round(dia, 1), 'overall_height_cm': round(height, 1),
                'base_diameter_cm': round(sr.get('pedestal_diameter_cm', dia * 0.55), 1),
                'neck_diameter_cm': round(sr.get('neck_diameter_cm', dia * 0.28), 1),
                'top_thickness_cm': round(sr.get('top_thickness_cm', 4.0), 1),
                'collar_diameter_cm': round(dia * 0.625, 1),
            }
        except Exception as e: print(f"[DISPATCH] resolved_dimensions failed: {e}")

        from app.backend.dimension_validator import check_round_pedestal_proportions
        extra['proportion_warnings'] = check_round_pedestal_proportions(
            dia, extra.get('resolved_dimensions', {}))

    elif f_type == 'rectangular_table':
        w = real_w or _dim(['w', 'width'], 120.0)
        h = real_h or _dim(['h', 'height'], 70.0)
        d = _dim(['d', 'depth'], 80.0)
        lt = _dim(['leg', 'thickness'], 6.0)
        try: save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, leg_thickness_cm=lt)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'width_cm': round(w, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h, 1), 'leg_thickness_cm': round(lt, 1),
        }
    elif f_type == 'cabinet':
        w = real_w or _dim(['w', 'width'], 100.0)
        h = real_h or _dim(['h', 'height'], 180.0)
        d = _dim(['d', 'depth'], 50.0)
        try: save_cabinet(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'sofa':
        w = real_w or _dim(['w', 'width'], 200.0)
        h = real_h or _dim(['h', 'height'], 85.0)
        d = _dim(['d', 'depth'], 80.0)
        try: save_sofa(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'coffee_table':
        w = real_w or _dim(['w', 'width', 'dia', 'diameter'], 100.0)
        h = real_h or _dim(['h', 'height'], 45.0)
        try: save_coffee_table(str(dxf_path), width_cm=w, height_cm=h)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type in ('dining_chair', 'chair'):
        w = real_w or _dim(['w', 'width', 'seat'], 45.0)
        h = real_h or _dim(['h', 'height'], 90.0)
        try: save_dining_chair(str(dxf_path), width_cm=w, height_cm=h)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'wardrobe':
        w = real_w or _dim(['w', 'width'], 120.0)
        h = real_h or _dim(['h', 'height'], 200.0)
        try: save_wardrobe(str(dxf_path), width_cm=w, height_cm=h)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'reception_counter':
        w = real_w or _dim(['w', 'width'], 180.0)
        h = real_h or _dim(['h', 'height'], 110.0)
        try: save_reception_counter(str(dxf_path), width_cm=w, height_cm=h)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'bed_headboard':
        w = real_w or _dim(['w', 'width'], 160.0)
        h = real_h or _dim(['h', 'height'], 120.0)
        try: save_bed_headboard(str(dxf_path), width_cm=w, height_cm=h)
        except Exception: save_generic(str(dxf_path), [], [], [])
    else:
        print(f"EXPORTER USED: save_generic (unknown type: {f_type})")
        save_generic(str(dxf_path), [], [], [])

    extra['component_schema'] = _component_schema(f_type)
    _save_drawing_model(f_type, dxf_path, real_w or 80.0, real_h or 70.0,
                         base_dia_cm=extra.get('base_dia_cm'), neck_dia_cm=extra.get('neck_dia_cm'),
                         depth_cm=extra.get('resolved_dimensions', {}).get('depth_cm'),
                         leg_thickness_cm=extra.get('resolved_dimensions', {}).get('leg_thickness_cm'),
                         materials=extra.get('materials'))
    try:
        from app.backend.brain_sync import record_drawing, record_proportion
        resolved = extra.get('resolved_dimensions') or {}
        record_drawing(dxf_path.stem, f_type, dxf_path.name, dimensions_used=resolved)
        if f_type == 'round_pedestal_table':
            top_dia = resolved.get('top_diameter_cm')
            if top_dia and extra.get('base_dia_cm') is not None:
                record_proportion('round_pedestal_table', 'top_diameter_cm', top_dia, 'pedestal_diameter_cm', extra['base_dia_cm'])
            if top_dia and extra.get('neck_dia_cm') is not None:
                record_proportion('round_pedestal_table', 'top_diameter_cm', top_dia, 'neck_diameter_cm', extra['neck_dia_cm'])
    except Exception as e: print(f"[DISPATCH] brain_sync recording failed: {e}")

    return extra


def _build_svg_model(f_type, resolved, real_w, real_h, dispatch_extra, detected=None):
    """Build the DrawingModel used for SVG preview, dispatching on furniture type.
    Mirrors _dispatch_furniture's type handling so every type gets its own
    geometry instead of silently falling back to round_pedestal_table.
    `detected` (optional dict of lines/circles/rects) drives the generic
    fallback when the type is unrecognized/unclassified.
    """
    from app.backend.drawing_builders import (
        build_round_pedestal_model, build_rectangular_table_model,
        build_cabinet_model, build_sofa_model, build_coffee_table_model,
        build_dining_chair_model, build_wardrobe_model,
        build_reception_counter_model, build_bed_headboard_model,
        build_generic_model,
    )

    if f_type == 'rectangular_table':
        w = resolved.get('width_cm', real_w or 120)
        d = resolved.get('depth_cm', 80)
        h = resolved.get('overall_height_cm', real_h or 70)
        lt = resolved.get('leg_thickness_cm', 6)
        return build_rectangular_table_model(float(w), float(d), float(h), float(lt))
    if f_type == 'cabinet':
        w = resolved.get('width_cm', real_w or 100)
        d = resolved.get('depth_cm', 50)
        h = resolved.get('overall_height_cm', real_h or 180)
        return build_cabinet_model(float(w), float(d), float(h))
    if f_type == 'sofa':
        w = resolved.get('width_cm', real_w or 200)
        d = resolved.get('depth_cm', 80)
        h = resolved.get('overall_height_cm', real_h or 85)
        return build_sofa_model(float(w), float(d), float(h))
    if f_type == 'coffee_table':
        w = resolved.get('width_cm', real_w or 100)
        d = resolved.get('depth_cm', 60)
        h = resolved.get('overall_height_cm', real_h or 45)
        return build_coffee_table_model(float(w), float(d), float(h))
    if f_type in ('dining_chair', 'chair'):
        w = resolved.get('width_cm', real_w or 45)
        h = resolved.get('overall_height_cm', real_h or 90)
        return build_dining_chair_model(float(w), float(h))
    if f_type == 'wardrobe':
        w = resolved.get('width_cm', real_w or 120)
        d = resolved.get('depth_cm', 60)
        h = resolved.get('overall_height_cm', real_h or 200)
        return build_wardrobe_model(float(w), float(d), float(h))
    if f_type == 'reception_counter':
        w = resolved.get('width_cm', real_w or 180)
        h = resolved.get('overall_height_cm', real_h or 110)
        return build_reception_counter_model(float(w), float(h))
    if f_type == 'bed_headboard':
        w = resolved.get('width_cm', real_w or 180)
        h = resolved.get('overall_height_cm', real_h or 60)
        return build_bed_headboard_model(float(w), float(h))

    if f_type == 'round_pedestal_table':
        svg_kwargs = {k: v for k, v in (dispatch_extra or {}).items()
                      if k in ('base_dia_cm', 'neck_dia_cm') and v is not None}
        svg_top_dia = resolved.get('top_diameter_cm', real_w or 80)
        svg_height = resolved.get('overall_height_cm', real_h or 70)
        # collar_dia_cm must be derived from THIS top diameter, not left to
        # build_round_pedestal_model's hardcoded default of 50.0 - that
        # default only looks right by coincidence when top_dia is ~80cm
        # (50/80 ~= the correct 62.5% ratio); for any other top diameter it
        # silently produces a disproportionate, "pinched" cone shape.
        svg_collar_dia = resolved.get('collar_diameter_cm', float(svg_top_dia) * 0.625)
        return build_round_pedestal_model(float(svg_top_dia), float(svg_height),
                                           collar_dia_cm=float(svg_collar_dia),
                                           materials=(dispatch_extra or {}).get('materials'), **svg_kwargs)

    # Unrecognized/generic type — trace the actually-detected geometry
    # instead of fabricating an unrelated round-pedestal-table shape.
    if detected:
        return build_generic_model(detected.get('lines'), detected.get('circles'), detected.get('rects'))
    return build_generic_model()


# ===== Accuracy Pipeline =====

def _run_accuracy_pipeline(img_path: str, lines, circles, rects, ocr_lines, dims):
    """
    Run the accuracy core pipeline:
    1. OCR Layout Parser — text boxes with positions
    2. Line Role Classifier — separate object/leader/dimension/center lines
    3. Dimension Associator — connect text to geometry
    4. Scale Solver — compute pixel-to-cm scale
    5. Geometry Reconstructor — snap/merge/close contours
    """
    result = {}

    try:
        layout = extract_layout(str(img_path))
        result['layout'] = layout.to_dict()
        text_boxes = layout.text_boxes
        dim_labels = layout.dimension_labels
        print(f"[ACCURACY] Layout: {len(text_boxes)} text boxes, {len(dim_labels)} dimension labels")
    except Exception as e:
        print(f"[ACCURACY] Layout failed: {e}")
        text_boxes = []
        dim_labels = []

    try:
        line_classification = classify_line_roles(lines, text_boxes)
        result['line_roles'] = line_classification.to_dict()
        object_edges = line_classification.object_edges
        dim_lines = line_classification.dimension_lines
        print(f"[ACCURACY] Line roles: {len(object_edges)} object, {len(dim_lines)} dimension")
    except Exception as e:
        print(f"[ACCURACY] Line roles failed: {e}")

    try:
        associations = associate_dimension_text(text_boxes, dim_labels, lines, circles, rects)
        result['associations'] = associations.to_dict()
        print(f"[ACCURACY] Associations: {len(associations.associations)} pairs")
    except Exception as e:
        print(f"[ACCURACY] Association failed: {e}")
        associations = None

    if associations and associations.associations:
        try:
            known_dims = {}
            for d in dims:
                if d.get('value_cm'):
                    known_dims[d.get('tag', f'dim_{len(known_dims)}')] = d['value_cm']
            scale_solution = compute_scale(associations.associations, lines, known_dims)
            result['scale'] = scale_solution.to_dict()
        except Exception as e:
            print(f"[ACCURACY] Scale solver failed: {e}")
            result['scale'] = None
    else:
        result['scale'] = None

    try:
        reconstruction = reconstruct(lines, circles)
        result['reconstruction'] = reconstruction.to_dict()
        print(f"[ACCURACY] Reconstruction: {len(reconstruction.closed_contours)} contours, "
              f"{len(reconstruction.circles)} circles")
    except Exception as e:
        print(f"[ACCURACY] Reconstruction failed: {e}")

    return result


# ===== DIGITIZE ENDPOINTS =====

@router.post("/digitize")
async def digitize(file: UploadFile = File(...), real_width_cm: str = Form(None),
                    real_height_cm: str = Form(None), furniture_type: str = Form(None)):
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
            ys = [p[1] for ln in constrained['lines'] for p in ln]
            if ys: pixel_measurements['height'] = max(ys) - min(ys)

        scale_cm_per_pixel, _scale_conf, scale_warns = validate_scale(dims, constrained['lines'])
        corrected_dims = autocorrect_dimensions(dims, pixel_measurements, scale_cm_per_pixel=scale_cm_per_pixel)
        dim_warns = [d['warning'] for d in corrected_dims if d.get('warning')]
        accuracy_results = _run_accuracy_pipeline(img_path, lines, circles, rects, ocr_lines, dims)

        classifier_result = classify_furniture(ocr_lines, constrained['circles'], constrained['lines'], constrained.get('rects'))
        f_type = normalize_furniture_type(furniture_type or classifier_result['type'])
        confidence = classifier_result.get('confidence', 0.5)

        real_w = _parse_float(real_width_cm)
        real_h = _parse_float(real_height_cm)

        if furniture_type and furniture_type.strip():
            from app.backend.feedback_learner import record_correction
            record_correction(job_id, "furniture_type", classifier_result.get('type', ''), f_type,
                              context={"confidence": confidence, "endpoint": "digitize"})
            if real_w: record_correction(job_id, "top_diameter_cm", None, real_w)
            if real_h: record_correction(job_id, "overall_height_cm", None, real_h)

        dxf_name = f'{job_id}_digitized.dxf'
        dxf_path = OUT / dxf_name
        dispatch_extra = _dispatch_furniture(f_type, dxf_path, corrected_dims, real_w, real_h)
        warns = scale_warns + dim_warns + (dispatch_extra or {}).get('proportion_warnings', [])

        svg_name = None
        try:
            from app.backend.svg_exporter import drawing_to_svg
            svg_name = f'{job_id}_digitized.svg'
            svg_path = OUT / svg_name
            resolved = (dispatch_extra or {}).get('resolved_dimensions') or {}
            detected = {'lines': constrained['lines'], 'circles': constrained['circles'],
                        'rects': constrained.get('rects')}
            model = _build_svg_model(f_type, resolved, real_w, real_h, dispatch_extra, detected)
            with open(str(svg_path), 'w', encoding='utf-8') as f2:
                f2.write(drawing_to_svg(model))
        except Exception: svg_name = None

        try: os.remove(str(img_path))
        except: pass

        return JSONResponse({
            'job_id': job_id, 'dxf_file': dxf_name,
            'download': f'/api/download/{dxf_name}',
            'preview_svg': f'/api/preview/svg/{dxf_name}' if svg_name else None,
            'resolved_dimensions': (dispatch_extra or {}).get('resolved_dimensions'),
            'component_schema': (dispatch_extra or {}).get('component_schema'),
            'furniture': {'type': f_type, 'confidence': confidence,
                          'needs_confirmation': confidence < CLASSIFIER_CONFIRM_THRESHOLD,
                          'required_dimensions': classifier_result.get('required_dimensions', []),
                          'recommended_template': classifier_result.get('recommended_template', '')},
            'detected': {'lines': len(constrained['lines']), 'circles': len(constrained['circles']),
                         'rectangles': len(constrained.get('rects', [])),
                         'dimensions': corrected_dims, 'ocr_lines': ocr_lines[:20]},
            'accuracy_pipeline': accuracy_results,
            'warnings': warns,
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.post("/digitize/hybrid")
async def digitize_hybrid(file: UploadFile = File(...), real_width_cm: str = Form(None),
                           real_height_cm: str = Form(None), furniture_type: str = Form(None)):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "OPENAI_API_KEY required"}, status_code=400)
    try:
        ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
        job_id = str(uuid.uuid4())
        safe = f"{job_id}_{uuid.uuid4().hex[:8]}"
        img_path = UPLOAD / f"{safe}{ext}"
        with img_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        import httpx, base64
        with open(img_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        mime = 'image/png'

        ai_result = {"furniture_type": "", "confidence": 0, "dimensions": []}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post("https://api.openai.com/v1/chat/completions",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"model": "gpt-4o", "messages": [
                        {"role": "system", "content": "Analyze furniture drawing. Identify the SPECIFIC furniture type from this list: round_pedestal_table, rectangular_table, cabinet, sofa, coffee_table, dining_chair, wardrobe, reception_counter, bed_headboard. For each dimension label, use nearby text to tag it precisely: 'top_dia' (tabletop diameter), 'base_dia' (base plate / pedestal foot / glide diameter), 'neck_dia' (narrowest point of pedestal), 'collar_dia' (metal collar plate just under the top), 'height', 'width', 'depth', 'thickness'. If a pedestal/leg base is the SAME width top-to-bottom (a straight cylinder/column, not visibly tapering), set base_dia and neck_dia to the SAME value. If the furniture is a round_pedestal_table, ALSO visually inspect the pedestal's actual silhouette and return a 'visual_base_estimate' object: {\"profile\":\"cylinder|tapered|flared|unknown\", \"neck_ratio\": ..., \"base_ratio\": ...}. ALSO inspect each visible component (tabletop, collar/base plate, neck/column, base/feet) for its material and finish. If a material is explicitly written/labeled in the image, use that exact text. If NOT labeled, infer the most likely material from visual cues - color, sheen/reflectivity, grain/texture, edge profile (e.g. glossy dark surface with visible weld seams -> 'powder-coated steel'; visible wood grain -> 'solid wood, [color] stain'; matte uniform color -> 'painted MDF' or 'matte lacquer'). Always provide a best-guess material per component, never leave it blank, but mark inferred ones. Return a 'materials' object: {\"component_name\": {\"description\": \"material text\", \"inferred\": true_or_false}}. Return JSON with furniture_type, confidence (0-1), dimensions array [{tag, value_cm}], visual_base_estimate, materials."},
                        {"role": "user", "content": [{"type": "text", "text": "Identify furniture and extract all dimensions."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}}]}
                    ], "max_tokens": 2000, "response_format": {"type": "json_object"}})
                if r.status_code == 200:
                    raw_content = r.json()['choices'][0]['message']['content']
                    try: ai_result = json.loads(raw_content)
                    except (json.JSONDecodeError, ValueError):
                        cleaned = raw_content.strip()
                        if cleaned.startswith('```'): cleaned = cleaned.split('\n', 1)[-1] if '\n' in cleaned else cleaned[3:]
                        if cleaned.rstrip().endswith('```'): cleaned = cleaned.rstrip()[:-3]
                        ai_result = json.loads(cleaned.strip())
        except Exception as e: print(f"[Hybrid] OpenAI error: {e}")

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
            ys = [p[1] for ln in constrained['lines'] for p in ln]
            if ys: pixel_measurements['height'] = max(ys) - min(ys)
        scale_cm_per_pixel, _scale_conf, scale_warns = validate_scale(dims, constrained['lines'])
        corrected_dims = autocorrect_dimensions(dims, pixel_measurements, scale_cm_per_pixel=scale_cm_per_pixel)
        dim_warns = [d['warning'] for d in corrected_dims if d.get('warning')]

        accuracy_results = _run_accuracy_pipeline(img_path, lines, circles, rects, ocr_lines, dims)

        opencv_classifier = classify_furniture(ocr_lines, constrained['circles'], constrained['lines'], constrained.get('rects'))
        opencv_type = opencv_classifier.get('type', 'generic_2d_furniture')
        opencv_conf = opencv_classifier.get('confidence', 0.3)

        try: os.remove(str(img_path))
        except: pass

        raw_ai_type = (ai_result.get('furniture_type', '') or '').strip()
        KNOWN_TYPES = {'round_pedestal_table', 'rectangular_table', 'cabinet', 'sofa',
                       'coffee_table', 'dining_chair', 'chair', 'wardrobe',
                       'reception_counter', 'bed_headboard'}
        if furniture_type: ftype = normalize_furniture_type(furniture_type)
        elif raw_ai_type:
            ftype = normalize_furniture_type(raw_ai_type)
            if ftype not in KNOWN_TYPES:
                opencv_ftype = normalize_furniture_type(opencv_type)
                if opencv_ftype in KNOWN_TYPES: ftype = opencv_ftype
        else: ftype = normalize_furniture_type(opencv_type)

        try: conf = max(float(ai_result.get('confidence', 0) or 0), opencv_conf)
        except: conf = 0.5

        ai_dims = ai_result.get('dimensions', []) or []
        merged_dims = corrected_dims + [
            {'tag': d.get('tag', ''), 'value_cm': float(d.get('value_cm', 0)), 'raw': str(d)}
            for d in ai_dims if isinstance(d, dict)]

        annotation_result = classify_drawing_annotations(ocr_lines, merged_dims)

        known_dims = {}
        for d in merged_dims:
            tag = d.get('tag', '').lower()
            val = float(d.get('value_cm', 0))
            if val > 0:
                if tag in ('top_dia', 'dia', 'diameter'): known_dims['top_diameter_cm'] = val
                elif any(k in tag for k in ['h', 'height']): known_dims['overall_height_cm'] = val
                elif any(k in tag for k in ['w', 'width']): known_dims['top_width_cm'] = val
        segmentation = segment_furniture(ftype, ocr_lines, ai_result, known_dims)

        dxf_name = f'{job_id}_hybrid.dxf'
        dxf_path = OUT / dxf_name
        real_w = _parse_float(real_width_cm)
        real_h = _parse_float(real_height_cm)
        visual_base_estimate = ai_result.get('visual_base_estimate') if isinstance(ai_result, dict) else None
        raw_materials = ai_result.get('materials') if isinstance(ai_result, dict) else None
        materials = {k: (v.get('description', '') if isinstance(v, dict) else str(v))
                     for k, v in (raw_materials or {}).items() if v}
        dispatch_extra = _dispatch_furniture(ftype, dxf_path, merged_dims, real_w, real_h, visual_base_estimate,
                                              materials=materials)

        svg_name = None
        try:
            from app.backend.svg_exporter import drawing_to_svg
            svg_name = f'{job_id}_hybrid.svg'
            svg_path = OUT / svg_name
            resolved = (dispatch_extra or {}).get('resolved_dimensions') or {}
            detected = {'lines': constrained['lines'], 'circles': constrained['circles'],
                        'rects': constrained.get('rects')}
            model = _build_svg_model(ftype, resolved, real_w, real_h, dispatch_extra, detected)
            with open(str(svg_path), 'w', encoding='utf-8') as f2:
                f2.write(drawing_to_svg(model))
        except Exception: svg_name = None

        return JSONResponse({
            'job_id': job_id, 'dxf_file': dxf_name,
            'download': f'/api/download/{dxf_name}',
            'preview_svg': f'/api/preview/svg/{dxf_name}' if svg_name else None,
            'resolved_dimensions': (dispatch_extra or {}).get('resolved_dimensions'),
            'component_schema': (dispatch_extra or {}).get('component_schema'),
            'furniture': {'type': ftype, 'confidence': max(conf, 0.5), 'hybrid': True,
                          'needs_confirmation': max(conf, 0.5) < CLASSIFIER_CONFIRM_THRESHOLD},
            'detected': {'lines': len(constrained['lines']), 'circles': len(constrained['circles']),
                         'rectangles': len(constrained.get('rects', [])),
                         'dimensions': merged_dims, 'ocr_lines': ocr_lines[:20]},
            'ai_analysis': ai_result,
            'materials': raw_materials or {},
            'accuracy_pipeline': accuracy_results,
            'warnings': scale_warns + dim_warns + (dispatch_extra or {}).get('proportion_warnings', []),
        })
    except Exception as e:
        return JSONResponse({"error": f"Hybrid failed: {e}", "trace": traceback.format_exc()}, status_code=500)


# ===== CORRECTION ENDPOINTS =====

@router.post("/corrections/submit")
async def corrections_submit(session_id: str = Form(...),
                              dimension_corrections: str = Form("[]"),
                              line_role_corrections: str = Form("[]")):
    """Submit user corrections for a drawing session."""
    try:
        dim_corrections = json.loads(dimension_corrections)
        role_corrections = json.loads(line_role_corrections)
    except json.JSONDecodeError as e:
        return JSONResponse({"error": f"Invalid JSON: {e}"}, status_code=400)

    result = submit_corrections(session_id, dim_corrections, role_corrections)
    return JSONResponse(result)


@router.get("/corrections/{session_id}")
async def corrections_get(session_id: str):
    """Get saved corrections for a session."""
    result = get_corrections(session_id)
    return JSONResponse(result)


@router.post("/corrections/reset/{session_id}")
async def corrections_reset(session_id: str):
    """Reset all corrections for a session."""
    result = reset_corrections(session_id)
    return JSONResponse(result)


# ===== DOWNLOAD / PREVIEW =====

@router.get("/download/{filename}")
def download(filename: str):
    safe = os.path.basename(filename)
    path = OUT / safe
    if not path.exists(): return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(path, filename=safe, media_type="application/dxf")


@router.get("/preview/svg/{filename}")
def preview_svg(filename: str):
    safe = os.path.basename(filename)
    svg_path = OUT / safe.replace('.dxf', '.svg')
    if svg_path.exists(): return FileResponse(svg_path, media_type="image/svg+xml; charset=utf-8")
    dxf_path = OUT / safe
    if dxf_path.exists():
        import ezdxf, re
        try:
            doc = ezdxf.readfile(str(dxf_path))
            from app.backend.drawing_builders import build_round_pedestal_model
            from app.backend.svg_exporter import drawing_to_svg
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
            with open(str(svg_path), 'w', encoding='utf-8') as f: f.write(svg)
            return FileResponse(svg_path, media_type="image/svg+xml; charset=utf-8")
        except Exception as e: return JSONResponse({"error": f"SVG failed: {e}"}, status_code=500)
    return JSONResponse({"error": "DXF not found"}, status_code=404)


@router.post("/adjust")
async def adjust_dimensions(dxf_file: str = Form(...),
                              top_diameter_cm: float = Form(None),
                              overall_height_cm: float = Form(None),
                              base_diameter_cm: float = Form(None),
                              neck_diameter_cm: float = Form(None),
                              collar_diameter_cm: float = Form(None),
                              top_thickness_cm: float = Form(None),
                              width_cm: float = Form(None),
                              depth_cm: float = Form(None),
                              leg_thickness_cm: float = Form(None)):
    safe = os.path.basename(dxf_file)
    dxf_path = OUT / safe
    if not dxf_path.exists(): return JSONResponse({"error": "DXF not found"}, status_code=404)

    try:
        import ezdxf, re
        doc = ezdxf.readfile(str(dxf_path))
        from app.backend.svg_exporter import drawing_to_svg

        ftype = "round_pedestal_table"
        has_circle = any(e.dxftype() == "CIRCLE" for e in doc.modelspace())
        dim_texts = []
        for e in doc.modelspace():
            if e.dxftype() == "DIMENSION":
                txt = (e.dxf.text if hasattr(e.dxf, "text") else "") or ""
                dim_texts.append(txt)
        all_txt = " ".join(dim_texts).lower()
        if not has_circle and any(k in all_txt for k in ["w =", "width"]): ftype = "rectangular_table"

        if ftype == "rectangular_table":
            w, h, d, lt = 120.0, 70.0, 80.0, 6.0
            for txt in dim_texts:
                nums = re.findall(r'(\d+(?:\.\d+)?)', txt)
                val = float(nums[0]) if nums else None
                if val:
                    if "w =" in txt.lower() or "width" in txt.lower(): w = val
                    elif "h =" in txt.lower() or "height" in txt.lower(): h = val
                    elif "d =" in txt.lower() or "depth" in txt.lower(): d = val
            if width_cm is not None: w = width_cm
            if overall_height_cm is not None: h = overall_height_cm
            if depth_cm is not None: d = depth_cm
            if leg_thickness_cm is not None: lt = leg_thickness_cm

            from app.backend.dxf_exporter import save_rectangular_table
            try: save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, leg_thickness_cm=lt)
            except Exception as e: print(f"[Adjust] Rect DXF regen failed: {e}")

            from app.backend.drawing_builders import build_rectangular_table_model
            model = build_rectangular_table_model(w, d, h, lt)
            svg = drawing_to_svg(model)
            svg_path = OUT / safe.replace('.dxf', '.svg')
            with open(str(svg_path), 'w', encoding='utf-8') as f: f.write(svg)

            return JSONResponse({"furniture_type": "rectangular_table", "dxf_file": safe,
                "preview_svg": f"/api/preview/svg/{safe}",
                "dimensions": {"width_cm": w, "depth_cm": d, "overall_height_cm": h, "leg_thickness_cm": lt}})

        from app.backend.drawing_builders import build_round_pedestal_model
        top_dia, height = 80.0, 70.0
        base_dia, neck_dia, top_thick = 44.0, 22.4, 4.0
        collar_dia = None

        # Prefer the structured JSON sidecar saved at generation time over
        # scraping DIMENSION entity text: the text-scrape heuristic ("dia"
        # text with value > 50cm is the top diameter, else the base") breaks
        # whenever a non-top component (e.g. a 60cm base plate) also exceeds
        # 50cm - it gets misread as the top diameter, silently corrupting an
        # otherwise-correct value on every subsequent /adjust call.
        json_path = Path(str(dxf_path).replace('.dxf', '.json'))
        loaded_from_sidecar = False
        sidecar_materials = {}
        if json_path.exists():
            try:
                sidecar = json.loads(json_path.read_text(encoding='utf-8'))
                known = sidecar.get('known_dimensions', {})
                est = sidecar.get('estimated_components', {})
                sidecar_materials = sidecar.get('materials', {})
                if known.get('top_diameter_cm'): top_dia = known['top_diameter_cm']
                if known.get('overall_height_cm'): height = known['overall_height_cm']
                if est.get('pedestal_diameter_cm'): base_dia = est['pedestal_diameter_cm']
                if est.get('neck_diameter_cm'): neck_dia = est['neck_diameter_cm']
                if est.get('top_thickness_cm'): top_thick = est['top_thickness_cm']
                if est.get('collar_diameter_cm'): collar_dia = est['collar_diameter_cm']
                loaded_from_sidecar = True
            except Exception as e:
                print(f"[Adjust] sidecar load failed: {e}")

        if not loaded_from_sidecar:
            for txt in dim_texts:
                nums = re.findall(r'(\d+(?:\.\d+)?)', txt)
                val = float(nums[0]) if nums else None
                if val:
                    if "%%c" in txt or "dia" in txt.lower():
                        if val > 50: top_dia = val
                        else: base_dia = val
                    if "h =" in txt.lower() or "height" in txt.lower(): height = val

        if top_diameter_cm is not None: top_dia = top_diameter_cm
        if overall_height_cm is not None: height = overall_height_cm
        if base_diameter_cm is not None: base_dia = base_diameter_cm
        if neck_diameter_cm is not None: neck_dia = neck_diameter_cm
        if top_thickness_cm is not None: top_thick = top_thickness_cm
        if collar_diameter_cm is not None: collar_dia = collar_diameter_cm

        from app.backend.dxf_exporter import save_round_pedestal_table
        try: save_round_pedestal_table(str(dxf_path), top_dia_cm=top_dia, height_cm=height,
                                         base_dia_cm=base_dia, neck_dia_cm=neck_dia,
                                         top_thick_cm=top_thick, collar_dia_cm=collar_dia,
                                         materials=sidecar_materials)
        except Exception as e: print(f"[Adjust] DXF regen failed: {e}")

        model = build_round_pedestal_model(top_dia_cm=top_dia, height_cm=height,
            base_dia_cm=base_dia, neck_dia_cm=neck_dia,
            top_thick_cm=top_thick, collar_dia_cm=(collar_dia or top_dia * 0.625),
            materials=sidecar_materials)
        svg = drawing_to_svg(model)
        svg_path = OUT / safe.replace('.dxf', '.svg')
        with open(str(svg_path), 'w', encoding='utf-8') as f: f.write(svg)

        try:
            from app.backend.brain_sync import record_proportion
            record_proportion('round_pedestal_table', 'top_diameter_cm', top_dia, 'pedestal_diameter_cm', base_dia)
            record_proportion('round_pedestal_table', 'top_diameter_cm', top_dia, 'neck_diameter_cm', neck_dia)
        except Exception as e: print(f"[Adjust] brain_sync recording failed: {e}")

        final_collar_dia = round(collar_dia or top_dia * 0.625, 1)
        from app.backend.dimension_validator import check_round_pedestal_proportions
        proportion_warnings = check_round_pedestal_proportions(top_dia, {
            'collar_diameter_cm': final_collar_dia,
            'pedestal_diameter_cm': base_dia,
            'neck_diameter_cm': neck_dia,
        })

        # Persist the adjusted state so it doesn't go stale on the *next*
        # /adjust call (which loads defaults from this same sidecar).
        try:
            json_path.write_text(json.dumps({
                'known_dimensions': {'top_diameter_cm': top_dia, 'overall_height_cm': height},
                'estimated_components': {'pedestal_diameter_cm': base_dia, 'neck_diameter_cm': neck_dia,
                                          'top_thickness_cm': top_thick, 'collar_diameter_cm': final_collar_dia},
                'materials': sidecar_materials,
            }, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[Adjust] sidecar persist failed: {e}")

        return JSONResponse({"dxf_file": safe, "preview_svg": f"/api/preview/svg/{safe}",
            "dimensions": {"top_diameter_cm": round(top_dia, 1), "overall_height_cm": round(height, 1),
                           "base_diameter_cm": round(base_dia, 1), "neck_diameter_cm": round(neck_dia, 1),
                           "top_thickness_cm": round(top_thick, 1),
                           "collar_diameter_cm": final_collar_dia},
            "warnings": proportion_warnings})
    except Exception as e: return JSONResponse({"error": f"Adjust failed: {e}"}, status_code=500)


@router.post("/material/edit")
async def edit_materials(dxf_file: str = Form(...), materials: str = Form(...),
                          drawing_title: str = Form(None), project: str = Form(None),
                          client: str = Form(None)):
    """Edit per-component material/finish text (and optional title-block text)
    on an existing drawing, regenerating both DXF and SVG with the current
    dimensions preserved from the sidecar JSON.

    `materials` is a JSON object string: {"tabletop": "...", "collar_plate": "...", ...}
    Known component keys for round_pedestal_table: tabletop, collar_plate,
    neck_ring, pedestal_body, base_foot.
    """
    safe = os.path.basename(dxf_file)
    dxf_path = OUT / safe
    if not dxf_path.exists():
        return JSONResponse({"error": "DXF not found"}, status_code=404)

    try:
        new_materials = json.loads(materials)
        if not isinstance(new_materials, dict):
            return JSONResponse({"error": "materials must be a JSON object"}, status_code=400)
    except json.JSONDecodeError as e:
        return JSONResponse({"error": f"Invalid materials JSON: {e}"}, status_code=400)

    json_path = Path(str(dxf_path).replace('.dxf', '.json'))
    if not json_path.exists():
        return JSONResponse({"error": "No drawing data found for this file - re-digitize first"}, status_code=404)

    try:
        sidecar = json.loads(json_path.read_text(encoding='utf-8'))
        furniture_type = sidecar.get('furniture_type', 'round_pedestal_table')
        known = sidecar.get('known_dimensions', {})
        est = sidecar.get('estimated_components', {})
        merged_materials = {**sidecar.get('materials', {}), **new_materials}

        from app.backend.svg_exporter import drawing_to_svg

        if furniture_type == 'round_pedestal_table':
            from app.backend.drawing_builders import build_round_pedestal_model
            from app.backend.dxf_exporter import save_round_pedestal_table
            top_dia = known.get('top_diameter_cm', 80.0)
            height = known.get('overall_height_cm', 70.0)
            base_dia = est.get('pedestal_diameter_cm', 44.0)
            neck_dia = est.get('neck_diameter_cm', 22.4)
            top_thick = est.get('top_thickness_cm', 4.0)
            collar_dia = est.get('collar_diameter_cm')

            try:
                save_round_pedestal_table(str(dxf_path), top_dia_cm=top_dia, height_cm=height,
                                           base_dia_cm=base_dia, neck_dia_cm=neck_dia,
                                           top_thick_cm=top_thick, collar_dia_cm=collar_dia,
                                           materials=merged_materials)
            except Exception as e:
                print(f"[MaterialEdit] DXF regen failed: {e}")

            model = build_round_pedestal_model(top_dia_cm=top_dia, height_cm=height,
                base_dia_cm=base_dia, neck_dia_cm=neck_dia, top_thick_cm=top_thick,
                collar_dia_cm=(collar_dia or top_dia * 0.625), materials=merged_materials,
                project=project or "Furniture Shop Drawing", client=client or "")
        else:
            return JSONResponse({"error": f"Material editing not yet supported for {furniture_type}"},
                                 status_code=400)

        svg = drawing_to_svg(model)
        svg_path = OUT / safe.replace('.dxf', '.svg')
        with open(str(svg_path), 'w', encoding='utf-8') as f:
            f.write(svg)

        sidecar['materials'] = merged_materials
        json_path.write_text(json.dumps(sidecar, indent=2), encoding='utf-8')

        return JSONResponse({"dxf_file": safe, "preview_svg": f"/api/preview/svg/{safe}",
                              "materials": merged_materials})
    except Exception as e:
        return JSONResponse({"error": f"Material edit failed: {e}", "trace": traceback.format_exc()},
                             status_code=500)


@router.get("/preview/{filename}")
def preview_dxf(filename: str):
    safe = os.path.basename(filename)
    path = OUT / safe
    if not path.exists(): return JSONResponse({"error": "DXF not found"}, status_code=404)
    png_name = safe.replace('.dxf', '.png')
    png_path = OUT / png_name
    if not png_path.exists():
        try:
            import matplotlib; matplotlib.use('Agg')
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
            ax.set_xlim(-10, 440); ax.set_ylim(-10, 310); ax.axis('off')
            fig.savefig(str(png_path), dpi=100, facecolor='white', bbox_inches='tight', pad_inches=0.1)
            plt.close(fig)
        except Exception as e: return JSONResponse({"error": f"Preview failed: {e}"}, status_code=500)
    return FileResponse(png_path, media_type="image/png")


@router.get("/preview/pdf/{filename}")
def preview_pdf(filename: str):
    safe = os.path.basename(filename)
    dxf_path = OUT / safe
    if not dxf_path.exists(): return JSONResponse({"error": "DXF not found"}, status_code=404)
    pdf_name = safe.replace('.dxf', '.pdf')
    pdf_path = OUT / pdf_name
    if not pdf_path.exists():
        try:
            import matplotlib; matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import ezdxf
            doc = ezdxf.readfile(str(dxf_path))
            fig = plt.figure(figsize=(16.54, 11.69), dpi=150)
            ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
            ctx = RenderContext(doc); backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
            ax.set_xlim(-10, 440); ax.set_ylim(-10, 310); ax.set_aspect('equal'); ax.axis('off')
            fig.savefig(str(pdf_path), dpi=150, facecolor='white'); plt.close(fig)
        except Exception:
            from app.services.pdf_exporter import export_pdf_shop_drawing
            export_pdf_shop_drawing(dxf_path, pdf_path,
                furniture_type=safe.replace('_digitized.dxf','').replace('_hybrid.dxf','').replace('_',' ').title())
    return FileResponse(pdf_path, filename=pdf_name, media_type="application/pdf")


@router.post("/export/freecad")
async def export_freecad(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    dxf_path = OUT / f"{job_id}_input.dxf"
    fcstd_path = OUT / f"{job_id}_model.FCStd"
    with dxf_path.open("wb") as f: shutil.copyfileobj(file.file, f)
    from app.services.freecad_exporter import export_freecad_fcstd
    ok = export_freecad_fcstd(dxf_path, fcstd_path, furniture_type="furniture")
    try: os.unlink(str(dxf_path))
    except: pass
    if not ok: return JSONResponse({"error": "FreeCAD export failed"}, status_code=500)
    return FileResponse(fcstd_path, filename=f"{job_id}_model.FCStd", media_type="application/octet-stream")


# ===== ML ENDPOINTS =====

@router.post("/ml/feedback")
async def ml_feedback(session_id: str = Form(...), predicted_type: str = Form(None),
                      corrected_type: str = Form(None), confidence: float = Form(0), verified: bool = Form(False)):
    from app.services.ml_engine import store_feedback
    predicted = {"type": predicted_type, "confidence": confidence}
    corrected = {"type": corrected_type or predicted_type}
    ok = store_feedback(session_id, predicted, corrected, verified)
    return JSONResponse({"stored": ok, "total_feedback": count_feedback()})

@router.get("/ml/status")
async def ml_status():
    from app.services.ml_engine import get_ml_status, get_feedback_count, should_retrain
    return JSONResponse({"feedback_samples": get_feedback_count(), "should_retrain": should_retrain(), "status": get_ml_status()})

@router.post("/ml/predict")
async def ml_predict(file: UploadFile = File(...)):
    from app.services.ml_engine import furniture_classifier, dimension_predictor
    from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles
    from app.backend.ocr import ocr_dimensions
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
    img_path = UPLOAD / f"{job_id}{ext}"
    with img_path.open("wb") as f: shutil.copyfileobj(file.file, f)
    ocr_lines, ocr_dims = ocr_dimensions(str(img_path))
    img, gray = load_image(str(img_path)); binary = preprocess(gray)
    geometry = {"lines": detect_lines(binary), "circles": detect_circles(gray), "rects": detect_rectangles(binary)}
    furn_pred = furniture_classifier.predict(str(img_path), "\n".join(ocr_lines), geometry)
    dim_pred = dimension_predictor.predict(geometry, ocr_dims, furn_pred["type"])
    try: os.unlink(str(img_path))
    except: pass
    return JSONResponse({"job_id": job_id, "furniture": furn_pred, "dimensions": dim_pred, "ml_available": furn_pred.get("ml", False)})

@router.post("/ml/retrain")
async def ml_retrain():
    from app.services.ml_engine import retrain_models
    return JSONResponse(retrain_models())


# ===== CENTRAL BRAIN ENDPOINTS =====

@router.get("/brain/report")
async def brain_report():
    from app.backend.brain_sync import get_intelligence_report
    return JSONResponse(get_intelligence_report())

@router.get("/brain/proportions")
async def brain_proportions(furniture_type: str = "round_pedestal_table",
                            anchor_dimension: str = "top_diameter_cm",
                            anchor_value: float = 80.0, component: str = "pedestal_diameter_cm"):
    from app.backend.brain_sync import get_proportion_estimate
    est = get_proportion_estimate(furniture_type, anchor_dimension, anchor_value, component)
    return JSONResponse({"estimate": est} if est else {"estimate": None, "note": "Not enough data yet"})

@router.get("/brain/materials")
async def brain_materials(component: str = "tabletop", furniture_type: str = None):
    from app.backend.brain_sync import get_material_suggestions
    suggestions = get_material_suggestions(component, furniture_type)
    return JSONResponse({"component": component, "suggestions": suggestions})


# ===== BATCH CONVERT =====

@router.post("/batch")
async def batch_convert(files: List[UploadFile] = File(...)):
    import zipfile, io, uuid
    buf = io.BytesIO()
    results = []
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            try:
                job_id = str(uuid.uuid4())
                img_path = UPLOAD / f"{job_id}_{file.filename}"
                with img_path.open("wb") as f: f.write(await file.read())
                img, gray = load_image(str(img_path)); binary = preprocess(gray)
                lines = normalize_lines(detect_lines(binary))
                circles = detect_circles(gray); rects = detect_rectangles(binary)
                ocr_lines, ocr_dims = ocr_dimensions(str(img_path))
                constrained = process_constraints(lines, circles, ocr_dims, rects)
                classifier = classify_furniture(ocr_lines, constrained["circles"], constrained["lines"], constrained.get("rects"))
                ftype = normalize_furniture_type(classifier["type"])
                corrected_dims = autocorrect_dimensions(ocr_dims, {})
                dxf_name = f"{job_id}_batch.dxf"
                dxf_path = OUT / dxf_name
                _dispatch_furniture(ftype, dxf_path, corrected_dims, 0.0, 0.0)
                if dxf_path.exists(): zf.write(str(dxf_path), dxf_name)
                try: os.unlink(str(img_path))
                except: pass
                results.append({"file": file.filename, "furniture_type": ftype, "dxf": dxf_name, "status": "ok"})
            except Exception as e: results.append({"file": file.filename, "status": "error", "error": str(e)[:100]})
    buf.seek(0)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename=batch_convert_{len(files)}_files.zip"})


@router.get("/view/{filename}")
def view_drawing(filename: str):
    safe = os.path.basename(filename)
    svg_path = OUT / safe.replace('.dxf', '.svg').replace('.json', '.svg')
    if not svg_path.exists():
        dxf_path = OUT / safe.replace('.svg', '.dxf')
        if dxf_path.exists():
            from app.backend.drawing_builders import build_round_pedestal_model
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
            with open(str(svg_path), 'w', encoding='utf-8') as f: f.write(svg)
    if not svg_path.exists(): return JSONResponse({"error": "Drawing not found"}, status_code=404)
    svg = svg_path.read_text()
    return HTMLResponse(f"""<!DOCTYPE html><html><head><title>CAD Drawing — {safe}</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>body{{margin:0;display:flex;justify-content:center;background:#f0f0f0}}</style></head><body>{svg}</body></html>""")


# ===== STYLE PRESETS =====

@router.get("/presets")
async def list_presets_endpoint():
    from app.backend.style_presets import list_presets as lp
    presets = lp()
    return JSONResponse({"presets": [p.to_dict() for p in presets], "count": len(presets)})

@router.post("/presets/save")
async def save_preset_endpoint(name: str = Form(...), session_id: str = Form(None), furniture_type: str = Form(None)):
    from app.backend.style_presets import StylePreset, preset_from_chat_state, save_preset as sp
    state = CHAT_SESSIONS.get(session_id or "default", {})
    preset = preset_from_chat_state(state, name)
    if furniture_type: preset.furniture_type = furniture_type
    filename = sp(preset)
    return JSONResponse({"saved": filename, "preset": preset.to_dict()})

@router.post("/presets/apply")
async def apply_preset_endpoint(name: str = Form(...)):
    from app.backend.style_presets import load_preset, apply_preset_to_template
    preset = load_preset(name)
    if not preset: return JSONResponse({"error": "Preset not found"}, status_code=404)
    params = apply_preset_to_template(preset)
    return JSONResponse({"preset": preset.to_dict(), "params": params})

@router.delete("/presets/{name}")
async def delete_preset_endpoint(name: str):
    from app.backend.style_presets import delete_preset as dp
    return JSONResponse({"deleted": dp(name)})


# ===== CHAT ENDPOINTS =====

CHAT_SESSIONS: dict = {}

# File-based persistence for chat sessions (survives server restarts)
_CHAT_STORE = OUT / "chat_sessions.json"
if _CHAT_STORE.exists():
    try:
        with open(_CHAT_STORE) as f:
            CHAT_SESSIONS.update(json.load(f))
    except Exception: pass

@router.post("/chat")
async def chat_message(message: str = Form(...), session_id: str = Form(None), image_id: str = Form(None),
                        dxf_file: str = Form(None)):
    from app.backend.chat_agent import chat_with_agent
    from app.backend.feedback_learner import learn_from_chat, get_adjustment_hints, load_preferences, apply_preferences
    sid = session_id or "default"
    prev_state = CHAT_SESSIONS.get(sid)

    # Seed the chat's known dimensions from the drawing's own sidecar JSON so
    # the LLM can reason about values it was never explicitly told via chat
    # (e.g. neck/collar diameter set during initial generation, not chat) -
    # without this, relational requests like "make X different from Y" have
    # no "current value of Y" to reason from and silently no-op.
    if dxf_file and (not prev_state or not prev_state.get("dimensions")):
        try:
            json_path = OUT / os.path.basename(dxf_file).replace('.dxf', '.json')
            if json_path.exists():
                sidecar = json.loads(json_path.read_text(encoding='utf-8'))
                seeded_dims = {**sidecar.get('known_dimensions', {}), **sidecar.get('estimated_components', {})}
                prev_state = {**(prev_state or {}), "dimensions": {**seeded_dims, **(prev_state or {}).get("dimensions", {})}}
        except Exception as e:
            print(f"[Chat] sidecar seed failed: {e}")

    result = chat_with_agent(message, prev_state)
    CHAT_SESSIONS[sid] = result["state"]
    try:
        with open(_CHAT_STORE, 'w') as f:
            json.dump(dict(CHAT_SESSIONS), f, indent=2)
    except Exception: pass
    corrections = learn_from_chat(sid, prev_state or {}, result["state"], user_id=session_id or "default")
    try:
        from app.backend.brain_sync import record_correction as brc, record_material as brm
        for c in corrections:
            brc(sid, result["state"].get("furniture_type", ""), c.field, c.old_value, c.new_value,
                correction_type="dimension" if c.field.endswith("_cm") else "material")
        for comp, mat in result["state"].get("materials", {}).items(): brm(comp, str(mat))
    except Exception: pass
    hints = get_adjustment_hints(user_id=session_id or "default") if len(corrections) > 0 else []
    return JSONResponse({"session_id": sid, "response": result["response"], "action": result["action"],
        "render_hint": result["render_hint"], "state": result["state"], "image_id": image_id,
        "corrections_learned": len(corrections), "adjustment_hints": hints[:5] if hints else []})

@router.get("/chat/state")
async def chat_state(session_id: str = "default"):
    state = CHAT_SESSIONS.get(session_id, {})
    return JSONResponse({"session_id": session_id, "state": state})

@router.get("/chat/sessions")
async def chat_sessions():
    return JSONResponse({"sessions": list(CHAT_SESSIONS.keys()), "count": len(CHAT_SESSIONS)})


# ===== ECHO DRAFTER =====

@router.get("/learn/preferences")
async def get_preferences(user_id: str = "default"):
    from app.backend.feedback_learner import load_preferences, get_adjustment_hints
    model = load_preferences(user_id)
    return JSONResponse({"user_id": user_id, "preferences": model.to_dict(),
        "hints": get_adjustment_hints(user_id), "model_active": model.correction_count >= 3})

# ===== ACCURACY BENCHMARK =====

@router.get("/benchmark")
async def run_benchmark_endpoint():
    """Run accuracy benchmark against ground truth fixtures."""
    result = run_accuracy_benchmark()
    return JSONResponse(result)

@router.get("/benchmark/fixtures")
async def list_benchmark_fixtures():
    """List available benchmark fixtures."""
    fixtures = load_fixtures()
    return JSONResponse({
        "count": len(fixtures),
        "fixtures": [f.to_dict() for f in fixtures],
    })


# ===== SECTION PREDICTOR =====

@router.get("/sections/predict")
async def predict_sections_endpoint(
    furniture_type: str = "round_pedestal_table",
    width_cm: float = 80.0,
    height_cm: float = 70.0,
    depth_cm: float = 60.0,
    diameter_cm: float = 80.0,
):
    """Predict shop drawing sections for a furniture piece."""
    params = {"w": width_cm, "h": height_cm, "d": depth_cm, "dia": diameter_cm}
    result = predict_drawing_sections(furniture_type, params)
    return JSONResponse(result)


# ===== LEARNED USERS =====

@router.get("/learn/users")
async def list_learned_users():
    from app.backend.feedback_learner import get_all_users, load_preferences
    users = get_all_users()
    result = {}
    for uid in users:
        model = load_preferences(uid)
        result[uid] = {"corrections": model.correction_count, "confidence": round(model.confidence, 2),
                       "last_updated": model.last_updated}
    return JSONResponse({"users": result, "total": len(users)})

@router.post("/learn/apply")
async def apply_learned_preferences(user_id: str = Form("default"), session_id: str = Form(None)):
    from app.backend.feedback_learner import apply_preferences, load_preferences, get_adjustment_hints
    state = CHAT_SESSIONS.get(session_id or "default", {})
    adjusted = apply_preferences(state, user_id)
    hints = get_adjustment_hints(user_id)
    return JSONResponse({"user_id": user_id, "adjusted_params": adjusted, "hints": hints})
