"""
Scale Solver — compute pixel-to-centimeter scale from confirmed dimension pairs.

Strategy:
1. Collect all (pixel_length, cm_value) pairs from dimension association
2. Filter out outliers using RANSAC-like approach (median + MAD)
3. Compute separate X and Y scale factors when possible
4. Apply ratio scaling only for dimensions without a direct pixel match
5. Mark every output with its source: MEASURED | COMPUTED | ESTIMATED | RATIO

The key improvement over visual_ratio_scaler.py:
  Pixel measurements take priority; ratios are only fallback for hidden parts.
"""

import math
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Literal

SourceType = Literal["MEASURED", "COMPUTED", "ESTIMATED", "RATIO"]


@dataclass
class ScaleFactor:
    """A computed scale factor linking pixels to cm."""
    px_per_cm: float
    source: SourceType
    confidence: float
    sample_count: int = 0
    std_dev: float = 0.0
    is_x_scale: bool = False
    is_y_scale: bool = False

    def to_cm(self, pixels: float) -> float:
        return pixels / self.px_per_cm if self.px_per_cm > 0 else 0.0

    def to_px(self, cm: float) -> float:
        return cm * self.px_per_cm


@dataclass
class ResolvedDimension:
    """A single dimension with its source and confidence metadata."""
    name: str                          # e.g. "top_diameter_cm"
    value_cm: float                    # Resolved value in cm
    pixel_equivalent: Optional[float] = None  # Measured in pixels
    source: SourceType = "ESTIMATED"
    confidence: float = 0.0
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value_cm": round(self.value_cm, 2),
            "pixel_equivalent": round(self.pixel_equivalent, 1) if self.pixel_equivalent else None,
            "source": self.source,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


@dataclass
class ScaleSolution:
    """Complete scale solution for a drawing."""
    x_scale: Optional[ScaleFactor]
    y_scale: Optional[ScaleFactor]
    combined_scale: Optional[ScaleFactor]
    resolved_dimensions: Dict[str, ResolvedDimension]
    outlier_rejected: int = 0
    samples_used: int = 0
    has_sufficient_data: bool = False

    def to_dict(self) -> dict:
        return {
            "x_scale": {"px_per_cm": round(self.x_scale.px_per_cm, 4),
                         "confidence": round(self.x_scale.confidence, 2),
                         "source": self.x_scale.source}
                        if self.x_scale else None,
            "y_scale": {"px_per_cm": round(self.y_scale.px_per_cm, 4),
                         "confidence": round(self.y_scale.confidence, 2),
                         "source": self.y_scale.source}
                        if self.y_scale else None,
            "combined_scale": {"px_per_cm": round(self.combined_scale.px_per_cm, 4),
                                "confidence": round(self.combined_scale.confidence, 2),
                                "source": self.combined_scale.source}
                               if self.combined_scale else None,
            "resolved_dimensions": {
                k: v.to_dict() for k, v in self.resolved_dimensions.items()
            },
            "outlier_rejected": self.outlier_rejected,
            "samples_used": self.samples_used,
            "has_sufficient_data": self.has_sufficient_data,
        }


# ===== Outlier Rejection =====

def _reject_outliers(
    ratios: List[float],
    mad_threshold: float = 3.0
) -> Tuple[List[float], int]:
    """
    Reject outliers using Median Absolute Deviation (MAD).
    More robust than standard deviation for small samples.
    """
    if len(ratios) < 3:
        return ratios, 0

    median = statistics.median(ratios)
    mad = statistics.median([abs(r - median) for r in ratios])

    if mad == 0:
        return ratios, 0

    filtered = [r for r in ratios if abs(r - median) / mad < mad_threshold]
    rejected = len(ratios) - len(filtered)
    return filtered, rejected


# ===== Main Solver =====

