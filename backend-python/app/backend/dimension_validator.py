"""
Module: dimension_validator.py
Cross-validate OCR dimensions against OpenCV geometry measurements.
"""
import math
from typing import List, Optional

# pixel_measurements is keyed by canonical name ('diameter'/'width'/'height'),
# but OCR tags vary ('dia', 'top_dia', 'w', 'h', ...) - without this alias map
# the lookup below misses every non-canonical tag and the cross-check never
# fires, silently letting OCR misreads (e.g. "80" read as "60") through.
_TAG_ALIASES = {
    'dia': 'diameter', 'diameter': 'diameter', 'top_dia': 'diameter',
    'w': 'width', 'width': 'width',
    'h': 'height', 'height': 'height',
}


def autocorrect_dimensions(ocr_dims: list, pixel_measurements: dict, tolerance: float = 0.15,
                            scale_cm_per_pixel: Optional[float] = None) -> list:
    """Cross-check OCR'd dimensions against OpenCV-measured pixel geometry.

    pixel_measurements values are in raw pixels; scale_cm_per_pixel converts
    them to cm before comparing against value_cm. Without a scale, pixels
    and centimeters were being compared directly, which is a meaningless
    comparison for any real (non-synthetic) photo.
    """
    corrected = []
    for dim in ocr_dims:
        tag = dim.get('tag', '')
        canonical = _TAG_ALIASES.get(tag.lower().strip())
        value = dim.get('value_cm', dim.get('value', 0))
        pixel_val = pixel_measurements.get(canonical) if canonical else None
        if pixel_val is not None and value > 0 and scale_cm_per_pixel:
            pixel_val_cm = pixel_val * scale_cm_per_pixel
            diff = abs(value - pixel_val_cm) / value
            if diff < tolerance:
                corrected.append({**dim, 'value_cm': round(value, 1), 'autocorrected': True})
            else:
                corrected.append({**dim, 'warning':
                    f'OCR reads {value:g}cm but measured geometry suggests ~{pixel_val_cm:.0f}cm - please verify'})
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


# Typical ratio bands observed across round pedestal tables (collar/neck/base
# as a fraction of top diameter). Values outside these bands usually mean a
# component's dimension was read/extracted independently of the others and
# never cross-checked against them - e.g. top misread as 60cm while a
# correctly-read collar of 50cm slips through unflagged.
_PEDESTAL_RATIO_BANDS = {
    'collar_diameter_cm': (0.35, 0.85),
    'pedestal_diameter_cm': (0.30, 0.75),
    'base_diameter_cm': (0.30, 0.75),
    'neck_diameter_cm': (0.15, 0.45),
}


def check_round_pedestal_proportions(top_dia_cm: float, components: dict) -> list:
    """Sanity-check that collar/base/neck diameters are plausible relative to
    the top diameter and to each other for a round pedestal table.
    Returns a list of human-readable warning strings (empty if all sane).
    """
    warnings = []
    if not top_dia_cm or top_dia_cm <= 0:
        return warnings

    for key, (lo, hi) in _PEDESTAL_RATIO_BANDS.items():
        val = components.get(key)
        if val is None:
            continue
        ratio = val / top_dia_cm
        if not (lo <= ratio <= hi):
            warnings.append(
                f"{key.replace('_', ' ')} ({val:g}cm) is {ratio:.0%} of the top diameter "
                f"({top_dia_cm:g}cm) - expected {lo:.0%}-{hi:.0%}, please verify"
            )

    collar = components.get('collar_diameter_cm')
    neck = components.get('neck_diameter_cm')
    base = components.get('base_diameter_cm') or components.get('pedestal_diameter_cm')
    if collar is not None and neck is not None and neck >= collar:
        warnings.append(f"neck diameter ({neck:g}cm) should be smaller than collar diameter ({collar:g}cm)")
    if collar is not None and collar >= top_dia_cm:
        warnings.append(f"collar diameter ({collar:g}cm) should be smaller than top diameter ({top_dia_cm:g}cm)")
    if base is not None and neck is not None and neck >= base:
        warnings.append(f"neck diameter ({neck:g}cm) should be smaller than base diameter ({base:g}cm)")

    return warnings
