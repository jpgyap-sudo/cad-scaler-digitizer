"""
Module: ocr.py
Tesseract + PaddleOCR dual-engine text extraction.
"""
import re
import os
from PIL import Image
import pytesseract

# Configure Tesseract path
for tp in [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
           r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
    if os.path.exists(tp):
        pytesseract.pytesseract.tesseract_cmd = tp
        break

DIM_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(cm|mm|m|in|ft)?\s*"
    r"(dia|diameter|h|height|w|width|d|depth|thk|thickness|l|length)?", re.I
)

_paddle_ocr = None

def _get_paddle():
    global _paddle_ocr
    if _paddle_ocr is None:
        try:
            from paddleocr import PaddleOCR
            _paddle_ocr = PaddleOCR(lang='en')
        except Exception as e:
            print(f"[OCR] PaddleOCR load failed: {e}")
            _paddle_ocr = False
    return _paddle_ocr if _paddle_ocr is not False else None


def _extract_dimensions(text: str) -> list:
    dims = []
    for m in DIM_RE.finditer(text):
        value = float(m.group(1))
        unit = (m.group(2) or "cm").lower()
        tag = (m.group(3) or "").lower()
        if unit == "mm": value /= 10
        elif unit == "m": value *= 100
        elif unit == "in": value *= 2.54
        elif unit == "ft": value *= 30.48
        if 1 <= value <= 10000:
            dims.append({"value_cm": round(value, 1), "tag": tag, "raw": m.group(0)})
    return dims


def ocr_dimensions(image_path: str):
    """
    Dual OCR: Tesseract (fast) + PaddleOCR (accurate for drawings).
    Returns merged lines and dimensions.
    """
    img = Image.open(image_path)

    # Tesseract
    tesseract_text = ""
    try:
        tesseract_text = pytesseract.image_to_string(img)
    except Exception as e:
        print(f"[OCR] Tesseract error: {e}")

    tesseract_lines = tesseract_text.splitlines()
    tesseract_dims = _extract_dimensions(tesseract_text)

    # PaddleOCR
    paddle = _get_paddle()
    paddle_text = ""
    if paddle:
        try:
            result = paddle.ocr(str(image_path), cls=False)
            if result and result[0]:
                lines = [line[1][0] for line in result[0]]
                paddle_text = "\n".join(lines)
        except Exception as e:
            print(f"[OCR] PaddleOCR error: {e}")

    paddle_lines = paddle_text.splitlines() if paddle_text else []
    paddle_dims = _extract_dimensions(paddle_text) if paddle_text else []

    # Merge: dedup, PaddleOCR takes priority
    all_lines = list(dict.fromkeys(tesseract_lines + paddle_lines))
    all_dims = {}
    for d in tesseract_dims + paddle_dims:
        all_dims[d['raw']] = d

    return all_lines, list(all_dims.values())
