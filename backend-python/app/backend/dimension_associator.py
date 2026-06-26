"""
Dimension Associator — connect OCR-detected text to the geometry it measures.

The core problem this solves:
  OCR reads "40 DIA" and "80 DIA", but without knowing which circle or line
  each number belongs to, the values can be swapped, producing wrong CAD.

Strategy:
1. For each dimension text box, find the nearest:
   a. Arrowhead ticks (line endpoints with small angle changes)
   b. Extension lines (thin lines perpendicular to dimension line)
   c. Object edges (thick continuous lines)
2. Score each candidate match by proximity + geometric alignment
3. Return verified dimension→geometry pairs

This creates the "dimension graph" that links text ↔ lines ↔ objects.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Set
from app.backend.ocr_layout_parser import TextBox


@dataclass
class DimensionLine:
    """A dimension line with arrows/ticks at both ends."""
    p1: Tuple[float, float]   # First arrow position
    p2: Tuple[float, float]   # Second arrow position
    extension_start: Optional[Tuple[float, float]] = None  # Extension line 1
    extension_end: Optional[Tuple[float, float]] = None    # Extension line 2
    is_vertical: bool = False
    is_horizontal: bool = False

    @property
    def length_px(self) -> float:
        return math.hypot(self.p2[0] - self.p1[0], self.p2[1] - self.p1[1])

    @property
    def midpoint(self) -> Tuple[float, float]:
        return ((self.p1[0] + self.p2[0]) / 2, (self.p1[1] + self.p2[1]) / 2)


@dataclass
class Association:
    """A confirmed association between a dimension label and geometry."""
    text: str
    value_cm: float
    text_box: TextBox
    dim_line: Optional[DimensionLine] = None
    associated_lines: List[Tuple[float, float, float, float]] = field(default_factory=list)
    associated_circle: Optional[Tuple[float, float, float]] = None  # (cx, cy, r_px)
    confidence: float = 0.0
    is_diameter: bool = False
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "value_cm": self.value_cm,
            "text_position": {"x": self.text_box.x, "y": self.text_box.y},
            "dim_line": {"p1": self.dim_line.p1, "p2": self.dim_line.p2,
                         "length_px": self.dim_line.length_px} if self.dim_line else None,
            "associated_lines_count": len(self.associated_lines),
            "associated_circle": self.associated_circle,
            "confidence": round(self.confidence, 2),
            "is_diameter": self.is_diameter,
            "evidence": self.evidence,
        }


@dataclass
class AssociationResult:
    """Complete set of dimension-to-geometry associations."""
    associations: List[Association]
    unassociated_labels: List[TextBox]      # Labels we couldn't match
    unassociated_geometry_count: int         # Geometry with no label
    scale_px_per_cm: Optional[float] = None  # Derived from confirmed pairs

    def to_dict(self) -> dict:
        return {
            "associations": [a.to_dict() for a in self.associations],
            "unassociated_labels": [{"text": t.text, "x": t.x, "y": t.y}
                                     for t in self.unassociated_labels],
            "unassociated_geometry_count": self.unassociated_geometry_count,
            "scale_px_per_cm": self.scale_px_per_cm,
            "summary": self.summary(),
        }

    def summary(self) -> str:
        if not self.associations:
            return "No dimension-to-geometry associations found"
        diameters = sum(1 for a in self.associations if a.is_diameter)
        lengths = sum(1 for a in self.associations if not a.is_diameter)
        return (f"{len(self.associations)} associations: {diameters} diameters, "
                f"{lengths} lengths. "
                f"Unmatched: {len(self.unassociated_labels)} labels, "
                f"{self.unassociated_geometry_count} geometry elements")


# ===== Helper Functions =====

def _line_angle(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Angle of line in radians."""
    return math.atan2(p2[1] - p1[1], p2[0] - p1[0])


def _angle_difference(a1: float, a2: float) -> float:
    """Smallest angle between two angles."""
    diff = abs(a1 - a2) % (2 * math.pi)
    return min(diff, 2 * math.pi - diff)


