"""
Module: dimension_validator.py
Cross-validate OCR dimensions against OpenCV geometry measurements.
"""
import math
from typing import List, Optional


def autocorrect_dimensions(ocr_dims: list, pixel_measurements: dict, tolerance: float = 0.15) -> list:
    """Snap pixel measurements to OCR text values within tolerance."""
    corrected = []
    for dim in ocr_dims:
        tag = dim.get('tag', '')
        value = dim.get('value_cm', dim.get('value', 0))
        pixel_val = pixel_measurements.get(tag)
        if pixel_val is not None and value > 0:
            diff = abs(value - pixel_val) / value
            if diff < tolerance:
                corrected.append({**dim, 'value_cm': round(value, 1), 'autocorrected': True})
            else:
                corrected.append({**dim, 'warning': f'OCR={value}cm vs pixel={pixel_val:.1f}cm'})
        else:
            corrected.append(dim)
    return corrected


def align_dimension_to_ocr(value: float, dims: list, tags: list) -> float:
    """Snap raw value to OCR dimension if within 15% tolerance."""
    for d in dims:
        tag = d.get('tag', '')
        ocr_val = d.get('value_cm', d.get('value', 0))
        if any(t in tag for t in tags) and ocr_val > 0:
            diff = abs(value - ocr_val) / max(value, ocr_val)
            if diff < 0.15:
                return ocr_val
    return value


def validate_scale(ocr_dims: list, lines: list) -> tuple:
    """Validate and compute scale from OCR dimensions vs detected lines.
    Returns (scale_cm_per_pixel, confidence, warnings)."""
    warnings = []
    if not lines or not ocr_dims:
        return 0.1, 0.0, ["No lines or dimensions to compute scale"]

    xs = [p[0] for ln in lines for p in ln]
    pixel_width = max(xs) - min(xs) if xs else 1
    if pixel_width <= 0:
        return 0.1, 0.0, ["Zero pixel width"]

    scales = []
    for dim in ocr_dims:
        val = dim.get('value_cm', dim.get('value', 0))
        if val > 0:
            tag = dim.get('tag', '')
            if any(t in tag for t in ['w', 'width', 'dia', 'diameter']):
                scales.append(val / pixel_width)

    if not scales:
        # Use first dimension as fallback
        val = ocr_dims[0].get('value_cm', ocr_dims[0].get('value', 0))
        if val > 0:
            scales.append(val / pixel_width)

    if not scales:
        return 0.1, 0.0, ["No valid scale dimensions found"]

    scale = sum(scales) / len(scales)
    consistency = 1.0 - (max(scales) - min(scales)) / max(scales) if len(scales) > 1 else 0.8
    confidence = min(consistency, 0.95)

    if consistency < 0.5:
        warnings.append(f"Scale inconsistency: scales range {min(scales):.4f}-{max(scales):.4f}")

    return scale, confidence, warnings
