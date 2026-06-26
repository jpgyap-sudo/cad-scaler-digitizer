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
import statistics
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


# ===== Multi-Factor Scoring System =====

def _detect_arrow_direction(
    p1: Tuple[float, float], p2: Tuple[float, float],
    vision_lines: List[Tuple[float, float, float, float]],
    search_radius: float = 30.0,
) -> Optional[Tuple[float, float]]:
    """Detect which direction the arrowhead points from a dimension endpoint.
    Returns a unit direction vector (dx, dy) or None if no arrow found."""
    best_dir = None
    best_score = 0.0

    for x1, y1, x2, y2 in vision_lines:
        # Check if this short line originates near p1
        d1 = math.hypot(x1 - p1[0], y1 - p1[1])
        d2 = math.hypot(x2 - p1[0], y2 - p1[1])
        if min(d1, d2) > search_radius:
            continue

        # Get the direction away from the endpoint
        if d1 < d2:
            dx, dy = x2 - x1, y2 - y1
        else:
            dx, dy = x1 - x2, y1 - y2

        length = math.hypot(dx, dy) or 0.001
        dx, dy = dx / length, dy / length

        # Arrow lines should point away from the dimension line
        dim_dx = p2[0] - p1[0]
        dim_dy = p2[1] - p1[1]
        dim_len = math.hypot(dim_dx, dim_dy) or 0.001
        dim_dx, dim_dy = dim_dx / dim_len, dim_dy / dim_len

        # Arrow should be roughly perpendicular to the dimension line (cos ~= 0)
        dot = abs(dx * dim_dx + dy * dim_dy)
        perp_score = 1.0 - min(1.0, dot * 2)  # High when perpendicular

        if perp_score > best_score:
            best_score = perp_score
            best_dir = (dx, dy)

    return best_dir if best_score > 0.3 else None


def _text_orientation_score(
    text_box: 'TextBox',
    dim_line: 'DimensionLine',
) -> float:
    """Score how well the text orientation aligns with the dimension line.
    Returns 0.0-1.0 where 1.0 = perfectly aligned."""
    dim_angle = _line_angle(dim_line.p1, dim_line.p2)

    # Text orientation: assume horizontal (0 rad) or aligned with dimension line
    text_angle = getattr(text_box, 'angle', 0.0) or 0.0

    # Nomalize both to [0, pi/2]
    def norm_angle(a):
        a = abs(a) % math.pi
        if a > math.pi / 2:
            a = math.pi - a
        return a

    text_norm = norm_angle(text_angle)
    dim_norm = norm_angle(dim_angle)

    # Score: 1.0 if aligned, 0.0 if perpendicular
    diff = abs(text_norm - dim_norm)
    return max(0.0, 1.0 - diff / (math.pi / 2))


def _distance_score(
    text_box: 'TextBox',
    dim_line: 'DimensionLine',
    max_dist: float = 100.0,
) -> float:
    """Score based on distance between text and dimension line.
    Returns 0.0-1.0 where 1.0 = very close."""
    cx, cy = text_box.center
    dist = _segment_distance(cx, cy, dim_line.p1[0], dim_line.p1[1],
                              dim_line.p2[0], dim_line.p2[1])
    return max(0.0, 1.0 - (dist / max_dist))


def _angle_alignment_score(
    text_box: 'TextBox',
    dim_line: 'DimensionLine',
    object_lines: List[Tuple[float, float, float, float]],
) -> float:
    """Score how well the dimension line is parallel to the measured object edge.
    Returns 0.0-1.0 where 1.0 = perfectly parallel."""
    if not object_lines:
        return 0.5  # Neutral if no object lines

    dim_angle = _line_angle(dim_line.p1, dim_line.p2)

    # Average angle of nearby object lines
    obj_angles = []
    for x1, y1, x2, y2 in object_lines:
        obj_angles.append(_line_angle((x1, y1), (x2, y2)))

    if not obj_angles:
        return 0.5

    # Find the alignment between dimension line and nearest object line angle
    best_alignment = 0.0
    for oa in obj_angles:
        diff = _angle_difference(dim_angle, oa)
        # Parallel or anti-parallel = good alignment
        alignment = 1.0 - min(diff, math.pi - diff) / (math.pi / 4)
        best_alignment = max(best_alignment, alignment)

    return max(0.0, min(1.0, best_alignment))


