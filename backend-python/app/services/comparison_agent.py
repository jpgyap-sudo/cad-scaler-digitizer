"""
Comparison Agent — Image vs DXF Accuracy Scorer
================================================
Compares the source product image against the generated DXF and produces:
  - Overall alignment score (0.0 - 1.0)
  - Per-entity mismatch heatmap (bounding boxes of errors)
  - Edge overlap percentage
  - Dimension deviation report
  - Log of every error type with severity

This feeds back into ML training — each comparison becomes a labeled
training example that the digitizer can learn from.
"""

import os
import io
import math
import json
import uuid
import logging
import tempfile
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass, field, asdict


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that converts numpy types to Python native types."""
    def default(self, obj):
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return super().default(obj)

logger = logging.getLogger("comparison_agent")

# ---------------------------------------------------------------------------
# Comparison Result model
# ---------------------------------------------------------------------------

@dataclass
class ComparisonError:
    error_type: str           # "missing_line", "extra_line", "misaligned_dim", "missing_entity", "extra_entity"
    severity: str             # "critical", "major", "minor"
    description: str
    score_impact: float       # 0.0 - 1.0, how much this error reduces the overall score
    bbox: Optional[list] = None   # [x1, y1, x2, y2] pixel coords of error region
    source: str = "edge_mismatch" # "edge_mismatch", "dimension", "entity_count"

@dataclass
class ComparisonResult:
    job_id: str
    product_id: str
    image_url: str
    dxf_path: str

    # Overall scores
    overall_score: float       # 0.0 - 1.0 weighted average of all checks
    edge_overlap_score: float  # 0.0 - 1.0 — how well DXF edges match image edges
    entity_match_score: float  # 0.0 - 1.0 — entity count/type match
    shape_score: float         # 0.0 - 1.0 — silhouette IoU between DXF and product image
    dimension_deviation_pct: float  # average dimension deviation %

    # Detailed errors
    errors: list[dict] = field(default_factory=list)
    dimension_comparisons: list[dict] = field(default_factory=list)

    # Metadata
    entity_counts: dict = field(default_factory=dict)
    image_width: int = 0
    image_height: int = 0
    dxf_width_mm: float = 0.0
    dxf_height_mm: float = 0.0
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "product_id": self.product_id,
            "image_url": self.image_url,
            "overall_score": round(self.overall_score, 3),
            "edge_overlap_score": round(self.edge_overlap_score, 3),
            "entity_match_score": round(self.entity_match_score, 3),
            "shape_score": round(self.shape_score, 3),
            "dimension_deviation_pct": round(self.dimension_deviation_pct, 1),
            "errors": self.errors[:50],  # top 50 errors
            "dimension_comparisons": self.dimension_comparisons,
            "entity_counts": self.entity_counts,
            "image_dimensions": {"width": self.image_width, "height": self.image_height},
            "dxf_dimensions_mm": {"width": self.dxf_width_mm, "height": self.dxf_height_mm},
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Core comparison engine
# ---------------------------------------------------------------------------

def _rasterize_dxf(dxf_path: str, output_size=(1000, 1000)) -> Optional[Any]:
    """Convert DXF to a raster image for pixel-level comparison.
    Returns OpenCV image or None.
    """
    try:
        import cv2
        import numpy as np
        import ezdxf
        from ezdxf import render as dxf_render

        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        # Create blank canvas
        img = np.ones((output_size[1], output_size[0], 3), dtype=np.uint8) * 255

        # Find bounding box of all entities
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        entities_to_render = []
        for e in msp:
            try:
                if e.dxftype() == "LINE":
                    start, end = e.dxf.start, e.dxf.end
                    min_x = min(min_x, start.x, end.x)
                    max_x = max(max_x, start.x, end.x)
                    min_y = min(min_y, start.y, end.y)
                    max_y = max(max_y, start.y, end.y)
                    entities_to_render.append(e)
                elif e.dxftype() in ("CIRCLE", "ARC"):
                    cx, cy = e.dxf.center.x, e.dxf.center.y
                    r = float(e.dxf.radius)
                    min_x = min(min_x, cx - r)
                    max_x = max(max_x, cx + r)
                    min_y = min(min_y, cy - r)
                    max_y = max(max_y, cy + r)
                    entities_to_render.append(e)
                elif e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                    if e.dxftype() == "LWPOLYLINE":
                        pts = e.get_points()
                    else:
                        pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                    for p in pts:
                        min_x = min(min_x, p[0])
                        max_x = max(max_x, p[0])
                        min_y = min(min_y, p[1])
                        max_y = max(max_y, p[1])
                    entities_to_render.append(e)
            except Exception:
                continue

        if not entities_to_render or math.isinf(min_x):
            return None

        # Scale and translate to fit canvas
        dw = max(max_x - min_x, 1)
        dh = max(max_y - min_y, 1)
        scale = min(output_size[0] / dw, output_size[1] / dh) * 0.9
        ox = (output_size[0] - dw * scale) / 2
        oy = (output_size[1] - dh * scale) / 2

        def tx(x): return int((x - min_x) * scale + ox)
        def ty(y): return int(output_size[1] - ((y - min_y) * scale + oy))

        for e in entities_to_render:
            try:
                if e.dxftype() == "LINE":
                    s, end = e.dxf.start, e.dxf.end
                    cv2.line(img, (tx(s.x), ty(s.y)), (tx(end.x), ty(end.y)), (0, 0, 0), 2)
                elif e.dxftype() == "CIRCLE":
                    cx, cy = e.dxf.center.x, e.dxf.center.y
                    r = int(float(e.dxf.radius) * scale)
                    cv2.circle(img, (tx(cx), ty(cy)), r, (0, 0, 0), 2)
                elif e.dxftype() == "ARC":
                    cx, cy = e.dxf.center.x, e.dxf.center.y
                    r = int(float(e.dxf.radius) * scale)
                    sa = math.radians(float(e.dxf.start_angle))
                    ea = math.radians(float(e.dxf.end_angle))
                    # Draw as points along the arc
                    for t in range(0, 100):
                        angle = sa + (ea - sa) * t / 100
                        x = int(tx(cx + r * math.cos(angle)))
                        y = int(ty(cy + r * math.sin(angle)))
                        if t > 0:
                            cv2.line(img, (lx, ly), (x, y), (0, 0, 0), 2)
                        lx, ly = x, y
                elif e.dxftype() == "LWPOLYLINE":
                    pts = e.get_points()
                    pts_arr = np.array([(tx(p[0]), ty(p[1])) for p in pts], dtype=np.int32)
                    cv2.polylines(img, [pts_arr], bool(e.closed), (0, 0, 0), 2)
                elif e.dxftype() == "POLYLINE":
                    pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                    pts_arr = np.array([[tx(p[0]), ty(p[1])] for p in pts], dtype=np.int32)
                    cv2.polylines(img, [pts_arr], False, (0, 0, 0), 2)
            except Exception:
                continue

        return img
    except Exception as e:
        logger.error(f"Rasterization failed: {e}")
        return None


def compare_images(original_img: Any, dxf_raster: Any) -> tuple[float, list, int, int]:
    """Pixel-level comparison of original image vs DXF raster using edge detection.
    
    Returns: (overlap_score, error_regions, original_edges_count, dxf_edges_count)
    """
    import cv2
    import numpy as np

    # Resize both to same dimensions
    h, w = original_img.shape[:2]
    dxf_resized = cv2.resize(dxf_raster, (w, h))

    # Convert to grayscale
    gray_orig = cv2.cvtColor(original_img, cv2.COLOR_BGR2GRAY)
    gray_dxf = cv2.cvtColor(dxf_resized, cv2.COLOR_BGR2GRAY)

    # Edge detection (configurable thresholds from training feedback)
    from app.services.digitizer_config import get_canny_thresholds
    _canny_low, _canny_high = get_canny_thresholds()
    edges_orig = cv2.Canny(gray_orig, _canny_low, _canny_high)
    edges_dxf = cv2.Canny(gray_dxf, _canny_low, _canny_high)

    # Morphological dilation to make edges thicker for comparison
    kernel = np.ones((3, 3), np.uint8)
    edges_orig_dilated = cv2.dilate(edges_orig, kernel, iterations=1)
    edges_dxf_dilated = cv2.dilate(edges_dxf, kernel, iterations=1)

    # Edge overlap
    overlap = cv2.bitwise_and(edges_orig_dilated, edges_dxf_dilated)
    union = cv2.bitwise_or(edges_orig_dilated, edges_dxf_dilated)

    total_union = np.sum(union > 0)
    total_overlap = np.sum(overlap > 0)
    overlap_score = total_overlap / max(total_union, 1)

    # Find error regions — edges in one but not the other
    errors_orig = cv2.bitwise_and(edges_orig_dilated, cv2.bitwise_not(edges_dxf_dilated))
    errors_dxf = cv2.bitwise_and(edges_dxf_dilated, cv2.bitwise_not(edges_orig_dilated))

    # Contour detection for error bounding boxes
    error_regions = []
    combined_errors = cv2.bitwise_or(errors_orig, errors_dxf)
    contours, _ = cv2.findContours(combined_errors, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 50:  # filter tiny noise
            x, y, w2, h2 = cv2.boundingRect(cnt)
            error_regions.append({
                "bbox": [int(x), int(y), int(x + w2), int(y + h2)],
                "area_px": int(area),
                "type": "edge_mismatch",
            })

    # Sort by area descending
    error_regions.sort(key=lambda r: r["area_px"], reverse=True)

    orig_edge_count = int(np.sum(edges_orig > 0))
    dxf_edge_count = int(np.sum(edges_dxf > 0))

    return overlap_score, error_regions, orig_edge_count, dxf_edge_count


def _extract_foreground(img: Any) -> Any:
    """Extract foreground mask from product image using GrabCut + edge refinement.
    
    GrabCut is initialized with a center rectangle (assumes product is centered).
    Edge-aware refinement sharpens the boundary.
    Returns binary mask (255 = foreground, 0 = background).
    """
    import cv2
    import numpy as np

    h, w = img.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)

    # Initial rectangle: assume product is in center 70% of image
    margin_x, margin_y = int(w * 0.15), int(h * 0.15)
    rect = (margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y)

    cv2.grabCut(img, mask, rect, bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
    fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    # Edge-aware refinement: use Canny edges to clean up boundary
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    kernel = np.ones((3, 3), np.uint8)
    edges_dilated = cv2.dilate(edges, kernel, iterations=1)

    # Remove background noise below the mask
    fg_mask = cv2.bitwise_and(fg_mask, cv2.bitwise_not(edges_dilated))

    # Morphological cleanup
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

    # Fill holes (keep largest connected component)
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        clean = np.zeros_like(fg_mask)
        cv2.drawContours(clean, [largest], -1, 255, -1)
        fg_mask = clean

    return fg_mask


def _contour_similarity(mask_a: Any, mask_b: Any) -> float:
    """Compare shape of two binary masks using Hu moment distance.
    
    Hu moments are invariant to translation, scale, and rotation,
    making this a robust shape comparison even when the product
    perspective differs from the DXF orthographic projection.
    Returns similarity score 0.0-1.0.
    """
    import cv2
    import numpy as np

    ca, _ = cv2.findContours(mask_a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cb, _ = cv2.findContours(mask_b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not ca or not cb:
        return 0.0

    # Largest contour from each
    ca = max(ca, key=cv2.contourArea)
    cb = max(cb, key=cv2.contourArea)

    ha = cv2.HuMoments(cv2.moments(ca)).flatten()
    hb = cv2.HuMoments(cv2.moments(cb)).flatten()

    # Log-scale Hu moments for better numeric stability
    ha = -np.sign(ha) * np.log10(np.abs(ha) + 1e-10)
    hb = -np.sign(hb) * np.log10(np.abs(hb) + 1e-10)

    dist = np.sum(np.abs(ha - hb))
    # Convert distance to similarity: dist=0 => 1.0, dist increases => score decreases
    return max(0.0, min(1.0, 1.0 - dist / 10.0))


def compare_silhouettes(original_img: Any, dxf_raster: Any) -> float:
    """Compare overall shape of the product using silhouette IoU + contour matching.
    
    Uses GrabCut (not OTSU) for better foreground extraction from e-commerce
    photos. Combines pixel-level IoU with contour-based Hu moment similarity
    for a robust shape score that tolerates perspective differences.
    """
    import cv2
    import numpy as np

    h, w = original_img.shape[:2]
    dxf_resized = cv2.resize(dxf_raster, (w, h))
    gray_dxf = cv2.cvtColor(dxf_resized, cv2.COLOR_BGR2GRAY)

    # Product foreground via GrabCut (much better than OTSU for e-commerce)
    fg_orig = _extract_foreground(original_img)

    # DXF silhouette: non-white pixels = drawn geometry, dilate to fill lines
    dxf_inv = cv2.bitwise_not(gray_dxf)
    _, fg_dxf = cv2.threshold(dxf_inv, 30, 255, cv2.THRESH_BINARY)
    fg_dxf = cv2.morphologyEx(fg_dxf, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    fg_dxf = cv2.dilate(fg_dxf, np.ones((5, 5), np.uint8), iterations=3)

    # Pixel-level IoU
    i = np.sum(cv2.bitwise_and(fg_orig, fg_dxf) > 0)
    u = np.sum(cv2.bitwise_or(fg_orig, fg_dxf) > 0)
    iou = i / max(u, 1)

    # Contour-based shape similarity (Hu moments — invariant to perspective)
    contour_sim = _contour_similarity(fg_orig, fg_dxf)

    # Blend: IoU (60%) + contour (40%)
    # Contour similarity provides robustness to perspective/size differences
    # while IoU provides pixel-level alignment signal
    return min(1.0, iou * 0.6 + contour_sim * 0.4)


def compare_entities(
    dxf_path: str,
    detected_entities: Optional[dict] = None,
) -> tuple[float, list, dict]:
    """Compare entity counts/types between detected and rendered DXF.
    
    Args:
        dxf_path: Path to the DXF file
        detected_entities: Dict from the digitizer with line/circle/rect counts
    
    Returns:
        (entity_match_score, errors, entity_counts)
    """
    errors = []
    entity_counts = {}

    try:
        import ezdxf
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        # Count DXF entities by type
        dxf_counts = {"line": 0, "circle": 0, "arc": 0, "polyline": 0, "text": 0, "total": 0}
        for e in msp:
            dxf_counts["total"] += 1
            dt = e.dxftype().lower()
            if dt == "line": dxf_counts["line"] += 1
            elif dt == "circle": dxf_counts["circle"] += 1
            elif dt == "arc": dxf_counts["arc"] += 1
            elif dt in ("lwpolyline", "polyline"): dxf_counts["polyline"] += 1
            elif dt in ("text", "mtext"): dxf_counts["text"] += 1

        entity_counts = dxf_counts

        # If we have detected counts from the digitizer, compare
        if detected_entities:
            detected_lines = detected_entities.get("lines", 0) or 0
            detected_circles = detected_entities.get("circles", 0) or 0
            detected_rects = detected_entities.get("rectangles", 0) or 0

            # Compare line counts
            if detected_lines > 0:
                diff = abs(detected_lines - dxf_counts["line"])
                pct = diff / max(detected_lines, 1)
                if pct > 0.3:
                    errors.append(ComparisonError(
                        error_type="missing_line",
                        severity="major" if pct > 0.5 else "minor",
                        description=f"Line count mismatch: detected {detected_lines}, DXF has {dxf_counts['line']} ({pct*100:.0f}% difference)",
                        score_impact=pct * 0.3,
                    ))

            # Compare circle/arc counts
            total_curves = detected_circles + detected_rects
            dxf_curves = dxf_counts["circle"] + dxf_counts["arc"]
            if total_curves > 0 and dxf_curves > 0:
                diff = abs(total_curves - dxf_curves)
                pct = diff / max(total_curves, 1)
                if pct > 0.3:
                    errors.append(ComparisonError(
                        error_type="missing_entity",
                        severity="major" if pct > 0.5 else "minor",
                        description=f"Circle/arc count mismatch: detected {total_curves}, DXF has {dxf_curves}",
                        score_impact=pct * 0.25,
                    ))

        entity_match_score = max(0.0, 1.0 - sum(e.score_impact for e in errors))

    except Exception as e:
        logger.error(f"Entity comparison failed: {e}")
        entity_match_score = 0.5
        errors.append(ComparisonError(
            error_type="comparison_error",
            severity="major",
            description=f"Entity comparison error: {e}",
            score_impact=0.3,
        ))

    return entity_match_score, [asdict(e) for e in errors], entity_counts


def compare_dimensions(
    page_dims: dict[str, float],
    dxf_path: str,
    resolved_dimensions: Optional[dict] = None,
) -> tuple[list, float]:
    """Compare page-extracted dimensions against resolved pipeline dimensions or DXF bbox.
    
    When resolved_dimensions are available (from pipeline output), uses those —
    they represent the actual real-world dimensions in cm. Falls back to DXF
    bounding box comparison (legacy) when resolved_dimensions aren't available.
    
    Returns:
        tuple of (dimension_comparisons list, average_deviation_pct)
    """
    if resolved_dimensions:
        return _compare_resolved_dims(page_dims, resolved_dimensions)
    
    import ezdxf
    
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception:
        return [], 0.0
    
    msp = doc.modelspace()
    min_x = float('inf')
    min_y = float('inf')
    max_x = float('-inf')
    max_y = float('-inf')
    
    for entity in msp:
        if entity.dxftype() == 'LINE':
            min_x = min(min_x, entity.dxf.start.x, entity.dxf.end.x)
            max_x = max(max_x, entity.dxf.start.x, entity.dxf.end.x)
            min_y = min(min_y, entity.dxf.start.y, entity.dxf.end.y)
            max_y = max(max_y, entity.dxf.start.y, entity.dxf.end.y)
        elif entity.dxftype() == 'LWPOLYLINE':
            try:
                pts = list(entity.get_points())
                for p in pts:
                    min_x = min(min_x, p[0])
                    max_x = max(max_x, p[0])
                    min_y = min(min_y, p[1])
                    max_y = max(max_y, p[1])
            except Exception:
                continue
        elif entity.dxftype() == 'CIRCLE':
            cx, cy = entity.dxf.center.x, entity.dxf.center.y
            r = entity.dxf.radius
            min_x = min(min_x, cx - r)
            max_x = max(max_x, cx + r)
            min_y = min(min_y, cy - r)
            max_y = max(max_y, cy + r)
    
    if math.isinf(min_x):
        return [], 0.0
    
    dxf_w = max_x - min_x
    dxf_h = max_y - min_y
    
    page_w = page_dims.get("width_cm", 0)
    page_h = page_dims.get("overall_height_cm", 0)
    page_d = page_dims.get("depth_cm", 0)
    page_l = page_dims.get("length_cm", 0)
    
    if page_w and dxf_w:
        page_w_mm = page_w * 10
        dev = abs(page_w_mm - dxf_w) / max(page_w_mm, 1) * 100
        deviations.append(dev)
        comparisons.append({
            "dimension": "width",
            "page_value_cm": round(page_w, 1),
            "dxf_value_mm": round(dxf_w, 1),
            "deviation_pct": round(dev, 1),
            "passed": dev <= 15,
        })
    
    if page_h and dxf_h:
        page_h_mm = page_h * 10
        dev = abs(page_h_mm - dxf_h) / max(page_h_mm, 1) * 100
        deviations.append(dev)
        comparisons.append({
            "dimension": "height",
            "page_value_cm": round(page_h, 1),
            "dxf_value_mm": round(dxf_h, 1),
            "deviation_pct": round(dev, 1),
            "passed": dev <= 15,
        })
    
    page_depth = page_d or page_l
    if page_depth:
        if dxf_w and dxf_h:
            dxf_depth = dxf_w
            page_depth_mm = page_depth * 10
            dev = abs(page_depth_mm - dxf_depth) / max(page_depth_mm, 1) * 100
            deviations.append(dev)
            comparisons.append({
                "dimension": "depth",
                "page_value_cm": round(page_depth, 1),
                "dxf_value_mm": round(dxf_depth, 1),
                "deviation_pct": round(dev, 1),
                "passed": dev <= 15,
            })
    
    avg_dev = sum(deviations) / max(len(deviations), 1) if deviations else 0.0
    return comparisons, avg_dev


def _compare_resolved_dims(page_dims: dict, resolved: dict) -> tuple[list, float]:
    """Compare page dimensions against resolved pipeline dimensions (real cm, not DXF coords)."""
    comparisons = []
    deviations = []

    dim_pairs = [
        ("width_cm", "width", ["width_cm", "top_diameter_cm"]),
        ("overall_height_cm", "height", ["overall_height_cm", "height_cm"]),
        ("depth_cm", "depth", ["depth_cm", "length_cm"]),
    ]

    for page_key, dim_label, resolved_keys in dim_pairs:
        page_val = page_dims.get(page_key, 0)
        resolved_val = 0
        for rk in resolved_keys:
            rv = resolved.get(rk, 0)
            if rv and isinstance(rv, (int, float)):
                resolved_val = float(rv)
                break

        if page_val and resolved_val:
            dev = abs(resolved_val - page_val) / max(page_val, 1) * 100
            deviations.append(dev)
            comparisons.append({
                "dimension": dim_label,
                "page_value_cm": round(page_val, 1),
                "resolved_value_cm": round(resolved_val, 1),
                "deviation_pct": round(dev, 1),
                "passed": dev <= 15,
            })

    avg_dev = sum(deviations) / max(len(deviations), 1) if deviations else 0.0
    return comparisons, avg_dev


# ---------------------------------------------------------------------------
# Main comparison entry point
# ---------------------------------------------------------------------------

def compare_digitization(
    job_id: str,
    product_id: str,
    image_url: str,
    image_data: bytes,
    dxf_path: str,
    page_dimensions: Optional[dict] = None,
    detected_entities: Optional[dict] = None,
    resolved_dimensions: Optional[dict] = None,
) -> ComparisonResult:
    """Full comparison pipeline: image vs DXF edge overlay, entity count, dimensions.
    
    Args:
        job_id: Unique job identifier
        product_id: Product identifier
        image_url: URL of the source product image
        image_data: Raw image bytes for OpenCV processing
        dxf_path: Local path to the generated DXF file
        page_dimensions: Optional dimensions extracted from the product page
        detected_entities: Optional entity counts from the digitizer
    
    Returns:
        ComparisonResult with scores, errors, and logs
    """
    import cv2
    import numpy as np

    result = ComparisonResult(
        job_id=job_id,
        product_id=product_id,
        image_url=image_url,
        dxf_path=dxf_path,
        overall_score=0.0,
        edge_overlap_score=0.0,
        entity_match_score=0.0,
        shape_score=0.0,
        dimension_deviation_pct=0.0,
        created_at=datetime.utcnow().isoformat(),
    )

    # Decode the original image
    img_array = np.frombuffer(image_data, np.uint8)
    original_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if original_img is None:
        result.errors.append(asdict(ComparisonError(
            error_type="image_decode_error",
            severity="critical",
            description="Failed to decode original image",
            score_impact=1.0,
        )))
        return result

    result.image_width = original_img.shape[1]
    result.image_height = original_img.shape[0]

    # Rasterize the DXF to an image
    dxf_raster = _rasterize_dxf(dxf_path, output_size=(result.image_width, result.image_height))
    if dxf_raster is None:
        result.errors.append(asdict(ComparisonError(
            error_type="dxf_render_error",
            severity="critical",
            description="Failed to rasterize DXF for comparison",
            score_impact=0.5,
        )))
        # Still continue with entity/dimension checks
    else:
        # Edge overlay comparison
        overlap_score, error_regions, orig_edges, dxf_edges = compare_images(original_img, dxf_raster)
        result.edge_overlap_score = overlap_score
        result.entity_counts = {"image_edges": orig_edges, "dxf_edges": dxf_edges}

        # Add error regions as comparison errors
        for region in error_regions[:20]:  # top 20
            sev = "critical" if region["area_px"] > 10000 else ("major" if region["area_px"] > 2000 else "minor")
            result.errors.append(asdict(ComparisonError(
                error_type="edge_mismatch",
                severity=sev,
                description=f"Edge mismatch region: {region['area_px']}px² — edges exist in image but not DXF (or vice versa)",
                score_impact=region["area_px"] / max(result.image_width * result.image_height, 1),
                bbox=region["bbox"],
                source="edge_mismatch",
            )))

    # Silhouette shape comparison (IoU of foreground masks)
    try:
        result.shape_score = compare_silhouettes(original_img, dxf_raster)
    except Exception:
        result.shape_score = 0.0

    # Entity count comparison
    ent_score, ent_errors, ent_counts = compare_entities(dxf_path, detected_entities)
    result.entity_match_score = ent_score
    result.entity_counts.update(ent_counts)
    result.errors.extend(ent_errors)

    # Dimension comparison (prefer resolved_dimensions for accurate real-world comparison)
    if page_dimensions:
        dim_comparisons, avg_dev = compare_dimensions(
            page_dimensions, dxf_path, resolved_dimensions=resolved_dimensions,
        )
        result.dimension_comparisons = dim_comparisons
        result.dimension_deviation_pct = avg_dev

        # Add dimension errors
        for dc in dim_comparisons:
            if not dc.get("passed", True):
                result.errors.append(asdict(ComparisonError(
                    error_type="misaligned_dim",
                    severity="major",
                    description=f"Dimension {dc['dimension']}: page={dc['page_value_cm']}cm, DXF={dc['dxf_value_mm']}mm (deviation {dc['deviation_pct']}%)",
                    score_impact=dc["deviation_pct"] / 100 * 0.3,
                    source="dimension",
                )))

    # Compute overall weighted score
    # Shape similarity (silhouette IoU) and dimension accuracy are the two
    # primary signals. Edge overlap is secondary (unreliable for e-commerce
    # backgrounds). Entity match is a tiebreaker.
    has_page_dims = bool(page_dimensions and (page_dimensions.get("width_cm") or page_dimensions.get("overall_height_cm")))
    has_dxf_edge = dxf_raster is not None

    if has_page_dims:
        dim_reliability = max(0.5, 1.0 - min(result.dimension_deviation_pct, 100) / 100)
        dim_score = dim_reliability
        shape_score = result.shape_score
        shape_weight = 0.40
        dim_weight = 0.40
        entity_weight = 0.10
        edge_weight = 0.10
    elif has_dxf_edge:
        dim_score = max(0.0, 1.0 - min(result.dimension_deviation_pct, 100) / 100)
        shape_score = result.shape_score
        shape_weight = 0.40
        dim_weight = 0.20
        entity_weight = 0.20
        edge_weight = 0.20
    else:
        dim_score = 0.0
        shape_score = result.shape_score
        shape_weight = 0.40
        dim_weight = 0.20
        entity_weight = 0.20
        edge_weight = 0.20

    overall = (
        result.edge_overlap_score * edge_weight
        + result.entity_match_score * entity_weight
        + shape_score * shape_weight
        + dim_score * dim_weight
    )

    # Apply error penalties (minimal — page dims are ground truth, edge errors expected)
    total_penalty = sum(e["score_impact"] for e in result.errors)
    overall = max(0.0, overall - total_penalty * 0.02)

    # Convert numpy types to Python native for JSON serialization
    import numpy as np
    result.overall_score = float(overall) if isinstance(overall, np.floating) else overall
    result.edge_overlap_score = float(result.edge_overlap_score) if isinstance(result.edge_overlap_score, np.floating) else result.edge_overlap_score
    result.entity_match_score = float(result.entity_match_score) if isinstance(result.entity_match_score, np.floating) else result.entity_match_score
    result.dimension_deviation_pct = float(result.dimension_deviation_pct) if isinstance(result.dimension_deviation_pct, np.floating) else result.dimension_deviation_pct

    logger.info(
        f"[ComparisonAgent] {product_id}: score={overall:.3f} "
        f"(edge={result.edge_overlap_score:.3f}, ent={result.entity_match_score:.3f}, "
        f"dim_dev={result.dimension_deviation_pct:.1f}%) "
        f"errors={len(result.errors)}"
    )

    return result


def log_comparison_to_db(result: ComparisonResult) -> bool:
    """Persist comparison result to Postgres for ML training feedback.
    
    Creates a record in comparison_results table with all scores, errors,
    and dimension data for later analysis.
    """
    try:
        import psycopg2
        import json

        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO comparison_results
                (job_id, product_id, overall_score, edge_overlap_score,
                 entity_match_score, shape_score, dimension_deviation_pct,
                 errors_json, dimension_comparisons_json,
                 image_width, image_height, dxf_width_mm, dxf_height_mm)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE SET
                overall_score = EXCLUDED.overall_score,
                edge_overlap_score = EXCLUDED.edge_overlap_score,
                entity_match_score = EXCLUDED.entity_match_score,
                shape_score = EXCLUDED.shape_score,
                dimension_deviation_pct = EXCLUDED.dimension_deviation_pct
        """, (
            result.job_id,
            result.product_id,
            result.overall_score,
            result.edge_overlap_score,
            result.entity_match_score,
            result.shape_score,
            result.dimension_deviation_pct,
            json.dumps(result.errors[:50], cls=NumpyEncoder),
            json.dumps(result.dimension_comparisons, cls=NumpyEncoder),
            result.image_width,
            result.image_height,
            result.dxf_width_mm,
            result.dxf_height_mm,
        ))

        conn.commit()
        cur.close()
        conn.close()

        # Auto-trigger calibration after every comparison (if enough data)
        try:
            import psycopg2 as _pg2
            _conn2 = _pg2.connect(
                host=os.environ.get("PG_HOST", "postgres"), port=int(os.environ.get("PG_PORT", 5432)),
                dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
                user=os.environ.get("PG_USER", "postgres"), password=os.environ.get("PG_PASSWORD", "postgres"),
            )
            _c2 = _conn2.cursor()
            _c2.execute("SELECT COUNT(*) FROM comparison_results")
            _count = _c2.fetchone()[0]
            _c2.close()
            _conn2.close()
            if _count >= 3 and _count % 3 == 0:
                from app.services.training_feedback import generate_correction_hints, apply_correction_hints
                _hints = generate_correction_hints()
                _applied = apply_correction_hints(_hints)
                if _applied > 0:
                    logger.info(f"Auto-calibration: applied {_applied} correction hints ({_count} comparisons)")
        except Exception as _:
            pass

        return True
    except Exception as e:
        import traceback
        logger.warning(f"Failed to log comparison to DB: {e}\n{traceback.format_exc()}")
        return False
