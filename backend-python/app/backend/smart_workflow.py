"""
Smart Auto Workflow for CAD Scaler Digitizer.

Goal:
- Hide OpenCV/Hybrid/AI/Pipeline from the user.
- Always run one excellent workflow.
- Ask confirmation questions only when confidence is low or when the answer changes DXF output.

Use from routes.py after detection/classification/dimension extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

KNOWN_TYPES = {
    "round_pedestal_table",
    "rectangular_table",
    "cabinet",
    "sofa",
    "coffee_table",
    "dining_chair",
    "chair",
    "wardrobe",
    "reception_counter",
    "bed_headboard",
    "generic_2d_furniture",
}


@dataclass
class ConfirmationQuestion:
    id: str
    type: str
    severity: str
    title: str
    message: str
    options: List[Dict[str, Any]]
    default_value: Optional[Any] = None
    required: bool = True
    affects_dxf: bool = True


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def dimension_confidence(dimensions: List[Dict[str, Any]]) -> float:
    if not dimensions:
        return 0.0
    scores = []
    for dim in dimensions:
        val = _safe_float(dim.get("value_cm"), 0)
        conf = _safe_float(dim.get("confidence"), 0.55)
        if val <= 0:
            conf *= 0.25
        raw = str(dim.get("raw") or dim.get("tag") or "").lower()
        if any(x in raw for x in ["?", "approx", "guess"]):
            conf *= 0.6
        scores.append(max(0.0, min(1.0, conf)))
    return sum(scores) / max(len(scores), 1)


def infer_scale_confidence(
    dimensions: List[Dict[str, Any]],
    lines_count: int,
    real_width_cm: Optional[float],
    real_height_cm: Optional[float],
) -> float:
    if real_width_cm or real_height_cm:
        return 0.95
    if not dimensions:
        return 0.1
    dim_conf = dimension_confidence(dimensions)
    geometry_bonus = 0.15 if lines_count >= 4 else 0.0
    return max(0.0, min(1.0, dim_conf + geometry_bonus))


def choose_internal_route(
    *,
    has_openai_key: bool,
    furniture_confidence: float,
    scale_confidence: float,
    dimensions_count: int,
    lines_count: int,
) -> Dict[str, Any]:
    """Internal routing, not exposed in UI."""
    reasons: List[str] = []

    if not has_openai_key:
        reasons.append("OPENAI_API_KEY missing, using deterministic OpenCV/OCR route")
        return {"route": "opencv", "use_ai": False, "reasons": reasons}

    if furniture_confidence < 0.72:
        reasons.append("furniture confidence below 0.72, AI verification needed")
        return {"route": "hybrid", "use_ai": True, "reasons": reasons}

    if scale_confidence < 0.70:
        reasons.append("scale confidence below 0.70, AI + user confirmation needed")
        return {"route": "hybrid", "use_ai": True, "reasons": reasons}

    if dimensions_count == 0 and lines_count >= 3:
        reasons.append("geometry found but no dimensions, AI OCR fallback needed")
        return {"route": "hybrid", "use_ai": True, "reasons": reasons}

    reasons.append("OpenCV/OCR confidence sufficient, AI not required")
    return {"route": "opencv", "use_ai": False, "reasons": reasons}


def build_confirmation_questions(
    *,
    furniture_type: str,
    furniture_confidence: float,
    dimensions: List[Dict[str, Any]],
    scale_confidence: float,
    real_width_cm: Optional[float],
    real_height_cm: Optional[float],
    ocr_lines: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    questions: List[ConfirmationQuestion] = []
    ftype = furniture_type or "generic_2d_furniture"

    # 1. Scale anchor is the most important question.
    if scale_confidence < 0.70 and not (real_width_cm or real_height_cm):
        questions.append(ConfirmationQuestion(
            id="scale_anchor",
            type="scale_anchor",
            severity="critical",
            title="Confirm one known size",
            message="I could not confidently lock the drawing scale. Click or choose one known length and enter the real size in cm.",
            options=[
                {"label": "Set width / diameter", "value": "real_width_cm"},
                {"label": "Set height", "value": "real_height_cm"},
                {"label": "Continue as estimate", "value": "estimate"},
            ],
            default_value="real_width_cm",
        ))

    # 2. Furniture type only matters when it changes template/DXF output.
    if furniture_confidence < 0.72 or ftype not in KNOWN_TYPES or ftype == "generic_2d_furniture":
        questions.append(ConfirmationQuestion(
            id="furniture_type",
            type="single_choice",
            severity="high",
            title="Confirm furniture type",
            message=f"I think this is {ftype.replace('_', ' ')} but confidence is only {round(furniture_confidence * 100)}%.",
            options=[
                {"label": "Round pedestal table", "value": "round_pedestal_table"},
                {"label": "Rectangular table", "value": "rectangular_table"},
                {"label": "Coffee table", "value": "coffee_table"},
                {"label": "Cabinet / wardrobe", "value": "cabinet"},
                {"label": "Sofa", "value": "sofa"},
                {"label": "Chair", "value": "chair"},
                {"label": "Bed / headboard", "value": "bed_headboard"},
                {"label": "Generic 2D trace", "value": "generic_2d_furniture"},
            ],
            default_value=ftype if ftype in KNOWN_TYPES else "generic_2d_furniture",
        ))

    # 3. Dimension conflicts / weak OCR.
    weak_dims = []
    for d in dimensions:
        conf = _safe_float(d.get("confidence"), 0.55)
        val = _safe_float(d.get("value_cm"), 0)
        if conf < 0.60 or val <= 0:
            weak_dims.append(d)

    if weak_dims:
        options = []
        for i, d in enumerate(weak_dims[:5]):
            label = str(d.get("raw") or d.get("tag") or f"dimension {i + 1}")
            options.append({"label": f"Correct: {label}", "value": label})
        questions.append(ConfirmationQuestion(
            id="weak_dimensions",
            type="dimension_review",
            severity="medium",
            title="Review weak dimensions",
            message="Some OCR dimensions are low confidence. Correct only the values that affect the final DXF.",
            options=options,
            required=False,
        ))

    return [asdict(q) for q in questions[:3]]


def build_smart_metadata(
    *,
    has_openai_key: bool,
    furniture_type: str,
    furniture_confidence: float,
    dimensions: List[Dict[str, Any]],
    lines_count: int,
    real_width_cm: Optional[float],
    real_height_cm: Optional[float],
    ocr_lines: Optional[List[str]] = None,
) -> Dict[str, Any]:
    scale_conf = infer_scale_confidence(dimensions, lines_count, real_width_cm, real_height_cm)
    route = choose_internal_route(
        has_openai_key=has_openai_key,
        furniture_confidence=furniture_confidence,
        scale_confidence=scale_conf,
        dimensions_count=len(dimensions),
        lines_count=lines_count,
    )
    questions = build_confirmation_questions(
        furniture_type=furniture_type,
        furniture_confidence=furniture_confidence,
        dimensions=dimensions,
        scale_confidence=scale_conf,
        real_width_cm=real_width_cm,
        real_height_cm=real_height_cm,
        ocr_lines=ocr_lines,
    )
    return {
        "workflow": "smart_auto",
        "internal_route": route["route"],
        "ai_used_or_recommended": bool(route["use_ai"]),
        "route_reasons": route["reasons"],
        "confidence": {
            "furniture": round(float(furniture_confidence or 0), 3),
            "dimensions": round(dimension_confidence(dimensions), 3),
            "scale": round(scale_conf, 3),
        },
        "needs_confirmation": len(questions) > 0,
        "confirmation_questions": questions,
    }
