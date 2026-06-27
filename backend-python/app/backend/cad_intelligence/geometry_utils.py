from __future__ import annotations
import math
from .models import Point, BBox

def distance(a: Point, b: Point) -> float:
    return math.dist(a, b)

def bbox_center(bbox: BBox) -> Point:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

def line_length(start: Point, end: Point) -> float:
    return distance(start, end)

def line_angle_deg(start: Point, end: Point) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    return math.degrees(math.atan2(dy, dx))

def normalize_angle(angle: float) -> float:
    while angle < 0:
        angle += 180
    while angle >= 180:
        angle -= 180
    return angle

def is_horizontal(angle: float, tolerance: float = 10) -> bool:
    a = normalize_angle(angle)
    return a <= tolerance or abs(a - 180) <= tolerance

def is_vertical(angle: float, tolerance: float = 10) -> bool:
    a = normalize_angle(angle)
    return abs(a - 90) <= tolerance

def point_to_line_distance(p: Point, a: Point, b: Point) -> float:
    px, py = p
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return distance(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    proj = (ax + t * dx, ay + t * dy)
    return distance(p, proj)

def bbox_distance_to_line(bbox: BBox, a: Point, b: Point) -> float:
    return point_to_line_distance(bbox_center(bbox), a, b)
