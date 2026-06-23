"""
Vision Agent: OpenCV preprocessing, line/circle/rectangle detection, OCR dimension extraction.
"""
import cv2
import numpy as np
import re
from PIL import Image
import pytesseract

DIM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(cm|mm|m|in|ft)?\s*(dia|diameter|h|height|w|width|d|depth|thk|thickness|l|length)?", re.I)

def load_gray(path: str):
    """Load image as BGR + grayscale. Handles PDF paths too."""
    img = cv2.imread(path)
    if img is None:
        # Try with PIL fallback
        try:
            pil_img = Image.open(path).convert("RGB")
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            raise ValueError(f"Cannot read image: {e}")
    return img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def preprocess(gray):
    """Adaptive threshold + morphological cleanup for line detection."""
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, 31, 9)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
    return th

def detect_lines(binary):
    """Hough Probabilistic line detection."""
    edges = cv2.Canny(binary, 50, 150, apertureSize=3)
    raw = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=35, maxLineGap=12)
    lines = []
    if raw is not None:
        for x1, y1, x2, y2 in raw[:, 0, :]:
            if np.hypot(x2 - x1, y2 - y1) > 20:
                lines.append(((float(x1), float(y1)), (float(x2), float(y2))))
    return lines

def detect_circles(gray):
    """Hough Circle detection."""
    blur = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=80,
                               param1=80, param2=28, minRadius=15, maxRadius=500)
    out = []
    if circles is not None:
        for x, y, r in np.round(circles[0, :]).astype(int):
            if r > 0:
                out.append((float(x), float(y), float(r)))
    return out

def detect_rectangles(binary):
    """Contour-based rectangle detection."""
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = []
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            if w > 30 and h > 30:
                rects.append((float(x), float(y), float(x + w), float(y + h)))
    return rects

def ocr_dimensions(path: str):
    """OCR all text, extract dimension values with tags and units."""
    text = pytesseract.image_to_string(Image.open(path))
    dims = []
    for m in DIM_RE.finditer(text):
        value = float(m.group(1))
        unit = (m.group(2) or "cm").lower()
        tag = (m.group(3) or "").lower()
        # Convert to cm
        if unit == "mm":
            value /= 10
        elif unit == "m":
            value *= 100
        elif unit == "in":
            value *= 2.54
        elif unit == "ft":
            value *= 30.48
        if 1 <= value <= 10000:
            dims.append({"value_cm": round(value, 1), "tag": tag, "raw": m.group(0)})
    return text.splitlines(), dims

def normalize_lines(lines):
    """Straighten near-horizontal/vertical lines, deduplicate."""
    fixed = []
    for (a, b) in lines:
        x1, y1 = a
        x2, y2 = b
        # Straighten near-horizontal
        if abs(y2 - y1) < abs(x2 - x1) * 0.08:
            y = (y1 + y2) / 2
            y1 = y2 = y
        # Straighten near-vertical
        elif abs(x2 - x1) < abs(y2 - y1) * 0.08:
            x = (x1 + x2) / 2
            x1 = x2 = x
        if np.hypot(x2 - x1, y2 - y1) >= 20:
            fixed.append(((round(x1, 1), round(y1, 1)), (round(x2, 1), round(y2, 1))))
    # Deduplicate
    seen = set()
    out = []
    for a, b in fixed:
        key = tuple(sorted([a, b]))
        if key not in seen:
            seen.add(key)
            out.append((a, b))
    return out
