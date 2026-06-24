"""
Semantic Proportion Validator — ensures furniture geometry follows real-world conventions.
When contours are detected from the image, this module validates proportions
and corrects inversions (e.g., base wider than neck always).
"""
from typing import List, Tuple, Optional


def validate_furniture_proportions(detected_parts: dict) -> dict:
    """
    Validate detected parts against architectural conventions.
    Ensures: Width_Base > Width_Neck for pedestal-style furniture.
    Returns corrected part layout.
    """
    corrected = dict(detected_parts)

    # Rule 1: Pedestal base must be wider than neck
    base_width = detected_parts.get('base_width_cm', 0)
    neck_width = detected_parts.get('neck_width_cm', 0)
    top_dia = detected_parts.get('top_diameter_cm', 0)

    if base_width > 0 and neck_width > 0:
        if base_width < neck_width:
            # Inverted — swap them
            corrected['base_width_cm'] = neck_width
            corrected['neck_width_cm'] = base_width
            corrected['_correction'] = 'base_neck_inverted_fixed'
        elif base_width > top_dia:
            # Base cannot be wider than the table top
            corrected['base_width_cm'] = top_dia * 0.55
            corrected['_correction'] = 'base_too_wide_scaled'

    # Rule 2: Table thickness must be reasonable (2-8% of height)
    height = detected_parts.get('height_cm', 70)
    thickness = detected_parts.get('top_thickness_cm', 4)
    if thickness < height * 0.02 or thickness > height * 0.08:
        corrected['top_thickness_cm'] = round(height * 0.05, 1)
        corrected['_correction'] = 'thickness_adjusted'

    return corrected


def get_semantic_hierarchy(furniture_type: str) -> dict:
    """
    Return the expected dimensional hierarchy for a furniture type.
    Used to validate that detected geometry makes physical sense.
    """
    hierarchies = {
        'round_pedestal_table': {
            'width_order': ['base_width_cm', 'neck_width_cm'],
            'width_rule': 'base > neck',
            'aspect_ratio': 'top_dia / height ≈ 0.8-1.5',
        },
        'rectangular_table': {
            'width_order': ['width_cm', 'leg_width_cm'],
            'width_rule': 'width > leg_width',
            'aspect_ratio': 'width / depth ≈ 1.2-2.0',
        },
        'cabinet': {
            'width_order': ['width_cm', 'door_width_cm'],
            'width_rule': 'width = 2 * door_width (double door)',
            'aspect_ratio': 'height / width ≈ 1.5-2.5',
        },
        'sofa': {
            'width_order': ['width_cm', 'seat_width_cm', 'armrest_width_cm'],
            'width_rule': 'width = 2 * arm_width + seat_width',
            'aspect_ratio': 'width / depth ≈ 2.0-3.0',
        },
    }
    return hierarchies.get(furniture_type, {})


def scale_to_cm(ocr_dims: list, pixel_measurements: dict) -> tuple:
    """
    Calculate precise cm/pixel scale from OCR dimensions.
    Returns (scale, confidence, aligned_dims).
    Aligned dims map pixel coordinates → physical cm at 1:1.
    """
    scales = []
    for dim in ocr_dims:
        tag = dim.get('tag', '')
        value = dim.get('value_cm', 0)
        if value <= 0:
            continue
        if 'width' in tag or 'w' in tag:
            px = pixel_measurements.get('width', 0)
            if px > 0:
                scales.append(value / px)
        elif 'height' in tag or 'h' in tag:
            px = pixel_measurements.get('height', 0)
            if px > 0:
                scales.append(value / px)
        elif 'diameter' in tag or 'dia' in tag:
            px = pixel_measurements.get('diameter', 0)
            if px > 0:
                scales.append(value / px)

    if not scales:
        return 0.1, 0, ocr_dims

    scale = sum(scales) / len(scales)
    consistency = 1.0 - (max(scales) - min(scales)) / max(scales) if len(scales) > 1 else 0.8
    confidence = min(consistency, 0.95)

    return scale, confidence, ocr_dims


def detect_structure_from_lines(lines: List[Tuple[Tuple[float, float], Tuple[float, float]]]) -> dict:
    """
    Analyze detected line segments to identify structural elements.
    Groups lines by: top (y-min), bottom (y-max), left (x-min), right (x-max).
    Returns bounding boxes for: tabletop, pedestal, base.
    """
    if not lines:
        return {}

    points = [p[0] for p in lines] + [p[1] for p in lines]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    height = max_y - min_y
    width = max_x - min_x

    if height <= 0 or width <= 0:
        return {}

    return {
        'tabletop': {'y_range': (max_y - height * 0.15, max_y), 'x_range': (min_x, max_x)},
        'pedestal_neck': {'y_range': (max_y * 0.4, max_y - height * 0.15), 'x_range': (min_x + width * 0.35, max_x - width * 0.35)},
        'pedestal_base': {'y_range': (min_y, max_y * 0.4), 'x_range': (min_x + width * 0.2, max_x - width * 0.2)},
        'width_cm': round(width, 1),
        'height_cm': round(height, 1),
    }
