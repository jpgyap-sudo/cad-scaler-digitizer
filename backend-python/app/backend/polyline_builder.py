"""Merge individual LINE entities into LWPOLYLINEs for cleaner CAD output."""
import math
from typing import List, Tuple


def lines_to_polylines(lines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
                        angle_tolerance: float = 5.0,
                        gap_tolerance: float = 3.0) -> Tuple[List, List]:
    """
    Connect collinear/adjacent lines into LWPOLYLINE chains.
    Returns (polylines, remaining_lines).
    """
    if not lines:
        return [], []

    # Cluster lines by angle
    clusters = []
    used = set()

    for i, (a, b) in enumerate(lines):
        if i in used:
            continue
        cluster = [(a, b)]
        used.add(i)
        angle = _line_angle(a, b)

        for j, (c, d) in enumerate(lines):
            if j in used:
                continue
            other_angle = _line_angle(c, d)
            if abs(angle - other_angle) < angle_tolerance:
                # Check if endpoints connect
                if _endpoint_distance(b, c) < gap_tolerance:
                    cluster.append((c, d))
                    used.add(j)
                    b = d
                elif _endpoint_distance(b, d) < gap_tolerance:
                    cluster.append((d, c))
                    used.add(j)
                    b = c
                elif _endpoint_distance(a, c) < gap_tolerance:
                    cluster.insert(0, (c, d))
                    used.add(j)
                    a = d
                elif _endpoint_distance(a, d) < gap_tolerance:
                    cluster.insert(0, (d, c))
                    used.add(j)
                    a = c

        clusters.append(cluster)

    polylines = []
    remaining = []
    for cluster in clusters:
        if len(cluster) >= 2:
            points = [cluster[0][0]]
            for seg in cluster:
                if _endpoint_distance(points[-1], seg[0]) < gap_tolerance:
                    points.append(seg[1])
                elif _endpoint_distance(points[-1], seg[1]) < gap_tolerance:
                    points.append(seg[0])
            # Check if closed
            closed = len(points) > 2 and _endpoint_distance(points[0], points[-1]) < gap_tolerance
            if closed:
                points = points[:-1]
            polylines.append((points, closed))
        else:
            remaining.append(cluster[0])

    return polylines, remaining


def _line_angle(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180


def _endpoint_distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
