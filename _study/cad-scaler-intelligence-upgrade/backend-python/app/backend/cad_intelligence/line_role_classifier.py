from __future__ import annotations
from .models import DetectedLine, OCRDimension
from .geometry_utils import bbox_distance_to_line, is_horizontal, is_vertical

def classify_line_roles(lines: list[DetectedLine], dimensions: list[OCRDimension]) -> list[DetectedLine]:
    for line in lines:
        nearest_dim_distance = None
        for dim in dimensions:
            d = bbox_distance_to_line(dim.bbox, line.start, line.end)
            if nearest_dim_distance is None or d < nearest_dim_distance:
                nearest_dim_distance = d

        near_text = nearest_dim_distance is not None and nearest_dim_distance < 45

        if near_text and line.length_px > 25:
            if is_horizontal(line.angle_deg, tolerance=12) or is_vertical(line.angle_deg, tolerance=12):
                line.role = "dimension_line"
                line.confidence = max(line.confidence, 0.72)
                line.metadata["role_reason"] = f"near dimension text, distance={nearest_dim_distance:.1f}px"
            else:
                line.role = "leader_line"
                line.confidence = max(line.confidence, 0.68)
                line.metadata["role_reason"] = f"angled line near dimension/note, distance={nearest_dim_distance:.1f}px"
        elif line.length_px < 30 and not (is_horizontal(line.angle_deg) or is_vertical(line.angle_deg)):
            line.role = "hatch"
            line.confidence = max(line.confidence, 0.45)
            line.metadata["role_reason"] = "short angled line"
        elif line.length_px > 45:
            line.role = "object_line"
            line.confidence = max(line.confidence, 0.58)
            line.metadata["role_reason"] = "long line away from text"
        else:
            line.role = "unknown"
            line.confidence = max(line.confidence, 0.3)
            line.metadata["role_reason"] = "insufficient evidence"
    return lines