def solve_scale(
    dimension_associations: List['Association'],
    vision_lines: List[Tuple[float, float, float, float]],
    dimensions_known_cm: Optional[Dict[str, float]] = None,
) -> ScaleSolution:
    """
    Solve for scale factors using confirmed dimension-geometry pairs.

    Algorithm:
    1. Collect (pixel_length, cm_value) pairs from confirmed associations
    2. Separate into horizontal/vertical pairs for anisotropic scaling
    3. Reject outliers using MAD
    4. Compute combined, x, and y scale factors
    5. Apply scale to resolve all dimension values

    Args:
        dimension_associations: List of Association objects from dimension_associator
        vision_lines: Raw vision lines from OpenCV
        dimensions_known_cm: Optional known dimension values (from OCR/user)

    Returns:
        ScaleSolution with resolved scale factors and dimension values
    """
    from app.backend.dimension_associator import Association

    dimensions_known_cm = dimensions_known_cm or {}

    # --- Collect pixel-to-cm pairs ---
    # Separate into horizontal, vertical, and mixed
    h_pairs: List[Tuple[float, float]] = []    # (pixels, cm)
    v_pairs: List[Tuple[float, float]] = []
    general_pairs: List[Tuple[float, float]] = []

    known_by_value: Dict[float, str] = {v: k for k, v in dimensions_known_cm.items()}

    for assoc in dimension_associations:
        if assoc.confidence < 0.5:
            continue  # Only use confident associations
        if not assoc.dim_line or assoc.value_cm <= 0:
            continue

        px_len = assoc.dim_line.length_px
        cm_val = assoc.value_cm
        pair = (px_len, cm_val)

        if assoc.dim_line.is_vertical:
            v_pairs.append(pair)
        elif assoc.dim_line.is_horizontal:
            h_pairs.append(pair)
        else:
            general_pairs.append(pair)

    # --- For diameters, compute from circle radius ---
    for assoc in dimension_associations:
        if assoc.confidence < 0.5:
            continue
        if assoc.associated_circle and assoc.value_cm > 0:
            _, _, r_px = assoc.associated_circle
            pixel_diameter = r_px * 2
            general_pairs.append((pixel_diameter, assoc.value_cm))

    # --- Compute ratios ---
    def _ratios_from_pairs(pairs):
        if not pairs:
            return []
        return [px / cm for px, cm in pairs if cm > 0]

    h_ratios = _ratios_from_pairs(h_pairs)
    v_ratios = _ratios_from_pairs(v_pairs)
    all_ratios = _ratios_from_pairs(general_pairs) + h_ratios + v_ratios

    # --- Reject outliers ---
    h_filtered, h_rejected = _reject_outliers(h_ratios)
    v_filtered, v_rejected = _reject_outliers(v_ratios)
    all_filtered, all_rejected = _reject_outliers(all_ratios)

    total_rejected = all_rejected + (h_rejected if not h_ratios else 0) + (v_rejected if not v_ratios else 0)

    # --- Compute scale factors ---
    x_scale = None
    y_scale = None
    combined_scale = None

    # X scale: from horizontal pairs or combined
    if h_filtered:
        median_h = statistics.median(h_filtered)
        std_h = statistics.stdev(h_filtered) if len(h_filtered) > 1 else 0
        x_scale = ScaleFactor(
            px_per_cm=median_h,
            source="MEASURED",
            confidence=min(0.95, 0.5 + len(h_filtered) * 0.1),
            sample_count=len(h_filtered),
            std_dev=std_h,
            is_x_scale=True,
        )

    # Y scale: from vertical pairs or fallback to X/combined
    if v_filtered:
        median_v = statistics.median(v_filtered)
        std_v = statistics.stdev(v_filtered) if len(v_filtered) > 1 else 0
        y_scale = ScaleFactor(
            px_per_cm=median_v,
            source="MEASURED",
            confidence=min(0.95, 0.5 + len(v_filtered) * 0.1),
            sample_count=len(v_filtered),
            std_dev=std_v,
            is_y_scale=True,
        )

    # Combined scale
    all_source = all_filtered or h_filtered or v_filtered
    if all_source:
        median_all = statistics.median(all_source)
        std_all = statistics.stdev(all_source) if len(all_source) > 1 else 0

        if len(all_source) >= 3:
            source = "COMPUTED"
            conf = min(0.95, 0.4 + len(all_source) * 0.08)
        elif len(all_source) >= 1:
            source = "MEASURED"
            conf = 0.6
        else:
            source = "ESTIMATED"
            conf = 0.3

        combined_scale = ScaleFactor(
            px_per_cm=median_all,
            source=source,
            confidence=min(0.95, conf),
            sample_count=len(all_source),
            std_dev=std_all,
        )

    # --- Resolve all dimension values ---
    resolved: Dict[str, ResolvedDimension] = {}

    for name, cm_val in dimensions_known_cm.items():
        resolved[name] = ResolvedDimension(
            name=name, value_cm=cm_val, source="MEASURED",
            confidence=0.98,
            evidence="From OCR dimension label",
        )

    # Add resolved from associations
    for assoc in dimension_associations:
        if assoc.confidence < 0.5 or assoc.value_cm <= 0:
            continue

        name = f"dim_{assoc.text.strip()[:20]}"
        pixel_val = assoc.dim_line.length_px if assoc.dim_line else None

        resolved[name] = ResolvedDimension(
            name=name,
            value_cm=assoc.value_cm,
            pixel_equivalent=pixel_val,
            source="MEASURED" if assoc.confidence > 0.7 else "ESTIMATED",
            confidence=assoc.confidence,
            evidence="; ".join(assoc.evidence),
        )

    has_sufficient = combined_scale is not None and combined_scale.sample_count >= 2

    return ScaleSolution(
        x_scale=x_scale,
        y_scale=y_scale,
        combined_scale=combined_scale,
        resolved_dimensions=resolved,
        outlier_rejected=total_rejected,
        samples_used=len(all_source) if all_source else 0,
        has_sufficient_data=has_sufficient,
    )


