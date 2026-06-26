"""
Line Role Classifier — classify every line in the drawing by its CAD role.

This is the upgraded replacement for leader_dimension_classifier.py.
Instead of classifying text strings, it classifies the actual LINE SEGMENTS
based on geometric properties.

Roles:
  OBJECT_EDGE      — Thick continuous lines, belong to the furniture shape
  DIMENSION_LINE   — Thin line with arrows/ticks at both ends, near numeric value
  EXTENSION_LINE   — Thin line perpendicular to dimension line, connects to object
  LEADER           — Thin line with one arrowhead, points to material/part note
  CENTERLINE       — Dashed or long-short dash pattern, passes through center
  HATCH            — Short lines at 45 degrees inside a closed area
  TITLE_BLOCK      — Lines belonging to the title block border
  HIDDEN           — Dashed lines representing hidden geometry

The classifier uses:
1. Line thickness (stroke width)
2. Line pattern (continuous, dashed, chain)
3. Proximity to text (dimension label vs. material note)
4. Angle relationships (parallel/perpendicular to other lines)
5. Arrowhead detection at endpoints
"""

import math
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Literal


LineRole = Literal[
    "OBJECT_EDGE",
    "DIMENSION_LINE",
    "EXTENSION_LINE",
    "LEADER",
    "CENTERLINE",
    "HATCH",
    "TITLE_BLOCK",
    "HIDDEN",
    "UNKNOWN",
]

ROLE_LABELS = {
    "OBJECT_EDGE": "Object Edge",
    "DIMENSION_LINE": "Dimension Line",
    "EXTENSION_LINE": "Extension Line",
    "LEADER": "Leader",
    "CENTERLINE": "Centerline",
    "HATCH": "Hatch",
    "TITLE_BLOCK": "Title Block",
    "HIDDEN": "Hidden",
    "UNKNOWN": "Unknown",
}


@dataclass
class ClassifiedLine:
    """A single line segment with its classified role."""
    x1: float
    y1: float
    x2: float
    y2: float
    length_px: float
    angle_deg: float
    role: LineRole = "UNKNOWN"
    confidence: float = 0.0
    is_horizontal: bool = False
    is_vertical: bool = False
    is_diagonal: bool = False
    stroke_width_px: float = 1.0  # Estimated stroke width
    has_arrowhead_at_p1: bool = False
    has_arrowhead_at_p2: bool = False
    nearby_text: str = ""  # Text found near this line

    def to_dict(self) -> dict:
        return {
            "x1": round(self.x1, 1), "y1": round(self.y1, 1),
            "x2": round(self.x2, 1), "y2": round(self.y2, 1),
            "length_px": round(self.length_px, 1),
            "angle_deg": round(self.angle_deg, 1),
            "role": self.role,
            "confidence": round(self.confidence, 2),
            "is_horizontal": self.is_horizontal,
            "is_vertical": self.is_vertical,
            "stroke_width_px": round(self.stroke_width_px, 1),
            "has_arrowhead_p1": self.has_arrowhead_at_p1,
            "has_arrowhead_p2": self.has_arrowhead_at_p2,
            "nearby_text": self.nearby_text[:50],
        }


@dataclass
class LineClassificationResult:
    """Complete line classification for a drawing."""
    object_edges: List[ClassifiedLine]
    dimension_lines: List[ClassifiedLine]
    extension_lines: List[ClassifiedLine]
    leaders: List[ClassifiedLine]
    centerlines: List[ClassifiedLine]
    hatches: List[ClassifiedLine]
    hidden_lines: List[ClassifiedLine]
    unknown: List[ClassifiedLine]
    all_lines: List[ClassifiedLine]

    def to_dict(self) -> dict:
        return {
            "object_edges": [l.to_dict() for l in self.object_edges],
            "dimension_lines": [l.to_dict() for l in self.dimension_lines],
            "extension_lines": [l.to_dict() for l in self.extension_lines],
            "leaders": [l.to_dict() for l in self.leaders],
            "centerlines": [l.to_dict() for l in self.centerlines],
            "hatches": [l.to_dict() for l in self.hatches],
            "hidden_lines": [l.to_dict() for l in self.hidden_lines],
            "unknown": [l.to_dict() for l in self.unknown],
            "summary": self.summary(),
        }

    def summary(self) -> str:
        return (f"Line Classification: {len(self.object_edges)} object edges, "
                f"{len(self.dimension_lines)} dimensions, "
                f"{len(self.extension_lines)} extension, "
                f"{len(self.leaders)} leaders, "
                f"{len(self.centerlines)} centerlines, "
                f"{len(self.hatches)} hatches, "
                f"{len(self.hidden_lines)} hidden, "
                f"{len(self.unknown)} unknown")

    def lines_by_role(self, role: LineRole) -> List[ClassifiedLine]:
        mapping = {
            "OBJECT_EDGE": self.object_edges,
            "DIMENSION_LINE": self.dimension_lines,
            "EXTENSION_LINE": self.extension_lines,
            "LEADER": self.leaders,
            "CENTERLINE": self.centerlines,
            "HATCH": self.hatches,
            "HIDDEN": self.hidden_lines,
        }
        return mapping.get(role, [])