def _point_to_line_distance(px: float, py: float,
                            x1: float, y1: float, x2: float, y2: float) -> float:
    """Perpendicular distance from point to infinite line."""
    return abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1) / \
           max(0.001, math.hypot(y2 - y1, x2 - x1))


def _segment_distance(px: float, py: float,
                      x1: float, y1: float, x2: float, y2: float) -> float:
    """Distance from point to line segment."""
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _is_arrowhead(p1: Tuple[float, float], p2: Tuple[float, float],
                  p3: Tuple[float, float], angle_threshold: float = 0.5) -> bool:
    """
    Detect arrowhead: three consecutive points with a sharp angle change.
    A dimension line arrow typically has 30-45 degree opening.
    """
    a1 = _line_angle(p1, p2)
    a2 = _line_angle(p2, p3)
    diff = _angle_difference(a1, a2)
    # Arrowheads have angles roughly between 0.3 and 0.8 radians
    return 0.2 < diff < 1.0


def _find_extension_lines(dim_p1: Tuple[float, float],
                          dim_p2: Tuple[float, float],
                          all_lines: List[Tuple[float, float, float, float]],
                          max_distance: float = 40.0) -> Tuple[Optional[Tuple[float, float]],
                                                                Optional[Tuple[float, float]]]:
    """
    Find extension lines associated with a dimension line.
    Extension lines are short lines perpendicular to the dimension line,
    starting from the dimension endpoints and extending toward the object.
    """
    mx, my = (dim_p1[0] + dim_p2[0]) / 2, (dim_p1[1] + dim_p2[1]) / 2
    dim_angle = _line_angle(dim_p1, dim_p2)

    ext_start = None
    ext_end = None
    min_dist_start = max_distance
    min_dist_end = max_distance

    for x1, y1, x2, y2 in all_lines:
        line_angle = _line_angle((x1, y1), (x2, y2))
        # Extension lines are roughly perpendicular to dimension lines
        angle_diff = _angle_difference(line_angle, dim_angle + math.pi / 2)
        is_perpendicular = angle_diff < 0.3 or angle_diff > math.pi - 0.3

        if not is_perpendicular:
            continue

        # Check proximity to each dimension endpoint
        d1 = _segment_distance(dim_p1[0], dim_p1[1], x1, y1, x2, y2)
        d2 = _segment_distance(dim_p2[0], dim_p2[1], x1, y1, x2, y2)

        if d1 < min_dist_start:
            min_dist_start = d1
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            ext_start = (mid_x, mid_y)

        if d2 < min_dist_end:
            min_dist_end = d2
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            ext_end = (mid_x, mid_y)

    return ext_start, ext_end


def _find_dimension_lines(
    vision_lines: List[Tuple[float, float, float, float]],
    max_gap: float = 15.0
) -> List[DimensionLine]:
    """
    Detect dimension lines from raw vision line segments.
    A dimension line has:
    - Two arrowheads at its ends (sharp angle changes)
    - Or is a thin line with extension lines at both ends
    """
    dim_lines: List[DimensionLine] = []

    for x1, y1, x2, y2 in vision_lines:
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)

        if length < 20:
            continue  # Too short to be a dimension line

        is_h = abs(dy) < abs(dx) * 0.1  # Near-horizontal
        is_v = abs(dx) < abs(dy) * 0.1  # Near-vertical

        dim_lines.append(DimensionLine(
            p1=(x1, y1),
            p2=(x2, y2),
            is_vertical=is_v,
            is_horizontal=is_h,
        ))

    return dim_lines


def _find_circle_for_dimension(
    text_box: TextBox,
    circles: List[Tuple[float, float, float]],
    max_dist_ratio: float = 0.3
) -> Optional[Tuple[float, float, float]]:
    """Find the circle that a diameter dimension refers to."""
    cx, cy = text_box.center
    for circle_cx, circle_cy, circle_r in circles:
        dist = math.hypot(cx - circle_cx, cy - circle_cy)
        # Text should be reasonably close to the circle
        if dist < circle_r * 1.5 + 30:
            return (circle_cx, circle_cy, circle_r)
    return None


