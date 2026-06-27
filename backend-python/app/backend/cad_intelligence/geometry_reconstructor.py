from __future__ import annotations
import uuid
from .models import DetectedLine, DetectedCircle, CadEntity, ScaleSolution

def px_to_mm_point(point, scale: ScaleSolution):
    if not scale.mm_per_px:
        return point
    return (point[0] * scale.mm_per_px, point[1] * scale.mm_per_px)

def reconstruct_entities(lines: list[DetectedLine], circles: list[DetectedCircle], scale: ScaleSolution) -> list[CadEntity]:
    entities: list[CadEntity] = []

    for line in lines:
        if line.role in ["hatch", "leader_line"]:
            layer = "ANNOTATION"
            confidence = min(line.confidence, 0.55)
        elif line.role == "dimension_line":
            layer = "DIMENSIONS"
            confidence = min(line.confidence, 0.65)
        elif line.role == "object_line":
            layer = "OBJECT"
            confidence = line.confidence
        else:
            layer = "UNKNOWN"
            confidence = min(line.confidence, 0.35)

        entities.append(CadEntity(
            id=f"entity_{uuid.uuid4().hex[:8]}",
            type="line",
            geometry={
                "start": px_to_mm_point(line.start, scale),
                "end": px_to_mm_point(line.end, scale),
                "length_px": line.length_px,
                "angle_deg": line.angle_deg,
            },
            source="pixel_detected",
            confidence=confidence,
            evidence=[line.id],
            layer=layer,
            metadata={"line_role": line.role, **line.metadata},
        ))

    for circle in circles:
        radius = circle.radius_px * scale.mm_per_px if scale.mm_per_px else circle.radius_px
        entities.append(CadEntity(
            id=f"entity_{uuid.uuid4().hex[:8]}",
            type="circle",
            geometry={
                "center": px_to_mm_point(circle.center, scale),
                "radius": radius,
                "radius_px": circle.radius_px,
            },
            source="pixel_detected",
            confidence=circle.confidence,
            evidence=[circle.id],
            layer="OBJECT",
            metadata=circle.metadata,
        ))

    return entities