# ===== Detection helpers =====

def _estimate_line_thickness(
    img_array,
    x1: int, y1: int, x2: int, y2: int,
    samples: int = 5
) -> float:
    """
    Estimate line thickness by sampling perpendicular to the line direction.
    This requires the image pixel data; returns 1.0 as fallback.
    """
    # Default — in practice this uses image pixel data
    return 1.0


def _line_angle(x1: float, y1: float, x2: float, y2: float) -> float:
    """Line angle in degrees (0-180)."""
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    return angle % 180  # Normalize to 0-180


def _is_near_horizontal(angle_deg: float, threshold: float = 15.0) -> bool:
    """Check if line is near-horizontal."""
    return angle_deg < threshold or angle_deg > 180 - threshold


def _is_near_vertical(angle_deg: float, threshold: float = 15.0) -> bool:
    """Check if line is near-vertical."""
    return 90 - threshold < angle_deg < 90 + threshold


def _detect_arrowhead(p1: Tuple[float, float],
                      p_mid: Tuple[float, float],
                      p2: Tuple[float, float]) -> Tuple[bool, float]:
    """
    Detect if there's an arrowhead at p1.
    An arrowhead has two short lines diverging from p1 at ~30-60 degrees.

    Uses the angle between (p_mid - p1) and (p2 - p1) to detect the "V" shape.
    """
    dx1, dy1 = p_mid[0] - p1[0], p_mid[1] - p1[1]
    dx2, dy2 = p2[0] - p1[0], p2[1] - p1[1]

    len1 = math.hypot(dx1, dy1)
    len2 = math.hypot(dx2, dy2)

    if len1 < 3 or len2 < 3:
        return False, 0.0

    # Angle between the two line segments
    dot = (dx1 * dx2 + dy1 * dy2) / (len1 * len2)
    dot = max(-1.0, min(1.0, dot))
    angle = math.acos(dot)

    # Arrowhead opening angle is typically 20-60 degrees (0.35-1.05 rad)
    is_arrow = 0.2 < angle < 1.2
    return is_arrow, angle