def apply_scale_to_model(
    drawing_model,
    scale_solution: ScaleSolution,
    pixel_geometry: Dict,
) -> dict:
    """
    Apply resolved scale factors to convert pixel geometry to cm coordinates.

    Args:
        drawing_model: DrawingModel to populate
        scale_solution: Resolved scale factors
        pixel_geometry: Dict with 'lines', 'circles', 'rects' in pixels

    Returns:
        Updated drawing model dict in cm coordinates
    """
    combined = scale_solution.combined_scale
    if not combined or not scale_solution.has_sufficient_data:
        return {}

    px_per_cm = combined.px_per_cm
    x_scale = scale_solution.x_scale or combined
    y_scale = scale_solution.y_scale or combined

    result = {
        "lines_cm": [],
        "circles_cm": [],
        "rects_cm": [],
        "scale": {
            "px_per_cm": px_per_cm,
            "confidence": combined.confidence,
            "x_px_per_cm": x_scale.px_per_cm,
            "y_px_per_cm": y_scale.px_per_cm,
        },
    }

    # Convert lines
    for line in pixel_geometry.get("lines", []):
        if len(line) == 4:
            x1, y1, x2, y2 = line
        elif len(line) == 2:
            (x1, y1), (x2, y2) = line
        else:
            continue

        result["lines_cm"].append((
            x1 / x_scale.px_per_cm,
            (height - y1) / y_scale.px_per_cm if y_scale else 0,
            x2 / x_scale.px_per_cm,
            (height - y2) / y_scale.px_per_cm if y_scale else 0,
        ))

    # Convert circles
    height = 0
    for circle in pixel_geometry.get("circles", []):
        if len(circle) >= 3:
            cx, cy, r = circle[:3]
            result["circles_cm"].append((
                cx / x_scale.px_per_cm,
                cy / y_scale.px_per_cm,
                r / px_per_cm,
            ))

    return result


# Public API
def compute_scale(
    dimension_associations: List['Association'],
    vision_lines: List[Tuple[float, float, float, float]],
    known_dimensions_cm: Optional[Dict[str, float]] = None,
) -> ScaleSolution:
    """Main entry point: compute scale factors from associated dimension pairs."""
    return solve_scale(dimension_associations, vision_lines, known_dimensions_cm)
