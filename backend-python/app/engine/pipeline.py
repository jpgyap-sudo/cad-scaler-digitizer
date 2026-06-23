"""
Pipeline: Orchestrate full digitization flow with constraint solving.
Vision → OCR → Constraint Snapping → Classify → Scale → Professional DXF
"""
from pathlib import Path
from typing import Optional, List, Any
from .vision import (
    load_gray, preprocess, detect_lines, detect_circles,
    detect_rectangles, ocr_dimensions, normalize_lines
)
from .constraints import process_constraints, autocorrect_dimensions
from .furniture_classifier import classify_furniture
from .dxf_writer import (
    save_generic, save_round_pedestal_table,
    save_rectangular_table, save_cabinet, save_sofa
)


def _pick_dimension(dims: List[dict], tags: List[str], fallback: Optional[float] = None) -> Optional[float]:
    """Pick first dimension matching any of the given tags."""
    for d in dims:
        tag = d.get('tag', '')
        if any(t in tag for t in tags):
            return d.get('value_cm', d.get('value', None))
    if fallback is not None:
        return fallback
    vals = [d.get('value_cm', d.get('value', 0)) for d in dims]
    return vals[0] if vals else None


def process_image(
    image_path: str,
    out_dir: str,
    job_id: str,
    real_width_cm: Optional[float] = None,
    real_height_cm: Optional[float] = None,
    furniture_override: Optional[str] = None
) -> dict:
    """
    Full pipeline: load → detect → constraints → OCR → classify → scale → professional DXF.
    """
    img, gray = load_gray(image_path)
    binary = preprocess(gray)
    lines_raw = detect_lines(binary)
    lines = normalize_lines(lines_raw)
    circles = detect_circles(gray)
    rects = detect_rectangles(binary)
    ocr_lines, dims = ocr_dimensions(image_path)

    # ---- CONSTRAINT SOLVER ----
    constrained = process_constraints(lines, circles, dims, rects)

    # ---- AUTOCORRECT DIMENSIONS ----
    # Calculate pixel measurements for cross-validation
    pixel_measurements = {}
    if constrained['circles']:
        pixel_measurements['diameter'] = constrained['circles'][0][2] * 2
    if constrained['lines']:
        xs = [p[0] for ln in constrained['lines'] for p in ln]
        if xs:
            pixel_measurements['width'] = max(xs) - min(xs)
            pixel_measurements['height'] = max([p[1] for ln in constrained['lines'] for p in ln]) - \
                                           min([p[1] for ln in constrained['lines'] for p in ln])

    corrected_dims = autocorrect_dimensions(dims, pixel_measurements)

    # ---- FURNITURE CLASSIFICATION ----
    if furniture_override:
        furniture = {
            "type": furniture_override, "confidence": 1.0,
            "required_dimensions": [], "missing_dimensions": [],
            "constraint_snapped": True
        }
    else:
        cv_furniture = classify_furniture(ocr_lines, constrained['circles'], constrained['lines'], constrained.get('rects'))
        furniture = {**cv_furniture, "constraint_snapped": True}

    # ---- GENERATE PROFESSIONAL DXF ----
    out = Path(out_dir)
    dxf_name = f'{job_id}_digitized.dxf'
    dxf_path = out / dxf_name
    warnings = []
    ftype = furniture['type']

    if ftype == 'round_pedestal_table':
        dia = real_width_cm or _pick_dimension(corrected_dims, ['dia', 'diameter', 'width', 'w'], 80.0)
        height = real_height_cm or _pick_dimension(corrected_dims, ['h', 'height'], 70.0)
        save_round_pedestal_table(str(dxf_path), top_dia_cm=dia, height_cm=height)
        warnings.append(f"✅ Professional reconstruction: Round Pedestal Table Ø{dia:.0f} x H{height:.0f}cm")

    elif ftype == 'rectangular_table':
        w = real_width_cm or _pick_dimension(corrected_dims, ['w', 'width'], 120.0)
        h = real_height_cm or _pick_dimension(corrected_dims, ['h', 'height'], 70.0)
        d = _pick_dimension(corrected_dims, ['d', 'depth'], w * 0.67)
        save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
        warnings.append(f"✅ Professional reconstruction: Rectangular Table {w:.0f}x{d:.0f}x{h:.0f}cm")

    elif ftype == 'cabinet':
        w = real_width_cm or _pick_dimension(corrected_dims, ['w', 'width'], 100.0)
        h = real_height_cm or _pick_dimension(corrected_dims, ['h', 'height'], 180.0)
        d = _pick_dimension(corrected_dims, ['d', 'depth'], 50.0)
        save_cabinet(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
        warnings.append(f"✅ Professional reconstruction: Cabinet {w:.0f}x{d:.0f}x{h:.0f}cm")

    elif ftype == 'sofa':
        w = real_width_cm or _pick_dimension(corrected_dims, ['w', 'width'], 200.0)
        h = real_height_cm or _pick_dimension(corrected_dims, ['h', 'height'], 85.0)
        sh = _pick_dimension(corrected_dims, ['seat', 'seat_height'], 45.0)
        d = _pick_dimension(corrected_dims, ['d', 'depth'], 80.0)
        save_sofa(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, seat_height_cm=sh)
        warnings.append(f"✅ Professional reconstruction: Sofa {w:.0f}x{d:.0f}x{h:.0f}cm")

    else:
        scale = 0.1
        if real_width_cm and constrained['lines']:
            xs = [p[0] for ln in constrained['lines'] for p in ln]
            if max(xs) > min(xs):
                scale = real_width_cm / (max(xs) - min(xs))
        elif corrected_dims and constrained['lines']:
            first_dim = corrected_dims[0].get('value_cm', 0)
            xs = [p[0] for ln in constrained['lines'] for p in ln]
            pixel_length = max(xs) - min(xs) if xs else 1
            if pixel_length > 0:
                scale = first_dim / pixel_length

        save_generic(str(dxf_path), constrained['lines'], constrained['circles'],
                     constrained.get('rects'), scale)
        warnings.append(f"Generic tracing with constraint snapping at scale {scale:.4f} cm/pixel")

    return {
        'job_id': job_id,
        'download': f'/api/download/{dxf_name}',
        'dxf_file': dxf_name,
        'furniture': furniture,
        'detected': {
            'lines': len(constrained['lines']),
            'circles': len(constrained['circles']),
            'rectangles': len(constrained.get('rects', [])),
            'rebuilt_circles': constrained.get('rebuilt_circles', 0),
            'dimensions': corrected_dims,
            'ocr_lines': ocr_lines[:30],
        },
        'warnings': warnings,
        'constraint_engine': {
            'enabled': True,
            'angle_snapped': True,
            'endpoint_snapped': True,
            'circles_rebuilt': constrained.get('rebuilt_circles', 0),
            'dimensions_autocorrected': sum(1 for d in corrected_dims if d.get('autocorrected')),
        }
    }