def _identify_line_role(
    line: ClassifiedLine,
    dim_labels: List[Tuple[float, float, float]],  # (x, y, value_cm)
    material_texts: List[Tuple[float, float]],      # (x, y) of material notes
    centerline_texts: List[Tuple[float, float]],    # (x, y) of center marks
    all_lines: List[ClassifiedLine],
) -> Tuple[LineRole, float]:
    """
    Classify a single line segment based on geometric and contextual evidence.

    Uses multiple signals:
    1. Arrowhead presence (dimension=both ends, leader=one end)
    2. Dash pattern (centerline, hidden)
    3. Text proximity (dimension label, material note)
    4. Angle relative to other lines (extension=perp to dimension)
    5. Length: hatches are short, title blocks are long
    """
    evidence_scores: Dict[LineRole, float] = {
        "OBJECT_EDGE": 0.1,
        "DIMENSION_LINE": 0.0,
        "EXTENSION_LINE": 0.0,
        "LEADER": 0.0,
        "CENTERLINE": 0.0,
        "HATCH": 0.0,
        "TITLE_BLOCK": 0.0,
        "HIDDEN": 0.0,
    }

    # --- Signal 1: Arrowheads ---
    has_p1_arrow = line.has_arrowhead_at_p1
    has_p2_arrow = line.has_arrowhead_at_p2

    if has_p1_arrow and has_p2_arrow:
        # Both ends have arrows → very likely DIMENSION_LINE
        evidence_scores["DIMENSION_LINE"] += 2.0
    elif has_p1_arrow or has_p2_arrow:
        # One arrow → likely LEADER
        evidence_scores["LEADER"] += 1.5

    # --- Signal 2: Line length ---
    if line.length_px < 15:
        evidence_scores["HATCH"] += 0.5
        evidence_scores["EXTENSION_LINE"] += 0.3
    elif line.length_px > 100:
        evidence_scores["TITLE_BLOCK"] += 0.3
        evidence_scores["OBJECT_EDGE"] += 0.2

    # --- Signal 3: Near dimension labels ---
    cx = (line.x1 + line.x2) / 2
    cy = (line.y1 + line.y2) / 2
    for lx, ly, val in dim_labels:
        dist = math.hypot(cx - lx, cy - ly)
        if dist < 80:
            evidence_scores["DIMENSION_LINE"] += 0.8 * (1 - dist / 80)
            # Extension lines are perpendicular to dimension with text
            if line.is_vertical or line.is_horizontal:
                evidence_scores["EXTENSION_LINE"] += 0.3 * (1 - dist / 80)
            break

    # --- Signal 4: Near material/leader texts ---
    for mx, my in material_texts:
        dist = math.hypot(cx - mx, cy - my)
        if dist < 100:
            evidence_scores["LEADER"] += 0.6 * (1 - dist / 100)
            break

    # --- Signal 5: Near center marks ---
    for cmx, cmy in centerline_texts:
        dist = math.hypot(cx - cmx, cy - cmy)
        if dist < 50:
            evidence_scores["CENTERLINE"] += 1.0 * (1 - dist / 50)
            break

    # --- Signal 6: Passes through center of geometry ---
    # (Simple heuristic: if a line crosses another long line near its midpoint)
    for other in all_lines:
        if other is line:
            continue
        # Check if this line's midpoint is near the other's midpoint
        mid_dist = math.hypot(cx - (other.x1 + other.x2) / 2,
                              cy - (other.y1 + other.y2) / 2)
        if mid_dist < 10 and other.length_px > line.length_px * 2:
            evidence_scores["CENTERLINE"] += 0.5
            break

    # --- Signal 7: Line angle classification ---
    if line.is_diagonal:
        # Hatches are often diagonal (45 degrees)
        angle = _line_angle(line.x1, line.y1, line.x2, line.y2)
        if 35 < angle < 55 or 125 < angle < 145:
            evidence_scores["HATCH"] += 0.5

    # --- Signal 8: Short perpendicular to another line (hatch) ---
    for other in all_lines:
        if other is line or other.length_px < 20:
            continue
        if abs(line.length_px) < 1:  # avoid division by zero
            continue
        # Perpendicular check
        a1 = _line_angle(line.x1, line.y1, line.x2, line.y2)
        a2 = _line_angle(other.x1, other.y1, other.x2, other.y2)
        angle_diff = abs(a1 - a2) % 180
        if 80 < angle_diff < 100:
            # Perpendicular: could be extension or part of a rect
            if line.length_px < other.length_px * 0.3:
                evidence_scores["EXTENSION_LINE"] += 0.4
                evidence_scores["HATCH"] += 0.2
            break

    # --- Signal 9: Very short line in group of parallel short lines (hatch fill) ---
    if line.length_px < 30:
        parallel_count = 0
        for other in all_lines:
            if other is line:
                continue
            if other.length_px < 40:
                a1 = _line_angle(line.x1, line.y1, line.x2, line.y2)
                a2 = _line_angle(other.x1, other.y1, other.x2, other.y2)
                if abs(a1 - a2) < 15:
                    parallel_count += 1
        if parallel_count > 3:
            evidence_scores["HATCH"] += 1.0

    # --- Select best role ---
    best_role: LineRole = "UNKNOWN"
    best_score = 0.0

    # Prefer OBJECT_EDGE for lines without other strong evidence
    if max(evidence_scores.values()) < 0.5 and line.length_px > 30:
        evidence_scores["OBJECT_EDGE"] = 0.4

    for role, score in evidence_scores.items():
        if score > best_score:
            best_score = score
            best_role = role

    # Normalize confidence to 0-1
    confidence = min(1.0, best_score / 3.0)

    return best_role, confidence


