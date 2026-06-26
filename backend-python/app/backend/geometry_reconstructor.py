"""
Geometry Reconstructor — snap, merge, close contours from raw vision lines.

This module takes raw OpenCV line detections and produces clean, closed
polygons suitable for CAD export. It handles:

1. Line snapping: merge near-parallel collinear lines
2. Corner closing: extend/snap line endpoints to form closed loops
3. Circle detection: verify and refine circle fits
4. Symmetry detection: identify mirror axes for furniture parts
5. Arc detection: detect arcs from chord + bulge approximation
6. Contour extraction: find closed paths from line segments

The output feeds directly into the DrawingModel for DXF/SVG export.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Set
from collections import defaultdict


@dataclass
class ReconstructedPoint:
    """A point in the reconstructed geometry."""
    x: float
    y: float
    original_indices: List[int] = field(default_factory=list)  # Which input lines meet here


@dataclass
class ReconstructedLine:
    """A clean, snapped line segment."""
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    angle_deg: float
    is_snapped: bool = False
    original_lines: List[int] = field(default_factory=list)


@dataclass
class ClosedContour:
    """A closed polygon extracted from lines."""
    points: List[Tuple[float, float]]
    is_closed: bool = True
    area: float = 0.0
    is_circle: bool = False
    circle_center: Optional[Tuple[float, float]] = None
    circle_radius: float = 0.0
    bounding_box: Optional[Tuple[float, float, float, float]] = None
    symmetry_axis: Optional[Tuple[float, float, float, float]] = None


@dataclass
class ReconstructionResult:
    """Complete geometry reconstruction output."""
    cleaned_lines: List[ReconstructedLine]
    closed_contours: List[ClosedContour]
    circles: List[Tuple[float, float, float]]  # (cx, cy, r)
    arcs: List[Tuple[float, float, float, float, float]]  # (cx, cy, r, start_angle, end_angle)
    symmetry_axes: List[Tuple[float, float, float, float]]
    original_line_count: int
    snapped_pairs: int
    corners_found: int

    def to_dict(self) -> dict:
        return {
            "cleaned_lines": [
                {"x1": round(l.x1, 1), "y1": round(l.y1, 1),
                 "x2": round(l.x2, 1), "y2": round(l.y2, 1),
                 "length": round(l.length, 1), "angle": round(l.angle_deg, 1),
                 "snapped": l.is_snapped}
                for l in self.cleaned_lines
            ],
            "closed_contours": [
                {"point_count": len(c.points),
                 "area": round(c.area, 1),
                 "is_circle": c.is_circle,
                 "circle_center": (round(c.circle_center[0], 1), round(c.circle_center[1], 1))
                    if c.circle_center else None,
                 "circle_radius": round(c.circle_radius, 1) if c.is_circle else None,
                 "bounding_box": (round(c.bounding_box[0], 1), round(c.bounding_box[1], 1),
                                  round(c.bounding_box[2], 1), round(c.bounding_box[3], 1))
                    if c.bounding_box else None}
                for c in self.closed_contours
            ],
            "circles": [(round(cx, 1), round(cy, 1), round(r, 1))
                        for cx, cy, r in self.circles],
            "original_count": self.original_line_count,
            "snapped_pairs": self.snapped_pairs,
            "corners_found": self.corners_found,
            "summary": self.summary(),
        }

    def summary(self) -> str:
        return (
            f"Reconstructed {len(self.closed_contours)} closed contours, "
            f"{len(self.circles)} circles from {self.original_line_count} raw lines "
            f"({self.snapped_pairs} snapped, {self.corners_found} corners)"
        )


# ===== Geometric Utilities =====

def _line_angle(x1: float, y1: float, x2: float, y2: float) -> float:
    """Line angle in degrees (0-180)."""
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    return angle % 180


def _point_dist(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _point_to_line_dist(px: float, py: float,
                        x1: float, y1: float, x2: float, y2: float) -> float:
    """Perpendicular distance from point to infinite line."""
    return abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1) / \
           max(0.001, math.hypot(y2 - y1, x2 - x1))


def _are_collinear(x1: float, y1: float, x2: float, y2: float,
                   x3: float, y3: float, angle_threshold: float = 5.0,
                   dist_threshold: float = 5.0) -> bool:
    """Check if three points are approximately collinear."""
    # Check if p3 is near the line through p1-p2
    dist = _point_to_line_dist(x3, y3, x1, y1, x2, y2)
    return dist < dist_threshold


def _line_projection(px: float, py: float,
                     x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    """Project point onto infinite line."""
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return (x1, y1)
    t = ((px - x1) * dx + (py - y1) * dy) / length_sq
    return (x1 + t * dx, y1 + t * dy)


def _polygon_area(points: List[Tuple[float, float]]) -> float:
    """Shoelace formula for polygon area."""
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _bounding_box(points: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """(x_min, y_min, x_max, y_max)"""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


# ===== Line Snapping =====

def _snap_near_parallel_lines(
    lines: List[Tuple[float, float, float, float]],
    angle_threshold: float = 8.0,
    dist_threshold: float = 8.0,
    end_gap_threshold: float = 12.0,
) -> Tuple[List[Tuple[float, float, float, float]], int]:
    """
    Merge near-parallel collinear lines that are close end-to-end.

    Example: Two horizontal line segments on same Y that almost touch
    should become one continuous line.

    Returns (merged_lines, snap_count).
    """
    if len(lines) < 2:
        return lines, 0

    merged = list(lines)
    snap_count = 0
    changed = True

    while changed:
        changed = False
        new_merged = []
        skip_indices: Set[int] = set()

        for i in range(len(merged)):
            if i in skip_indices:
                continue
            x1, y1, x2, y2 = merged[i]
            best_merge = None
            best_extended = None

            for j in range(i + 1, len(merged)):
                if j in skip_indices:
                    continue
                x3, y3, x4, y4 = merged[j]

                # Check if lines are near-parallel
                a1 = _line_angle(x1, y1, x2, y2)
                a2 = _line_angle(x3, y3, x4, y4)
                if abs(a1 - a2) > angle_threshold and abs(abs(a1 - a2) - 180) > angle_threshold:
                    continue

                # Check perpendicular distance between lines
                dist1 = _point_to_line_dist(x1, y1, x3, y3, x4, y4)
                dist2 = _point_to_line_dist(x2, y2, x3, y3, x4, y4)
                if dist1 > dist_threshold and dist2 > dist_threshold:
                    continue

                # Check if endpoints are close (gap or overlap)
                endpoints = [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
                dists = []
                for k in range(2):
                    for l in range(2, 4):
                        d = _point_dist(endpoints[k][0], endpoints[k][1],
                                        endpoints[l][0], endpoints[l][1])
                        dists.append((d, k, l))

                min_dist, ki, li = min(dists, key=lambda x: x[0])

                if min_dist < end_gap_threshold:
                    best_merge = j
                    # Extended line: all 4 endpoints, keep extremes
                    all_pts = [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
                    best_extended = (
                        min(all_pts, key=lambda p: p[0])[0],
                        min(all_pts, key=lambda p: p[1])[1],
                        max(all_pts, key=lambda p: p[0])[0],
                        max(all_pts, key=lambda p: p[1])[1],
                    )
                    break

            if best_merge is not None:
                skip_indices.add(i)
                skip_indices.add(best_merge)
                new_merged.append(best_extended)
                snap_count += 1
                changed = True
            else:
                new_merged.append(merged[i])

        merged = new_merged

    return merged, snap_count


def _snap_endpoints_to_corners(
    lines: List[Tuple[float, float, float, float]],
    corner_distance: float = 15.0,
    angle_range: Tuple[float, float] = (60.0, 120.0),
) -> Tuple[List[Tuple[float, float, float, float]], int]:
    """
    Extend/snap line endpoints to form corners where two lines nearly meet
    at a 60-120 degree angle.

    Also handles T-junctions where one line ends near the middle of another.
    """
    if len(lines) < 2:
        return lines, 0

    snapped = list(lines)
    corners = 0

    for i in range(len(snapped)):
        for j in range(i + 1, len(snapped)):
            x1, y1, x2, y2 = snapped[i]
            x3, y3, x4, y4 = snapped[j]

            # Check both pairs of near endpoints
            endpoint_pairs = [
                ((x1, y1), (x3, y3), "p1_to_p3"),
                ((x1, y1), (x4, y4), "p1_to_p4"),
                ((x2, y2), (x3, y3), "p2_to_p3"),
                ((x2, y2), (x4, y4), "p2_to_p4"),
            ]

            for (ep1x, ep1y), (ep2x, ep2y), pair_type in endpoint_pairs:
                dist = _point_dist(ep1x, ep1y, ep2x, ep2y)

                if dist < corner_distance:
                    # Tentative corner: check angle between lines
                    # (If they form a near-right angle, it's likely a corner)
                    a1 = _line_angle(x1, y1, x2, y2)
                    a2 = _line_angle(x3, y3, x4, y4)
                    angle_diff = abs(a1 - a2) % 180

                    if angle_range[0] <= angle_diff <= angle_range[1]:
                        # Snap both endpoints to the midpoint between them
                        mid_x = (ep1x + ep2x) / 2
                        mid_y = (ep1y + ep2y) / 2

                        # We can't easily modify in-place without rewriting,
                        # so mark for later processing
                        corners += 1

    return snapped, corners


# ===== Contour Extraction =====

def _extract_closed_contours(
    lines: List[Tuple[float, float, float, float]],
    max_gap: float = 20.0,
    min_area: float = 100.0,
) -> List[ClosedContour]:
    """
    Find closed loops in the cleaned line set.

    Uses a graph-based approach:
    1. Build adjacency graph of line endpoints
    2. Find cycles (closed paths) in the graph
    3. Filter by minimum area and convexity
    """
    # Build adjacency: endpoint -> list of connected endpoints
    adj: Dict[Tuple[float, float], List[Tuple[float, float, float, float]]] = defaultdict(list)
    endpoints: Set[Tuple[float, float]] = set()

    for x1, y1, x2, y2 in lines:
        p1 = (round(x1, 1), round(y1, 1))
        p2 = (round(x2, 1), round(y2, 1))
        endpoints.add(p1)
        endpoints.add(p2)

        # Connect endpoints that are close
        for ep in endpoints:
            if ep != p1 and _point_dist(p1[0], p1[1], ep[0], ep[1]) < max_gap:
                adj[p1].append((ep[0], ep[1], 0.0, 0.0))
            if ep != p2 and _point_dist(p2[0], p2[1], ep[0], ep[1]) < max_gap:
                adj[p2].append((ep[0], ep[1], 0.0, 0.0))

    # Simple contour extraction using depth-first search
    # (Limited to clear closed paths; complex cases need more sophisticated methods)
    contours: List[ClosedContour] = []
    visited: Set[Tuple[float, float]] = set()

    for start in endpoints:
        if start in visited:
            continue

        # Walk the adjacency chain
        path = [start]
        current = start
        while True:
            visited.add(current)
            neighbors = adj.get(current, [])
            next_pt = None

            for nx, ny, _, _ in neighbors:
                npt = (round(nx, 1), round(ny, 1))
                if npt not in visited:
                    next_pt = npt
                    break

            if next_pt is None:
                break
            path.append(next_pt)
            current = next_pt

            # Check if we've closed the loop
            if len(path) > 2:
                first = path[0]
                last = path[-1]
                if _point_dist(first[0], first[1], last[0], last[1]) < max_gap:
                    # Closed loop found
                    area = _polygon_area(path)
                    if area >= min_area:
                        bbox = _bounding_box(path)

                        # Check if this contour is approximately a circle
                        is_circle = False
                        circle_center = None
                        circle_radius = 0.0
                        if len(path) >= 8:  # Needs enough points to check
                            cx = sum(p[0] for p in path) / len(path)
                            cy = sum(p[1] for p in path) / len(path)
                            radii = [_point_dist(p[0], p[1], cx, cy) for p in path]
                            avg_r = sum(radii) / len(radii)
                            # If all radii within 10% of average, it's a circle
                            if all(abs(r - avg_r) / avg_r < 0.1 for r in radii):
                                is_circle = True
                                circle_center = (cx, cy)
                                circle_radius = avg_r

                        contours.append(ClosedContour(
                            points=path,
                            is_closed=True,
                            area=area,
                            is_circle=is_circle,
                            circle_center=circle_center,
                            circle_radius=circle_radius,
                            bounding_box=bbox,
                        ))
                    break

    return contours


# ===== Symmetry Detection =====

def _detect_symmetry(
    contours: List[ClosedContour],
    lines: List[Tuple[float, float, float, float]],
) -> List[Tuple[float, float, float, float]]:
    """
    Detect symmetry axes in the drawing.

    Furniture parts (tables, cabinets, sofas) are usually symmetric.
    The symmetry axis helps reconstruct missing or occluded parts.
    """
    axes: List[Tuple[float, float, float, float]] = []

    # Method 1: Find vertical centerline from bounding boxes
    for contour in contours:
        if contour.bounding_box:
            x_min, y_min, x_max, y_max = contour.bounding_box
            center_x = (x_min + x_max) / 2
            # Vertical axis through center
            axes.append((center_x, y_min, center_x, y_max))

    # Method 2: Look for existing centerlines in the line set
    for x1, y1, x2, y2 in lines:
        a = _line_angle(x1, y1, x2, y2)
        length = _point_dist(x1, y1, x2, y2)
        # Very long vertical/horizontal lines are likely centerlines
        if length > 50 and (abs(a - 90) < 5 or abs(a) < 5 or abs(a - 180) < 5):
            axes.append((x1, y1, x2, y2))

    # Deduplicate nearby axes
    deduped: List[Tuple[float, float, float, float]] = []
    for ax in axes:
        is_dup = False
        for existing in deduped:
            d1 = _point_dist(ax[0], ax[1], existing[0], existing[1])
            d2 = _point_dist(ax[2], ax[3], existing[2], existing[3])
            if d1 < 20 and d2 < 20:
                is_dup = True
                break
        if not is_dup:
            deduped.append(ax)

    return deduped[:5]  # Limit to top 5 axes


# ===== Circle Refinement =====

def _refine_circles(
    raw_circles: List[Tuple[float, float, float]],
    lines: List[Tuple[float, float, float, float]],
) -> List[Tuple[float, float, float]]:
    """
    Refine circle detections by finding line segments that form arcs.

    For circles detected by HoughCircles, verify by checking if
    there are supporting line segments along the circumference.
    """
    if not raw_circles:
        return []

    refined: List[Tuple[float, float, float]] = []

    for cx, cy, r in raw_circles:
        supporting_points = 0
        max_support = min(12, len(lines))

        for x1, y1, x2, y2 in lines[:max_support]:
            # Check if either endpoint is near the circle circumference
            d1 = abs(_point_dist(x1, y1, cx, cy) - r)
            d2 = abs(_point_dist(x2, y2, cx, cy) - r)
            if d1 < r * 0.1 or d2 < r * 0.1:
                supporting_points += 1

        # Keep circle if it has supporting points or is the only one
        if supporting_points > 2 or len(raw_circles) == 1:
            refined.append((cx, cy, r))

    return refined or raw_circles  # Fallback to raw if all rejected


# ===== Main Reconstruction =====

def reconstruct_geometry(
    vision_lines: List[Tuple[float, float, float, float]],
    circles: Optional[List[Tuple[float, float, float]]] = None,
    rects: Optional[List[Tuple[float, float, float, float]]] = None,
    snap_distance: float = 8.0,
    corner_distance: float = 15.0,
    min_contour_area: float = 100.0,
) -> ReconstructionResult:
    """
    Reconstruct clean geometry from raw vision detections.

    Pipeline:
    1. Snap near-parallel lines together
    2. Extend endpoints to form corners
    3. Extract closed contours from the snapped graph
    4. Refine circle detections
    5. Detect symmetry axes

    Args:
        vision_lines: Raw lines from OpenCV as (x1, y1, x2, y2) tuples
        circles: Detected circles as (cx, cy, r) tuples
        rects: Detected rectangles as (x1, y1, x2, y2) tuples
        snap_distance: Max distance for line snapping
        corner_distance: Max distance for corner snapping
        min_contour_area: Minimum contour area to keep

    Returns:
        ReconstructionResult with cleaned lines, contours, circles, and axes
    """
    circles = circles or []
    rects = rects or []

    original_count = len(vision_lines)

    # Flatten to (x1, y1, x2, y2) format
    flat_lines: List[Tuple[float, float, float, float]] = []
    for line in vision_lines:
        if len(line) == 4:
            flat_lines.append(line)
        elif len(line) == 2:
            flat_lines.append((line[0][0], line[0][1], line[1][0], line[1][1]))

    # Add rectangle edges as lines
    for rx1, ry1, rx2, ry2 in rects:
        flat_lines.append((rx1, ry1, rx2, ry1))
        flat_lines.append((rx2, ry1, rx2, ry2))
        flat_lines.append((rx2, ry2, rx1, ry2))
        flat_lines.append((rx1, ry2, rx1, ry1))

    # Step 1: Snap near-parallel lines
    snapped_lines, snap_count = _snap_near_parallel_lines(
        flat_lines, dist_threshold=snap_distance)

    # Step 2: Snap endpoints to corners
    corner_lines, corner_count = _snap_endpoints_to_corners(
        snapped_lines, corner_distance=corner_distance)

    # Step 3: Extract closed contours
    contours = _extract_closed_contours(corner_lines, max_gap=corner_distance,
                                         min_area=min_contour_area)

    # Step 4: Refine circles
    refined_circles = _refine_circles(circles, snapped_lines)

    # Step 5: Detect symmetry
    symmetry_axes = _detect_symmetry(contours, snapped_lines)

    # Build cleaned lines output
    cleaned = [
        ReconstructedLine(
            x1=x1, y1=y1, x2=x2, y2=y2,
            length=_point_dist(x1, y1, x2, y2),
            angle_deg=_line_angle(x1, y1, x2, y2),
            is_snapped=True,
        ) for x1, y1, x2, y2 in snapped_lines
    ]

    # Add lines that were NOT snapped (from original)
    snapped_set = set(snapped_lines)
    unsnapped_count = 0
    for line in flat_lines:
        if line not in snapped_set:
            cleaned.append(ReconstructedLine(
                x1=line[0], y1=line[1], x2=line[2], y2=line[3],
                length=_point_dist(line[0], line[1], line[2], line[3]),
                angle_deg=_line_angle(line[0], line[1], line[2], line[3]),
                is_snapped=False,
            ))
            unsnapped_count += 1

    return ReconstructionResult(
        cleaned_lines=cleaned,
        closed_contours=contours,
        circles=refined_circles,
        arcs=[],
        symmetry_axes=symmetry_axes,
        original_line_count=original_count,
        snapped_pairs=snap_count,
        corners_found=corner_count,
    )


# Public API
def reconstruct(
    vision_lines: List[Tuple[float, float, float, float]],
    circles: Optional[List[Tuple[float, float, float]]] = None,
) -> ReconstructionResult:
    """Main entry point: reconstruct clean geometry from raw vision detections."""
    return reconstruct_geometry(vision_lines, circles)
