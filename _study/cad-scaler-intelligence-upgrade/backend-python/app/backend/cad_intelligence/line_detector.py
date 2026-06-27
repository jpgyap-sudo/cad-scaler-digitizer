from __future__ import annotations
import uuid
import cv2
import numpy as np
from .models import DetectedLine, DetectedCircle
from .geometry_utils import line_angle_deg, line_length

def load_grayscale(image_path: str):
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    return image

def detect_lines(image_path: str, min_line_length: int = 35, max_line_gap: int = 10) -> list[DetectedLine]:
    gray = load_grayscale(image_path)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 50, 150, apertureSize=3)
    raw_lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=45,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap,
    )
    results: list[DetectedLine] = []
    if raw_lines is None:
        return results
    for raw in raw_lines:
        x1, y1, x2, y2 = [float(v) for v in raw[0]]
        start = (x1, y1)
        end = (x2, y2)
        length = line_length(start, end)
        if length < min_line_length:
            continue
        results.append(DetectedLine(
            id=f"line_{uuid.uuid4().hex[:8]}",
            start=start,
            end=end,
            length_px=length,
            angle_deg=line_angle_deg(start, end),
            confidence=0.65,
            metadata={"detector": "hough_lines_p"},
        ))
    return results

def detect_circles(image_path: str, min_radius: int = 10, max_radius: int = 1000) -> list[DetectedCircle]:
    gray = load_grayscale(image_path)
    blur = cv2.medianBlur(gray, 5)
    raw_circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=40,
        param1=80,
        param2=28,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    results: list[DetectedCircle] = []
    if raw_circles is None:
        return results
    for x, y, r in np.round(raw_circles[0, :]).astype("float"):
        results.append(DetectedCircle(
            id=f"circle_{uuid.uuid4().hex[:8]}",
            center=(float(x), float(y)),
            radius_px=float(r),
            confidence=0.62,
            metadata={"detector": "hough_circles"},
        ))
    return results