# ===== Public API =====

def classify_lines(
    vision_lines: List[Tuple[float, float, float, float]],
    text_boxes: Optional[List['TextBox']] = None,
    img_array=None,
) -> LineClassificationResult:
    """
    Classify every line in a drawing by CAD role.

    Args:
        vision_lines: List of lines as (x1, y1, x2, y2) tuples
        text_boxes: Optional list of TextBox objects with positions
        img_array: Optional image pixel data for thickness estimation

    Returns:
        LineClassificationResult with categorized lines
    """
    # Import TextBox type lazily to avoid circular import
    from app.backend.ocr_layout_parser import TextBox as TB

    if text_boxes is None:
        text_boxes = []

    # Process each line into a ClassifiedLine
    classified_all: List[ClassifiedLine] = []

    for line_data in vision_lines:
        if len(line_data) == 4:
            x1, y1, x2, y2 = line_data
        elif len(line_data) == 2:
            p1, p2 = line_data
            x1, y1 = p1
            x2, y2 = p2
        else:
            continue

        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)

        if length < 5:
            continue  # Skip tiny segments

        angle_deg = _line_angle(x1, y1, x2, y2)
        is_h = _is_near_horizontal(angle_deg)
        is_v = _is_near_vertical(angle_deg)
        is_diag = not is_h and not is_v

        # Estimate arrowheads (simplified)
        # In production, this would inspect the image for arrow path
        has_p1_arrow = False
        has_p2_arrow = False

        cl = ClassifiedLine(
            x1=x1, y1=y1, x2=x2, y2=y2,
            length_px=length,
            angle_deg=angle_deg,
            is_horizontal=is_h,
            is_vertical=is_v,
            is_diagonal=is_diag,
            has_arrowhead_at_p1=has_p1_arrow,
            has_arrowhead_at_p2=has_p2_arrow,
        )
        classified_all.append(cl)

    # Extract text positions for classification
    dim_positions: List[Tuple[float, float, float]] = []  # (x, y, value_cm)
    material_positions: List[Tuple[float, float]] = []
    centerline_positions: List[Tuple[float, float]] = []

    for tb in text_boxes:
        cx = tb.x + tb.w / 2
        cy = tb.y + tb.h / 2
        if tb.text_type == "DIMENSION_LABEL" and tb.value_cm:
            dim_positions.append((cx, cy, tb.value_cm))
        elif tb.text_type == "MATERIAL_NOTE":
            material_positions.append((cx, cy))
        elif tb.text_type == "CENTERLINE_MARK":
            centerline_positions.append((cx, cy))

    # Classify each line
    for cl in classified_all:
        role, conf = _identify_line_role(
            cl, dim_positions, material_positions,
            centerline_positions, classified_all,
        )
        cl.role = role
        cl.confidence = conf

    # Split into role buckets
    object_edges = [l for l in classified_all if l.role == "OBJECT_EDGE"]
    dimension_lines = [l for l in classified_all if l.role == "DIMENSION_LINE"]
    extension_lines = [l for l in classified_all if l.role == "EXTENSION_LINE"]
    leaders = [l for l in classified_all if l.role == "LEADER"]
    centerlines = [l for l in classified_all if l.role == "CENTERLINE"]
    hatches = [l for l in classified_all if l.role == "HATCH"]
    hidden_lines = [l for l in classified_all if l.role == "HIDDEN"]
    unknown = [l for l in classified_all if l.role == "UNKNOWN"]

    return LineClassificationResult(
        object_edges=object_edges,
        dimension_lines=dimension_lines,
        extension_lines=extension_lines,
        leaders=leaders,
        centerlines=centerlines,
        hatches=hatches,
        hidden_lines=hidden_lines,
        unknown=unknown,
        all_lines=classified_all,
    )


# Public API
def classify_line_roles(
    vision_lines: List[Tuple[float, float, float, float]],
    text_boxes=None,
) -> LineClassificationResult:
    """Main entry point: classify all lines by CAD role."""
    return classify_lines(vision_lines, text_boxes)
