from __future__ import annotations
from .models import OCRDimension, DetectedLine, DetectedCircle, DimensionAssociation
from .geometry_utils import bbox_center, point_to_line_distance, distance

def associate_dimensions(
    dimensions: list[OCRDimension],
    lines: list[DetectedLine],
    circles: list[DetectedCircle],
    max_distance: float = 140,
) -> list[DimensionAssociation]:
    associations: list[DimensionAssociation] = []
    for dim in dimensions:
        center = bbox_center(dim.bbox)
        candidates: list[tuple[float, str, str, float, str]] = []

        if dim.kind in ["diameter", "radius"]:
            for c in circles:
                d = distance(center, c.center)
                measured = c.radius_px * 2 if dim.kind == "diameter" else c.radius_px
                score = max(0.0, 1.0 - d / max_distance) + 0.25
                candidates.append((score, c.id, "circle", measured, f"{dim.kind} text near circle"))

        for line in lines:
            d = point_to_line_distance(center, line.start, line.end)
            role_bonus = 0.28 if line.role == "dimension_line" else 0.12 if line.role == "object_line" else -0.05 if line.role == "leader_line" else 0
            score = max(0.0, 1.0 - d / max_distance) + role_bonus
            if dim.kind == "diameter" and line.role == "dimension_line":
                score += 0.10
            candidates.append((score, line.id, "line", line.length_px, f"near {line.role}, distance={d:.1f}px"))

        candidates.sort(key=lambda x: x[0], reverse=True)
        if not candidates or candidates[0][0] <= 0.2:
            associations.append(DimensionAssociation(dim, None, None, None, 0.0, "No reliable geometry target found"))
            continue

        score, target_id, target_type, measured_px, reason = candidates[0]
        associations.append(DimensionAssociation(
            dimension=dim,
            target_id=target_id,
            target_type=target_type,
            measured_px=measured_px,
            confidence=min(score, 1.0) * dim.confidence,
            reason=reason,
        ))
    return associations
