from __future__ import annotations
from .models import PipelineResult
from .ocr_dimension_parser import parse_ocr_dimensions
from .line_detector import detect_lines, detect_circles
from .line_role_classifier import classify_line_roles
from .dimension_associator import associate_dimensions
from .scale_solver import solve_scale
from .geometry_reconstructor import reconstruct_entities
from .entity_confidence import apply_dimension_evidence, confidence_summary

def run_cad_intelligence_pipeline(image_path: str, ocr_items: list[dict], default_unit: str = "mm") -> PipelineResult:
    dimensions = parse_ocr_dimensions(ocr_items, default_unit=default_unit)
    lines = detect_lines(image_path)
    circles = detect_circles(image_path)
    lines = classify_line_roles(lines, dimensions)
    associations = associate_dimensions(dimensions, lines, circles)
    scale = solve_scale(associations)
    entities = reconstruct_entities(lines, circles, scale)
    entities = apply_dimension_evidence(entities, associations)
    debug = {
        "confidence_summary": confidence_summary(entities),
        "line_count": len(lines),
        "circle_count": len(circles),
        "dimension_count": len(dimensions),
        "association_count": len(associations),
    }
    return PipelineResult(
        dimensions=dimensions,
        lines=lines,
        circles=circles,
        associations=associations,
        scale=scale,
        entities=entities,
        debug=debug,
    )
