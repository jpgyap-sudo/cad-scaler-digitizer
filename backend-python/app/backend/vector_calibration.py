"""
Vector Output Calibration & Validation Pipeline.
Ensures DXF coordinates map 1:1 to physical dimensions for CNC/laser readiness.
"""
import math
from typing import List, Tuple


def calibrate_coordinates(lines: List[Tuple], circles: List[Tuple],
                           ocr_dims: List[dict]) -> dict:
    """
    Validate that DXF coordinates match the OCR dimension claims.
    If dimension says 80cm, the actual coordinate distance must be 80 units.
    Returns calibration with scale correction factor.
    """
    result = {
        'correction_factor': 1.0,
        'warnings': [],
        'is_calibrated': True,
    }

    if not ocr_dims or (not lines and not circles):
        return result

    # Build pixel measurements from geometry
    pixel_measurements = {}
    if circles:
        max_r = max(c[2] for c in circles)
        pixel_measurements['diameter'] = max_r * 2
    if lines:
        xs = [p[0] for pair in lines for p in pair]
        ys = [p[1] for pair in lines for p in pair]
        if xs:
            pixel_measurements['width'] = max(xs) - min(xs)
            pixel_measurements['height'] = max(ys) - min(ys)

    # Compare each OCR dimension against pixel measurements
    scales = []
    for dim in ocr_dims:
        tag = dim.get('tag', '')
        value = dim.get('value_cm', 0)
        if value <= 0:
            continue

        # Find matching pixel measurement
        pixel_val = None
        if any(t in tag for t in ['dia', 'diameter', 'width', 'w']):
            pixel_val = pixel_measurements.get('diameter') or pixel_measurements.get('width')
        elif any(t in tag for t in ['height', 'h']):
            pixel_val = pixel_measurements.get('height')

        if pixel_val and pixel_val > 0:
            scale = value / pixel_val
            scales.append((scale, tag, value, pixel_val))

    # If there's a systematic scale offset, compute correction
    if scales and len(scales) >= 2:
        avg_scale = sum(s[0] for s in scales) / len(scales)
        variations = [abs(s[0] - avg_scale) / avg_scale for s in scales]
        max_variation = max(variations)

        if max_variation > 0.05:
            result['warnings'].append(
                f"Scale inconsistency: {max_variation*100:.1f}% variation across dimensions")
            result['is_calibrated'] = False

        result['correction_factor'] = avg_scale

    # Log the calibration
    for scale, tag, value, px in scales:
        result['warnings'].append(f"Calibrated: {tag}={value}cm → {px:.1f}px (scale={scale:.4f})")

    return result


def snap_to_mm(value: float) -> float:
    """Snap a coordinate value to the nearest millimeter (0.1 cm)."""
    return round(value, 1)


def enforce_1_to_1_scale(lines: List[Tuple], circles: List[Tuple], scale: float) -> tuple:
    """
    Apply correction factor to make geometry match 1:1 physical scale.
    If scale was 0.5 (2 pixels = 1 cm), multiply all coordinates by 2.
    """
    if abs(scale - 1.0) < 0.001:
        return lines, circles

    corrected_lines = []
    for (x1, y1), (x2, y2) in lines:
        corrected_lines.append((
            (snap_to_mm(x1 / scale), snap_to_mm(y1 / scale)),
            (snap_to_mm(x2 / scale), snap_to_mm(y2 / scale)),
        ))

    corrected_circles = []
    for x, y, r in circles:
        corrected_circles.append((
            snap_to_mm(x / scale),
            snap_to_mm(y / scale),
            snap_to_mm(r / scale),
        ))

    return corrected_lines, corrected_circles


def build_pipeline_report(lines_count: int, circles_count: int,
                          ocr_dims: list, scale: float, warnings: list) -> dict:
    """Build a structured report for the calibration pipeline."""
    return {
        'pipeline': 'vector_calibration_v1',
        'input_lines': lines_count,
        'input_circles': circles_count,
        'ocr_dimensions': len(ocr_dims),
        'applied_scale': f'{scale:.4f}',
        'is_1_to_1': abs(scale - 1.0) < 0.001,
        'warnings': warnings,
    }
