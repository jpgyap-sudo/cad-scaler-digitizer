"""
Pipeline: Orchestrate full digitization flow.
Vision → OCR → Classify → Scale → DXF
"""
from pathlib import Path
from typing import Optional, List, Tuple, Any
from .vision import (
    load_gray, preprocess, detect_lines, detect_circles,
    detect_rectangles, ocr_dimensions, normalize_lines
)
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
            return d['value_cm']
    if fallback is not None:
        return fallback
    vals = [d['value_cm'] for d in dims]
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
    Full pipeline: load → detect → OCR → classify → scale → save DXF.
    
    Returns JSON result with download URL and metadata.
    """
    img, gray = load_gray(image_path)
    binary = preprocess(gray)
    lines_raw = detect_lines(binary)
    lines = normalize_lines(lines_raw)
    circles = detect_circles(gray)
    rects = detect_rectangles(binary)
    ocr_lines, dims = ocr_dimensions(image_path)

    # Furniture classification (with optional override)
    if furniture_override:
        furniture = {
            "type": furniture_override,
            "confidence": 1.0,
            "required_dimensions": [],
            "missing_dimensions": [],
            "recommended_template": ""
        }
    else:
        furniture = classify_furniture(ocr_lines, circles, lines, rects)

    out = Path(out_dir)
    dxf_name = f'{job_id}_digitized.dxf'
    dxf_path = out / dxf_name
    warnings = []

    # Template-based reconstruction for known furniture types
    ftype = furniture['type']
    if ftype == 'round_pedestal_table':
        dia = real_width_cm or _pick_dimension(dims, ['dia', 'diameter', 'width', 'w'], 80.0)
        height = real_height_cm or _pick_dimension(dims, ['h', 'height'], 70.0)
        save_round_pedestal_table(str(dxf_path), top_dia_cm=dia, height_cm=height)
        warnings.append(f"Reconstructed as round pedestal table Ø{dia:.0f}cm x H{height:.0f}cm")

    elif ftype == 'rectangular_table':
        w = real_width_cm or _pick_dimension(dims, ['w', 'width'], 120.0)
        h = real_height_cm or _pick_dimension(dims, ['h', 'height'], 70.0)
        d = _pick_dimension(dims, ['d', 'depth'], w * 0.67)
        save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
        warnings.append(f"Reconstructed as rectangular table {w:.0f}x{d:.0f}x{h:.0f}cm")

    elif ftype == 'cabinet':
        w = real_width_cm or _pick_dimension(dims, ['w', 'width'], 100.0)
        h = real_height_cm or _pick_dimension(dims, ['h', 'height'], 180.0)
        d = _pick_dimension(dims, ['d', 'depth'], 50.0)
        save_cabinet(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
        warnings.append(f"Reconstructed as cabinet {w:.0f}x{d:.0f}x{h:.0f}cm")

    elif ftype == 'sofa':
        w = real_width_cm or _pick_dimension(dims, ['w', 'width'], 200.0)
        h = real_height_cm or _pick_dimension(dims, ['h', 'height'], 85.0)
        sh = _pick_dimension(dims, ['seat', 'seat_height'], 45.0)
        d = _pick_dimension(dims, ['d', 'depth'], 80.0)
        save_sofa(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, seat_height_cm=sh)
        warnings.append(f"Reconstructed as sofa {w:.0f}x{d:.0f}x{h:.0f}cm")

    else:
        # Generic: pixel-to-cm scaling, fallback 1px = 0.1cm
        scale = 0.1
        if real_width_cm and lines:
            xs = [p[0] for ln in lines for p in ln]
            if max(xs) > min(xs):
                scale = real_width_cm / (max(xs) - min(xs))
        elif dims:
            # Try to derive scale from OCR dimensions
            first_dim = dims[0]['value_cm']
            # Assume first dimension corresponds to the longest detected line
            if lines:
                xs = [p[0] for ln in lines for p in ln]
                pixel_length = max(xs) - min(xs)
                if pixel_length > 0:
                    scale = first_dim / pixel_length
                    warnings.append(f"Auto-scaled from OCR dimension: {first_dim}cm")

        save_generic(str(dxf_path), lines, circles, rects, scale)
        warnings.append(f"Generic tracing output at scale {scale:.4f} cm/pixel")

    return {
        'job_id': job_id,
        'download': f'/api/download/{dxf_name}',
        'dxf_file': dxf_name,
        'furniture': furniture,
        'detected': {
            'lines': len(lines),
            'circles': len(circles),
            'rectangles': len(rects),
            'dimensions': dims,
            'ocr_lines': ocr_lines[:30],
        },
        'warnings': warnings
    }