def _arrow_presence_score(
    dim_line: 'DimensionLine',
    vision_lines: List[Tuple[float, float, float, float]],
) -> float:
    """Score based on arrowhead presence at dimension line endpoints.
    Returns 0.0-1.0 where 1.0 = arrows at both ends."""
    arrow1 = _detect_arrow_direction(dim_line.p1, dim_line.p2, vision_lines)
    arrow2 = _detect_arrow_direction(dim_line.p2, dim_line.p1, vision_lines)

    if arrow1 and arrow2:
        return 1.0
    elif arrow1 or arrow2:
        return 0.6
    return 0.2


def _validate_value_consistency(
    value_cm: float,
    dim_line: 'DimensionLine',
    is_diameter: bool,
    associated_circle: Optional[Tuple[float, float, float]] = None,
    px_per_cm_estimate: Optional[float] = 2.0,
) -> Tuple[float, str]:
    """Check whether the OCR value is consistent with the pixel measurement.
    Returns (consistency_score, evidence_string)."""
    if value_cm <= 0 or px_per_cm_estimate is None:
        return 0.3, "no scale estimate available"

    if is_diameter and associated_circle:
        _, _, r_px = associated_circle
        pixel_dia = r_px * 2
        expected_cm = pixel_dia / px_per_cm_estimate
    elif dim_line:
        pixel_len = dim_line.length_px
        expected_cm = pixel_len / px_per_cm_estimate
    else:
        return 0.3, "no pixel measurement to compare"

    if expected_cm <= 0:
        return 0.3, "zero pixel measurement"

    # Compare OCR value to pixel-derived value
    ratio = value_cm / max(expected_cm, 0.01)
    if 0.7 <= ratio <= 1.4:
        # Good agreement
        error = abs(1.0 - ratio)
        score = max(0.0, 1.0 - error * 2)
        evidence = f"value consistent with pixel measurement (ratio {ratio:.2f})"
    elif 0.5 <= ratio <= 2.0:
        score = 0.4
        evidence = f"value somewhat off from pixel measurement (ratio {ratio:.2f})"
    else:
        score = 0.1
        evidence = f"value drastically different from pixel measurement (ratio {ratio:.2f}) — likely wrong leader"

    return score, evidence


