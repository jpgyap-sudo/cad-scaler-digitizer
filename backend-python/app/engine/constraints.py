"""
Geometric Constraint Snapping Engine

Professional-grade geometric solver that snaps raw OpenCV detections
to perfect CAD geometry before DXF output.

Features:
- Angle snapping (0°, 45°, 90°)
- Endpoint snapping (coincident within tolerance)
- Collinear merging
- Circle rebuilding from segments
- Dimension autocorrect (snap to OCR values)
"""
import math
import numpy as np
from typing import List, Tuple, Optional


def snap_angle(angle_deg: float, tolerance: float = 5.0) -> float:
    """Snap angle to nearest 0°, 45°, 90°, 135°, 180° within tolerance."""
    targets = [0, 45, 90, 135, 180]
    for t in targets:
        if abs(angle_deg - t) <= tolerance or abs(angle_deg - (t - 180)) <= tolerance:
            return float(t)
    return angle_deg


def snap_line_angle(
    line: Tuple[Tuple[float, float], Tuple[float, float]],
    tolerance: float = 5.0
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Snap a line segment to the nearest constrained angle."""
    (x1, y1), (x2, y2) = line
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return line

    angle = math.degrees(math.atan2(dy, dx)) % 180
    snapped = snap_angle(angle, tolerance)
    length = math.hypot(dx, dy)

    if snapped == 0:
        # Horizontal
        return ((x1, y1), (x2, y1))
    elif snapped == 90:
        # Vertical
        return ((x1, y1), (x1, y2))
    elif snapped == 45:
        # Diagonal 45°
        sign = 1 if dy > 0 else -1
        return ((x1, y1), (x1 + length * math.cos(math.radians(45)) * (1 if dx > 0 else -1),
                                y1 + length * math.sin(math.radians(45)) * sign))
    elif snapped == 135:
        # Diagonal 135°
        return ((x1, y1), (x1 + length * math.cos(math.radians(135)) * (1 if dx > 0 else -1),
                                y1 + length * math.sin(math.radians(135)) * (1 if dy > 0 else -1)))

    return line


def snap_endpoints(
    lines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    tolerance: float = 5.0
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Snap endpoints that are close together to be perfectly coincident.
    Uses clustering to find groups of nearby endpoints.
    """
    if not lines:
        return lines

    # Collect all unique endpoints
    all_points = []
    for a, b in lines:
        all_points.append(a)
        all_points.append(b)

    # Cluster nearby points
    clusters = []  # list of lists of points
    for p in all_points:
        added = False
        for cluster in clusters:
            if math.hypot(p[0] - cluster[0][0], p[1] - cluster[0][1]) <= tolerance:
                cluster.append(p)
                added = True
                break
        if not added:
            clusters.append([p])

    # Compute cluster centers
    centers = []
    for cluster in clusters:
        cx = sum(p[0] for p in cluster) / len(cluster)
        cy = sum(p[1] for p in cluster) / len(cluster)
        centers.append((round(cx, 1), round(cy, 1)))

    # Snap lines to nearest center
    snapped = []
    for a, b in lines:
        sa = _snap_to_nearest(a, centers)
        sb = _snap_to_nearest(b, centers)
        if math.hypot(sa[0] - sb[0], sa[1] - sb[1]) >= 1.0:  # Skip zero-length
            snapped.append((sa, sb))

    return snapped


def _snap_to_nearest(
    point: Tuple[float, float],
    targets: List[Tuple[float, float]],
    max_dist: float = 5.0
) -> Tuple[float, float]:
    """Snap a point to nearest target within tolerance."""
    for t in targets:
        if math.hypot(point[0] - t[0], point[1] - t[1]) <= max_dist:
            return t
    return point


def merge_collinear(
    lines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    gap_tolerance: float = 5.0,
    angle_tolerance: float = 3.0
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Merge collinear lines that overlap or are within gap_tolerance."""
    if not lines:
        return lines

    merged = list(lines)
    changed = True
    while changed:
        changed = False
        new_merged = []
        used = set()

        for i, a in enumerate(merged):
            if i in used:
                continue
            best = a
            for j, b in enumerate(merged):
                if j <= i or j in used:
                    continue
                result = _try_merge(best, b, gap_tolerance, angle_tolerance)
                if result:
                    best = result
                    used.add(j)
                    changed = True
            new_merged.append(best)
            used.add(i)

        merged = new_merged

    return merged


def _try_merge(
    a: Tuple[Tuple[float, float], Tuple[float, float]],
    b: Tuple[Tuple[float, float], Tuple[float, float]],
    gap_tol: float,
    angle_tol: float
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Try to merge two line segments if they're collinear and close."""
    (ax1, ay1), (ax2, ay2) = a
    (bx1, by1), (bx2, by2) = b

    # Check collinearity
    angle_a = math.degrees(math.atan2(ay2 - ay1, ax2 - ax1)) % 180
    angle_b = math.degrees(math.atan2(by2 - by1, bx2 - bx1)) % 180
    diff = abs(angle_a - angle_b)
    if diff > angle_tol and abs(diff - 180) > angle_tol:
        return None

    # Check if endpoints connect
    pts = [a[0], a[1], b[0], b[1]]
    # Find farthest pair
    max_dist = 0
    best_pair = (a[0], b[1])
    for i, p1 in enumerate(pts):
        for p2 in pts[i + 1:]:
            d = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
            if d > max_dist:
                max_dist = d
                best_pair = (p1, p2)

    # Check if the gap between endpoints is small enough
    endpoint_gaps = [
        math.hypot(ax2 - bx1, ay2 - by1),
        math.hypot(ax1 - bx2, ay1 - by2),
        math.hypot(ax1 - bx1, ay1 - by1),
        math.hypot(ax2 - bx2, ay2 - by2),
    ]
    if min(endpoint_gaps) > gap_tol:
        return None

    return best_pair


def rebuild_circles_from_segments(
    lines: List[Tuple[Tuple[float, float], Tuple[float, float]]]
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[Tuple[float, float], Tuple[float, float]]]]:
    """
    Detect if a set of line segments form a circle approximation.
    Returns (detected_circles, remaining_lines).
    """
    if len(lines) < 8:
        return [], lines

    points = []
    for a, b in lines:
        points.extend([a, b])

    if len(points) < 8:
        return [], lines

    # Fit a circle to the points
    pts_array = np.array(points)
    center, radius = _fit_circle(pts_array)

    if radius <= 0:
        return [], lines

    # Check how well the points fit the circle
    errors = [abs(math.hypot(p[0] - center[0], p[1] - center[1]) - radius) for p in points]
    mean_error = np.mean(errors)
    max_error = np.max(errors)

    # If mean error is small relative to radius, it's a circle
    if mean_error < radius * 0.05 and max_error < radius * 0.1:
        return [(float(center[0]), float(center[1]), float(radius))], []

    return [], lines


def _fit_circle(points: np.ndarray) -> Tuple[np.ndarray, float]:
    """Fit a circle to points using least squares."""
    if len(points) < 3:
        return np.array([0, 0]), 0

    x, y = points[:, 0], points[:, 1]
    A = np.column_stack([x, y, np.ones_like(x)])
    B = -(x ** 2 + y ** 2)

    try:
        C = np.linalg.lstsq(A, B, rcond=None)[0]
        cx = -C[0] / 2
        cy = -C[1] / 2
        r = math.sqrt(cx ** 2 + cy ** 2 - C[2])
        return np.array([cx, cy]), r
    except np.linalg.LinAlgError:
        return np.array([0, 0]), 0


def autocorrect_dimensions(
    ocr_dims: List[dict],
    pixel_measurements: dict,
    tolerance: float = 0.1
) -> List[dict]:
    """
    Snap raw pixel measurements to OCR text values.
    If OCR says '80 cm' and pixels measure 79.2 cm, snap to 80.0 cm.
    """
    corrected = []
    for dim in ocr_dims:
        tag = dim.get('tag', '')
        value = dim.get('value_cm', dim.get('value', 0))

        # Look for matching pixel measurement
        pixel_val = pixel_measurements.get(tag)
        if pixel_val is not None:
            diff = abs(value - pixel_val) / value if value > 0 else 1
            if diff < tolerance:
                # Snap to OCR value (more accurate)
                dim['value_cm'] = round(value, 1)
                dim['autocorrected'] = True
            else:
                dim['warning'] = f'OCR={value}cm vs pixel={pixel_val:.1f}cm diff={diff*100:.0f}%'

        corrected.append(dim)

    return corrected


def clean_geometry(raw_lines):
    """Clean geometry: normalize + snap angles + snap endpoints + merge collinear."""
    from .vision import normalize_lines
    normalized = normalize_lines(raw_lines)
    angle_snapped = [snap_line_angle(l) for l in normalized]
    merged = merge_collinear(angle_snapped)
    final = snap_endpoints(merged)
    return final


def align_dimension_to_ocr(value: float, dims: list, tags: list) -> float:
    """Snap a raw value to matching OCR dimension if close."""
    for d in dims:
        tag = d.get('tag', '')
        ocr_val = d.get('value_cm', d.get('value', 0))
        if any(t in tag for t in tags) and ocr_val > 0:
            diff = abs(value - ocr_val) / max(value, ocr_val)
            if diff < 0.15:  # 15% tolerance
                return ocr_val
    return value


def extract_table_proportions(lines, circles, rects):
    """Extract visual ratios from detected geometry for table reconstruction."""
    ratios = {
        'base_ratio': 0.55,
        'neck_ratio': 0.28,
        'thickness_ratio': 0.05,
        'base_height_ratio': 0.15,  # base height as fraction of total height
    }
    
    if circles:
        # If circles found, use radius ratios
        radii = [r for _, _, r in circles]
        if radii:
            max_r = max(radii)
            for r in radii:
                ratio = r / max_r
                if 0.4 < ratio < 0.7:
                    ratios['base_ratio'] = ratio
                elif 0.2 < ratio < 0.35:
                    ratios['neck_ratio'] = ratio
    
    return ratios


def process_constraints(
    lines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    circles: List[Tuple[float, float, float]],
    ocr_dims: List[dict],
    rects: List[Tuple[float, float, float, float]] = None
) -> dict:
    """
    Full constraint processing pipeline.
    Returns snapped geometry and validated dimensions.
    """
    # Step 1: Snap angles
    angle_snapped = [snap_line_angle(l) for l in lines]

    # Step 2: Merge collinear
    merged = merge_collinear(angle_snapped)

    # Step 3: Rebuild circles from segments
    rebuilt_circles, remaining_lines = rebuild_circles_from_segments(merged)

    # Step 4: Snap endpoints
    final_lines = snap_endpoints(remaining_lines)

    # Step 5: All circles (original + rebuilt)
    all_circles = list(circles) + rebuilt_circles

    return {
        'lines': final_lines,
        'circles': all_circles,
        'rects': rects or [],
        'rebuilt_circles': len(rebuilt_circles),
    }
