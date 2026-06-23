"""
Module: geometry_cleanup.py
Constraint solver — angle snapping, endpoint snapping, collinear merging.
"""
import math
import numpy as np
from typing import List, Tuple, Optional


def snap_angle(angle_deg: float, tolerance: float = 5.0) -> float:
    for t in [0, 45, 90, 135, 180]:
        if abs(angle_deg - t) <= tolerance or abs(angle_deg - (t - 180)) <= tolerance:
            return float(t)
    return angle_deg


def snap_line_angle(line, tolerance=5.0):
    (x1, y1), (x2, y2) = line
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return line
    angle = math.degrees(math.atan2(dy, dx)) % 180
    snapped = snap_angle(angle, tolerance)
    length = math.hypot(dx, dy)
    if snapped == 0: return ((x1, y1), (x2, y1))
    if snapped == 90: return ((x1, y1), (x1, y2))
    if snapped == 45:
        sign_y = 1 if dy > 0 else -1
        sign_x = 1 if dx > 0 else -1
        return ((x1, y1), (x1 + length * math.cos(math.radians(45)) * sign_x,
                                y1 + length * math.sin(math.radians(45)) * sign_y))
    if snapped == 135:
        sl = length * math.sin(math.radians(45))
        cl = length * math.cos(math.radians(135))
        return ((x1, y1), (x1 + cl * (1 if dx > 0 else -1),
                                y1 + sl * (1 if dy > 0 else -1)))
    return line


def _snap_to_nearest(point, targets, max_dist=5.0):
    for t in targets:
        if math.hypot(point[0] - t[0], point[1] - t[1]) <= max_dist:
            return t
    return point


def snap_endpoints(lines, tolerance=5.0):
    if not lines:
        return lines
    all_points = [p for a, b in lines for p in (a, b)]
    clusters = []
    for p in all_points:
        added = False
        for cluster in clusters:
            if math.hypot(p[0] - cluster[0][0], p[1] - cluster[0][1]) <= tolerance:
                cluster.append(p); added = True; break
        if not added:
            clusters.append([p])
    centers = [(round(sum(p[0] for p in c) / len(c), 1),
                round(sum(p[1] for p in c) / len(c), 1)) for c in clusters]
    snapped = []
    for a, b in lines:
        sa, sb = _snap_to_nearest(a, centers), _snap_to_nearest(b, centers)
        if math.hypot(sa[0] - sb[0], sa[1] - sb[1]) >= 1.0:
            snapped.append((sa, sb))
    return snapped


def _try_merge(a, b, gap_tol, angle_tol):
    (ax1, ay1), (ax2, ay2) = a
    (bx1, by1), (bx2, by2) = b
    angle_a = math.degrees(math.atan2(ay2 - ay1, ax2 - ax1)) % 180
    angle_b = math.degrees(math.atan2(by2 - by1, bx2 - bx1)) % 180
    diff = abs(angle_a - angle_b)
    if diff > angle_tol and abs(diff - 180) > angle_tol:
        return None
    endpoint_gaps = [math.hypot(ax2 - bx1, ay2 - by1), math.hypot(ax1 - bx2, ay1 - by2),
                     math.hypot(ax1 - bx1, ay1 - by1), math.hypot(ax2 - bx2, ay2 - by2)]
    if min(endpoint_gaps) > gap_tol:
        return None
    pts = [a[0], a[1], b[0], b[1]]
    max_d, best = 0, (a[0], b[1])
    for i, p1 in enumerate(pts):
        for p2 in pts[i+1:]:
            d = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
            if d > max_d:
                max_d, best = d, (p1, p2)
    return best


def merge_collinear(lines, gap_tolerance=5.0, angle_tolerance=3.0):
    if not lines:
        return lines
    merged = list(lines)
    changed = True
    while changed:
        changed = False
        new_merged, used = [], set()
        for i, a in enumerate(merged):
            if i in used: continue
            best = a
            for j, b in enumerate(merged):
                if j <= i or j in used: continue
                result = _try_merge(best, b, gap_tolerance, angle_tolerance)
                if result:
                    best = result; used.add(j); changed = True
            new_merged.append(best)
            used.add(i)
        merged = new_merged
    return merged


def _fit_circle(points):
    if len(points) < 3:
        return np.array([0, 0]), 0
    x, y = points[:, 0], points[:, 1]
    A = np.column_stack([x, y, np.ones_like(x)])
    B = -(x**2 + y**2)
    try:
        C = np.linalg.lstsq(A, B, rcond=None)[0]
        cx, cy = -C[0] / 2, -C[1] / 2
        return np.array([cx, cy]), math.sqrt(cx**2 + cy**2 - C[2])
    except np.linalg.LinAlgError:
        return np.array([0, 0]), 0


def rebuild_circles_from_segments(lines):
    if len(lines) < 8:
        return [], lines
    points = [p for a, b in lines for p in (a, b)]
    if len(points) < 8:
        return [], lines
    pts_array = np.array(points)
    center, radius = _fit_circle(pts_array)
    if radius <= 0:
        return [], lines
    errors = [abs(math.hypot(p[0] - center[0], p[1] - center[1]) - radius) for p in points]
    mean_err, max_err = np.mean(errors), np.max(errors)
    if mean_err < radius * 0.05 and max_err < radius * 0.1:
        return [(float(center[0]), float(center[1]), float(radius))], []
    return [], lines


def process_constraints(lines, circles, ocr_dims, rects=None):
    angle_snapped = [snap_line_angle(l) for l in lines]
    merged = merge_collinear(angle_snapped)
    rebuilt_circles, remaining_lines = rebuild_circles_from_segments(merged)
    final_lines = snap_endpoints(remaining_lines)
    all_circles = list(circles) + rebuilt_circles
    return {'lines': final_lines, 'circles': all_circles,
            'rects': rects or [], 'rebuilt_circles': len(rebuilt_circles)}