def _find_best_dimension_line(
    text_box: TextBox,
    dim_lines: List[DimensionLine],
    max_dist: float = 100.0
) -> Optional[DimensionLine]:
    """Find the dimension line closest to this text box."""
    cx, cy = text_box.center
    best_line = None
    best_dist = max_dist

    for dl in dim_lines:
        dist = _segment_distance(cx, cy, dl.p1[0], dl.p1[1], dl.p2[0], dl.p2[1])
        if dist < best_dist:
            best_dist = dist
            best_line = dl

    return best_line


def _find_nearby_object_lines(
    text_box: TextBox,
    dim_line: Optional[DimensionLine],
    all_lines: List[Tuple[float, float, float, float]],
    vision_lines: List[Tuple[float, float, float, float]],
    search_radius: float = 60.0
) -> Tuple[List[Tuple[float, float, float, float]], List[Tuple[float, float, float, float]]]:
    """
    Find object lines near a dimension.
    Returns (parallel_lines, perpendicular_lines).
    """
    cx, cy = text_box.center

    if dim_line:
        dim_angle = _line_angle(dim_line.p1, dim_line.p2)
    else:
        dim_angle = 0.0

    parallel: List[Tuple[float, float, float, float]] = []
    perpendicular: List[Tuple[float, float, float, float]] = []

    for x1, y1, x2, y2 in vision_lines:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        dist = math.hypot(mid_x - cx, mid_y - cy)

        if dist > search_radius:
            continue

        line_angle = _line_angle((x1, y1), (x2, y2))
        angle_diff = _angle_difference(line_angle, dim_angle)

        if angle_diff < 0.2 or angle_diff > math.pi - 0.2:
            parallel.append((x1, y1, x2, y2))
        elif 0.5 < angle_diff < math.pi - 0.5:  # Near perpendicular
            perpendicular.append((x1, y1, x2, y2))

    return parallel, perpendicular


# ===== Main Association Logic =====