def _score_association(
    text_box: 'TextBox',
    dim_line: 'DimensionLine',
    vision_lines: List[Tuple[float, float, float, float]],
    object_lines: List[Tuple[float, float, float, float]],
    value_cm: float,
    is_diameter: bool,
    associated_circle: Optional[Tuple[float, float, float]],
    ext_start: Optional[Tuple[float, float]],
    ext_end: Optional[Tuple[float, float]],
    px_per_cm_estimate: Optional[float] = None,
) -> Tuple[float, List[str]]:
    """Compute a weighted multi-factor confidence score for a dimension association.

    Weights:
        distance:           0.25  — how close text is to the dimension line
        angle_alignment:    0.20  — how parallel dim line is to object edge
        arrow_presence:     0.20  — arrowheads at both ends
        text_orientation:   0.10  — text rotation matches drawing
        value_consistency:  0.15  — OCR value matches pixel measurement
        extension_lines:    0.10  — extension lines found

    Returns (confidence 0.0-1.0, evidence_list).
    """
    evidence: List[str] = []
    score = 0.0

    # 1. Distance score (25%)
    dist_score = _distance_score(text_box, dim_line)
    score += dist_score * 0.25
    if dist_score < 0.5:
        evidence.append(f"text far from dim line (dist={dist_score:.2f})")

    # 2. Angle alignment score (20%)
    angle_score = _angle_alignment_score(text_box, dim_line, object_lines)
    score += angle_score * 0.20
    if angle_score < 0.5:
        evidence.append(f"poor angle alignment ({angle_score:.2f})")

    # 3. Arrow presence score (20%)
    arrow_score = _arrow_presence_score(dim_line, vision_lines)
    score += arrow_score * 0.20
    if arrow_score >= 1.0:
        evidence.append("arrows at both ends of dimension line")
    elif arrow_score >= 0.6:
        evidence.append("arrow at one end of dimension line")
    else:
        evidence.append("no clear arrowheads on dimension line")

    # 4. Text orientation score (10%)
    orient_score = _text_orientation_score(text_box, dim_line)
    score += orient_score * 0.10

    # 5. Value consistency score (15%)
    val_score, val_evidence = _validate_value_consistency(
        value_cm, dim_line, is_diameter, associated_circle, px_per_cm_estimate)
    score += val_score * 0.15
    evidence.append(val_evidence)

    # 6. Extension lines score (10%)
    if ext_start and ext_end:
        ext_score = 1.0
        evidence.append("extension lines at both ends")
    elif ext_start or ext_end:
        ext_score = 0.6
        evidence.append("extension line at one end")
    else:
        ext_score = 0.2
    score += ext_score * 0.10

    return min(1.0, max(0.0, score)), evidence


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

    # Pre-compute a rough px_per_cm estimate for value-consistency scoring
    # Use the median ratio from all usable dim lines
    rough_scale_estimates = []
    for dl in dim_lines:
        if dl.length_px > 30:
            rough_scale_estimates.append(dl.length_px)
    rough_px_per_cm = statistics.median(rough_scale_estimates) / 80.0 if rough_scale_estimates else None

    for label in dimension_labels:
        idx = text_boxes.index(label)
        if idx in matched_labels:
            continue

        is_dia = label.is_diameter
        best_dim_line = _find_best_dimension_line(label, dim_lines)

        evidence: List[str] = []
        associated_circle = None
        associated_lines = []
        ext_start = None
        ext_end = None

        if is_dia:
            # Diameter: find nearest circle
            circle = _find_circle_for_dimension(label, circles)
            if circle:
                associated_circle = circle
                evidence.append(f"matched to circle at ({circle[0]:.0f}, {circle[1]:.0f}), r={circle[2]:.0f}px")
            else:
                evidence.append("diameter label but no circle found nearby")

        if best_dim_line:
            evidence.append(f"matched to dimension line ({best_dim_line.p1[0]:.0f},{best_dim_line.p1[1]:.0f})-({best_dim_line.p2[0]:.0f},{best_dim_line.p2[1]:.0f})")

            # Find extension lines
            ext_start, ext_end = _find_extension_lines(
                best_dim_line.p1, best_dim_line.p2, flat_lines)

            # Find object lines near this dimension
            parallel_lines, perp_lines = _find_nearby_object_lines(
                label, best_dim_line, flat_lines, flat_lines)
            associated_lines = parallel_lines + perp_lines
            if associated_lines:
                evidence.append(f"{len(associated_lines)} nearby object lines")
        else:
            # No dimension line found — try geometric matching
            evidence.append("no dimension line found, using geometric proximity")
            parallel_lines, _ = _find_nearby_object_lines(
                label, None, flat_lines, flat_lines)
            if parallel_lines:
                evidence.append(f"found {len(parallel_lines)} potential object lines nearby")
                associated_lines = parallel_lines

        # Compute confidence via multi-factor scoring (upgraded from simple proximity)
        if best_dim_line:
            confidence, score_evidence = _score_association(
                text_box=label,
                dim_line=best_dim_line,
                vision_lines=flat_lines,
                object_lines=associated_lines,
                value_cm=label.value_cm or 0.0,
                is_diameter=is_dia,
                associated_circle=associated_circle,
                ext_start=ext_start,
                ext_end=ext_end,
                px_per_cm_estimate=rough_px_per_cm,
            )
            evidence.extend(score_evidence)
        elif is_dia and associated_circle:
            # Diameter with circle but no dimension line: use circle-based scoring
            confidence = 0.85 if associated_circle else 0.40
        elif associated_lines:
            # Object lines found but no dim line: moderate confidence
            confidence = 0.45
        else:
            # Nothing matched: very low confidence
            confidence = 0.20

        assoc = Association(
            text=label.text,
            value_cm=label.value_cm or 0.0,
            text_box=label,
            dim_line=best_dim_line,
            associated_lines=associated_lines[:10],
            associated_circle=associated_circle,
            confidence=min(1.0, max(0.0, confidence)),
            is_diameter=is_dia,
            evidence=evidence[:8],
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
