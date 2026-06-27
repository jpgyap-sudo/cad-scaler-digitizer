"""
UNIFIED INTELLIGENCE ROUTER — The "genius" endpoint.

Merges 3 parallel analysis tracks into one confidence-weighted result:

  Track A — AI Vision (GPT-4o / Gemini)
    "What type of furniture is this? What materials?"
    Source: CloudVisionFeatureSet from cloud_vision.py
    Weight: High for type/material, Low for precise dimensions

  Track B — OpenCV + OCR + cad_intelligence
    "What geometry can I detect? What dimension text exists?"
    Source: OpenCV lines/circles + OCR text + cad_intelligence pipeline
    Weight: High for geometry, Medium for dimensions

  Track C — Template Graph System
    "What does a standard version of this look like?"
    Source: TemplateGraphLoader + TemplateResolver
    Weight: Fallback — used when A and B disagree or are uncertain

The fusion algorithm:
  1. Run ALL 3 tracks in parallel (or gracefully degrade)
  2. For each output field (type, width, height, material, etc.):
     - Collect all sources that provided a value + their confidence
  3. Weighted blend:
     - AI Vision: weight = confidence * 0.7 (type/material expert)
     - pixel geometry: weight = confidence * 0.5 (geometry expert)
     - OCR dimensions: weight = confidence * 0.9 (precision expert)
     - Template default: weight = 0.2 (background knowledge)
  4. Return blended result with per-field provenance tracking

This gives the user ONE endpoint that works for:
  - Photos (no geometry) → AI Vision heavy
  - CAD drawings (text + lines) → OCR + geometry heavy
  - Unknown objects → template with clear "default" labels
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import PipelineResult, CadEntity
from .pipeline import run_cad_intelligence_pipeline
from .export_debug import pipeline_result_to_dict
from .reference_ratio_solver import solve_missing_dimensions
from ..vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles, normalize_lines
from ..ocr import ocr_dimensions
from ..geometry_cleanup import process_constraints
from ..furniture_classifier import classify_furniture, normalize_furniture_type

# --- Data classes for provenance tracking ---

class ProvenanceValue:
    """A single field value with source tracking."""
    def __init__(self, value: Any, source: str, confidence: float, note: str = ""):
        self.value = value
        self.source = source  # "ai_vision" | "ocr" | "pixel_geometry" | "cad_intelligence" | "template_default" | "user"
        self.confidence = confidence
        self.note = note

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "confidence": round(self.confidence, 3),
            "note": self.note,
        }


class UnifiedResult:
    """Complete unified pipeline result with provenance."""
    def __init__(self):
        self.product_type: Optional[ProvenanceValue] = None
        self.top_shape: Optional[ProvenanceValue] = None
        self.support_type: Optional[ProvenanceValue] = None
        self.material_top: Optional[ProvenanceValue] = None
        self.material_base: Optional[ProvenanceValue] = None
        self.dimensions: Dict[str, ProvenanceValue] = {}
        self.entities: List[CadEntity] = []
        self.entity_count: int = 0
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.template_graph: Optional[Dict[str, Any]] = None
        self.cad_intel_result: Optional[Dict[str, Any]] = None
        self.ai_analysis: Optional[Dict[str, Any]] = None

    def to_api_dict(self) -> Dict[str, Any]:
        result = {
            "product_type": self.product_type.to_dict() if self.product_type else None,
            "top_shape": self.top_shape.to_dict() if self.top_shape else None,
            "support_type": self.support_type.to_dict() if self.support_type else None,
            "material_top": self.material_top.to_dict() if self.material_top else None,
            "material_base": self.material_base.to_dict() if self.material_base else None,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "entity_count": self.entity_count,
            "warnings": self.warnings,
            "errors": self.errors,
        }
        if self.template_graph:
            result["template"] = {
                "template_id": self.template_graph.get("template", {}).get("id"),
                "template_name": self.template_graph.get("template", {}).get("name"),
                "resolved_parameters_mm": self.template_graph.get("resolved_parameters"),
                "required_views": self.template_graph.get("component_views"),
                "required_details": self.template_graph.get("required_details"),
                "drawing_notes": self.template_graph.get("drawing_notes"),
            }
        return result


# --- Blending weights ---
WEIGHT_AI_VISION = 0.7
WEIGHT_OCR = 0.9
WEIGHT_PIXEL_GEOMETRY = 0.5
WEIGHT_CAD_INTEL = 0.6
WEIGHT_TEMPLATE = 0.2
WEIGHT_USER = 1.0


def _blend(values: List[Tuple[Any, float]]) -> Tuple[Any, float]:
    """Weighted average of (value, weight) pairs. Values should be numeric."""
    total_w = sum(w for _, w in values if w > 0)
    if total_w == 0:
        return (None, 0.0)
    blended = sum(v * w for v, w in values if w > 0) / total_w
    avg_weight = total_w / len(values)
    return (blended, min(avg_weight, 1.0))


def run_unified_pipeline(
    image_path: str,
    furniture_type_override: Optional[str] = None,
    user_dimensions_cm: Optional[Dict[str, float]] = None,
    ai_vision_result: Optional[Dict[str, Any]] = None,
    default_unit: str = "mm",
) -> UnifiedResult:
    """Run the unified intelligence pipeline.

    Args:
        image_path: Path to the uploaded image (photo or technical drawing)
        furniture_type_override: Optional — user says "this is a round table"
        user_dimensions_cm: Optional — user provides "80cm diameter"
        ai_vision_result: Optional — pre-computed AI vision result
        default_unit: Unit for OCR dimension parsing

    Returns:
        UnifiedResult with provenance-tracked fields
    """
    result = UnifiedResult()

    # ===== PHASE 1: Run ALL detection tracks in parallel =====

    # Track A: AI Vision (if available)
    ai_type = None
    ai_conf = 0.0
    ai_dimensions: Dict[str, float] = {}
    ai_materials: Dict[str, str] = {}

    if ai_vision_result:
        result.ai_analysis = ai_vision_result
        ai_type = normalize_furniture_type(ai_vision_result.get("product_type", ""))
        ai_conf = float(ai_vision_result.get("confidence", 0) or 0)
        approx = ai_vision_result.get("approximate_dimensions_mm", {}) or {}
        if approx.get("length_mm"):
            ai_dimensions["length_cm"] = approx["length_mm"] / 10.0
        if approx.get("depth_mm"):
            ai_dimensions["depth_cm"] = approx["depth_mm"] / 10.0
        if approx.get("height_mm"):
            ai_dimensions["overall_height_cm"] = approx["height_mm"] / 10.0
        if ai_vision_result.get("material_top"):
            ai_materials["top"] = ai_vision_result["material_top"]
        if ai_vision_result.get("material_base"):
            ai_materials["base"] = ai_vision_result["material_base"]

    # Track B: OpenCV + OCR + cad_intelligence
    try:
        img, gray = load_image(image_path)
        binary = preprocess(gray)
        lines_raw = detect_lines(binary)
        lines = normalize_lines(lines_raw)
        circles = detect_circles(gray)
        rects = detect_rectangles(binary)
        ocr_texts, ocr_dims = ocr_dimensions(image_path)

        # Build OCR items for cad_intelligence pipeline
        ocr_items = [{"text": t, "bbox": [0, 0, 0, 0], "confidence": 0.8} for t in ocr_texts[:50]]
        
        # Run cad_intelligence pipeline
        ci = run_cad_intelligence_pipeline(
            image_path=image_path,
            ocr_items=ocr_items,
            default_unit=default_unit,
        )
        result.cad_intel_result = pipeline_result_to_dict(ci)
        result.entities = ci.entities
        result.entity_count = len(ci.entities)

        # Extract OCR dimensions
        ocr_dimensions_cm: Dict[str, float] = {}
        for dim in ci.dimensions:
            val_cm = dim.value_mm / 10.0 if dim.unit == "mm" else dim.value
            key = f"{dim.kind}_{dim.raw_text[:8]}"
            ocr_dimensions_cm[key] = val_cm

        # OpenCV classifier
        opencv_classifier = classify_furniture(ocr_texts, circles, lines, rects)
        opencv_type = normalize_furniture_type(opencv_classifier.get("type", ""))
        opencv_conf = opencv_classifier.get("confidence", 0.3)

    except Exception as e:
        result.errors.append(f"Track B (OpenCV/OCR) failed: {e}")
        lines, circles, rects = [], [], []
        ocr_texts, ocr_dims = [], []
        opencv_type, opencv_conf = "", 0.0
        ci = None

    # ===== PHASE 2: Fuse Product Type =====

    # Priority: user override > AI vision > OpenCV classifier > "unknown"
    if furniture_type_override:
        result.product_type = ProvenanceValue(
            normalize_furniture_type(furniture_type_override),
            "user", 1.0, "User-specified furniture type"
        )
    elif ai_type and ai_conf >= 0.5:
        result.product_type = ProvenanceValue(
            ai_type, "ai_vision", ai_conf,
            f"AI Vision classified as {ai_type}"
        )
    elif opencv_type and opencv_conf > 0.3:
        result.product_type = ProvenanceValue(
            opencv_type, "pixel_geometry", opencv_conf,
            f"OpenCV geometry classified as {opencv_type}"
        )
    else:
        result.product_type = ProvenanceValue(
            "unknown", "template_default", 0.1,
            "Could not determine furniture type — please specify"
        )

    ftype = result.product_type.value

    # ===== PHASE 3: Fuse Dimensions =====

    # Collect all dimension sources
    all_dim_sources: Dict[str, List[Tuple[float, float, str, str]]] = {}
    # (dim_key: [(value_cm, weight, source, note)])

    # Source 1: User-provided dimensions (highest priority)
    if user_dimensions_cm:
        for k, v in user_dimensions_cm.items():
            if v > 0:
                all_dim_sources.setdefault(k, []).append((v, WEIGHT_USER, "user", "Provided by user"))

    # Source 2: AI Vision approximate dimensions
    for k, v in ai_dimensions.items():
        if v > 0:
            all_dim_sources.setdefault(k, []).append((v, WEIGHT_AI_VISION * ai_conf, "ai_vision", "Estimated by AI Vision"))

    # Source 3: OCR parsed dimensions
    if ci:
        for d in ci.dimensions:
            val_cm = d.value_mm / 10.0
            key = d.kind  # "diameter", "width", "height", "length"
            all_dim_sources.setdefault(key, []).append((val_cm, WEIGHT_OCR * d.confidence, "ocr", f"OCR: '{d.raw_text}'"))

    # Source 4: Reference ratios (fill in missing from known)
    known_for_ratios = {}
    for sources in all_dim_sources.values():
        best = max(sources, key=lambda s: s[1])
        known_for_ratios[best[3].split(":")[0].strip()] = best[0]

    if ftype != "unknown" and known_for_ratios:
        try:
            solved = solve_missing_dimensions(ftype, known_for_ratios)
            for k, v in solved.items():
                if k not in all_dim_sources and v > 0:
                    all_dim_sources.setdefault(k, []).append((v, WEIGHT_TEMPLATE, "reference_ratio", f"Estimated from {ftype} proportions"))
        except Exception:
            pass

    # Blend per dimension
    for dim_key, sources in all_dim_sources.items():
        blended_val, blended_conf = _blend([(v, w) for v, w, _, _ in sources])
        best_source = max(sources, key=lambda s: s[1])
        result.dimensions[dim_key] = ProvenanceValue(
            round(blended_val, 1),
            best_source[2],
            blended_conf,
            f"Blended from {len(sources)} source(s). Best: {best_source[3]}"
        )

    # ===== PHASE 4: Materials =====

    if ai_materials.get("top"):
        result.material_top = ProvenanceValue(
            ai_materials["top"], "ai_vision", ai_conf * 0.8, "AI Vision detected material"
        )
    if ai_materials.get("base"):
        result.material_base = ProvenanceValue(
            ai_materials["base"], "ai_vision", ai_conf * 0.8, "AI Vision detected material"
        )

    # ===== PHASE 5: Template Graph Resolution =====

    try:
        from app.resource_engine.template_loader import TemplateGraphLoader
        from app.resource_engine.template_resolver import TemplateResolver
        
        loader = TemplateGraphLoader().load()
        resolver = TemplateResolver(loader)

        # Build dimension dict from blended dimensions
        blended_dims = {}
        for k, pv in result.dimensions.items():
            blended_dims[k] = pv.value

        if ftype != "unknown":
            template_result = resolver.resolve(ftype, blended_dims)
            result.template_graph = template_result
            
            # Add template view requirements as notes
            views = template_result.get("component_views", [])
            result.warnings.append(f"Template requires views: {', '.join(views)}")
            
            # Add constraint warnings
            for c in template_result.get("constraints", []):
                if not c.get("passed", True):
                    result.warnings.append(f"Constraint: {c.get('description', '')}")
    except Exception as e:
        result.errors.append(f"Template resolution failed: {e}")

    # ===== PHASE 6: Warnings & Summary =====

    if not result.entities and "error" not in str(result.errors):
        result.warnings.append("No geometry entities detected — image may be a photo, not a technical drawing")

    if result.product_type and result.product_type.source == "template_default":
        result.warnings.append("Furniture type could not be auto-detected — please specify it for better results")

    if ai_vision_result is None:
        result.warnings.append("AI Vision (GPT-4o/Gemini) not available — set OPENAI_API_KEY or GEMINI_API_KEY for better type/material detection")

    return result