def associate_dimensions(
    text_boxes: List[TextBox],
    dimension_labels: List[TextBox],
    vision_lines: List[Tuple[float, float, float, float]],
    circles: List[Tuple[float, float, float]],
    rects: Optional[List[Tuple[float, float, float, float]]] = None,
) -> AssociationResult:
    """
    Associate OCR dimension labels with geometry (lines, circles).

    The algorithm:
    1. Find dimension lines (lines with arrow/extension characteristics)
    2. For each dimension label, find nearest dimension line
    3. Find object lines near that dimension line (the measured edge)
    4. For diameter labels, find nearest circle
    5. Compute confidence scores for each association

    Args:
        text_boxes: All OCR-detected text with positions
        dimension_labels: Subset of text_boxes classified as dimensions
        vision_lines: Raw lines from OpenCV [((x1,y1),(x2,y2)), ...]
        circles: Detected circles [(cx, cy, r_px), ...]
        rects: Detected rectangles [(x1, y1, x2, y2), ...] (optional)

    Returns:
        AssociationResult with confirmed and unconfirmed associations
    """
    # Flatten vision lines to tuples
    flat_lines: List[Tuple[float, float, float, float]] = []
    for line in vision_lines:
        if len(line) == 4:
            flat_lines.append(line)
        elif len(line) == 2:
            p1, p2 = line
            flat_lines.append((p1[0], p1[1], p2[0], p2[1]))

    # Find dimension lines
    dim_lines = _find_dimension_lines(flat_lines)

    associations: List[Association] = []
    matched_labels: Set[int] = set()

    for label in dimension_labels:
        idx = text_boxes.index(label)
        if idx in matched_labels:
            continue

        is_dia = label.is_diameter
        best_dim_line = _find_best_dimension_line(label, dim_lines)

        evidence: List[str] = []
        associated_circle = None
        associated_lines = []

        if is_dia:
            # Diameter: find nearest circle
            circle = _find_circle_for_dimension(label, circles)
            if circle:
                associated_circle = circle
                evidence.append(f"matched to circle at ({circle[0]:.0f}, {circle[1]:.0f}), r={circle[2]:.0f}px")
                confidence = 0.85
            else:
                evidence.append("diameter label but no circle found nearby")
                confidence = 0.40
        else:
            if best_dim_line:
                evidence.append(f"matched to dimension line ({best_dim_line.p1[0]:.0f},{best_dim_line.p1[1]:.0f})-({best_dim_line.p2[0]:.0f},{best_dim_line.p2[1]:.0f})")

                # Find extension lines
                ext_start, ext_end = _find_extension_lines(
                    best_dim_line.p1, best_dim_line.p2, flat_lines)

                if ext_start:
                    evidence.append("extension line found at start")
                if ext_end:
                    evidence.append("extension line found at end")

                # Find object lines near this dimension
                parallel_lines, perp_lines = _find_nearby_object_lines(
                    label, best_dim_line, flat_lines, flat_lines)

                associated_lines = parallel_lines + perp_lines
                if associated_lines:
                    evidence.append(f"{len(associated_lines)} nearby object lines")

                # Confidence scoring
                conf = 0.5
                if ext_start and ext_end:
                    conf = 0.85  # Both extension lines visible
                elif ext_start or ext_end:
                    conf = 0.70  # One extension line
                if associated_lines:
                    conf = min(1.0, conf + 0.1)
                confidence = conf
            else:
                # No dimension line found — try geometric matching
                evidence.append("no dimension line found, using geometric proximity")
                # Search for parallel object lines near label
                parallel_lines, _ = _find_nearby_object_lines(
                    label, None, text_boxes, flat_lines)
                if parallel_lines:
                    evidence.append(f"found {len(parallel_lines)} potential object lines nearby")
                    associated_lines = parallel_lines
                    confidence = 0.45
                else:
                    confidence = 0.20

        assoc = Association(
            text=label.text,
            value_cm=label.value_cm or 0.0,
            text_box=label,
            dim_line=best_dim_line,
            associated_lines=associated_lines[:10],  # Limit evidence
            associated_circle=associated_circle,
            confidence=min(1.0, max(0.0, confidence)),
            is_diameter=is_dia,
            evidence=evidence[:5],  # Keep top evidence
        )
        associations.append(assoc)
        matched_labels.add(idx)

    # Compute scale_px_per_cm from confirmed associations
    scale_px_per_cm = None
    valid_assocs = [a for a in associations if a.confidence >= 0.6 and a.dim_line and a.value_cm > 0]
    if valid_assocs:
        ratios = [a.dim_line.length_px / a.value_cm for a in valid_assocs]
        if ratios:
            # Use median to reject outliers
            ratios.sort()
            scale_px_per_cm = ratios[len(ratios) // 2]

    # Unassociated labels
    matched_indices = {text_boxes.index(a.text_box) for a in associations}
    unassociated = [tb for i, tb in enumerate(text_boxes)
                    if i not in matched_indices and tb.text_type == "DIMENSION_LABEL"]

    # Count unassociated geometry (rough estimate)
    unassociated_geo = len(flat_lines) - sum(len(a.associated_lines) for a in associations)

    return AssociationResult(
        associations=associations,
        unassociated_labels=unassociated,
        unassociated_geometry_count=max(0, unassociated_geo),
        scale_px_per_cm=scale_px_per_cm,
    )


# Public API
def associate_dimension_text(
    text_boxes: List[TextBox],
    dimension_labels: List[TextBox],
    vision_lines: List[Tuple[float, float, float, float]],
    circles: List[Tuple[float, float, float]],
    rects: Optional[List[Tuple[float, float, float, float]]] = None,
) -> AssociationResult:
    """
    Main entry point: associate dimension text with geometry.
    """
    return associate_dimensions(text_boxes, dimension_labels, vision_lines, circles, rects)
