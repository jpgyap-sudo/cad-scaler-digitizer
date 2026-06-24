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

# Require EITHER a unit OR a label tag after the number to avoid matching random digits
DIM_RE = re.compile(
    r"(\d+(?:\.\d+)?)"
    r"\s*(?:(cm|mm|m|in|ft)\s*(dia|diameter|h|height|w|width|d|depth|thk|thickness|l|length)?"
    r"|(?:^|\s)(dia|diameter|h|height|w|width|d|depth|thk|thickness|l|length))",
    re.I
)
# Simpler and safer alternative — match number followed by unit, OR label=number, OR number+label
_DIM_RE = re.compile(
    r"(?P<label>dia(?:meter)?|h(?:eight)?|w(?:idth)?|d(?:epth)?|thk|thickness|l(?:ength)?)?\s*[=:]?\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>cm|mm|m\b|in|ft|\")?\s*"
    r"(?P<label2>dia(?:meter)?|h(?:eight)?|w(?:idth)?|d(?:epth)?|thk|thickness)?",
    re.I
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
    """Extract dimensions that have either a unit or a label — avoids matching bare numbers."""
    dims = []
    m = _DIM_RE.finditer(text)
    for match in m:
        label = (match.group('label') or match.group('label2') or '').lower()
        raw_val = match.group('value')
        unit = (match.group('unit') or '').lower().strip('"')

        # Must have at least a unit or a label to be a real dimension
        if not label and not unit:
            continue

        try:
            value = float(raw_val)
        except Exception:
            continue

        # Unit conversion to cm
        if unit == 'mm':
            value /= 10
        elif unit == 'm':
            value *= 100
        elif unit == 'in' or unit == '"':
            value *= 2.54
        elif unit == 'ft':
            value *= 30.48
        # else assume cm

        # Sanity-check: furniture dimensions are 2cm–1000cm
        if 2.0 <= value <= 1000.0:
            dims.append({
                "value_cm": round(value, 1),
                "tag": label,
                "raw": match.group(0).strip()
            })
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
