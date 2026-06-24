"""
OCR Module: Uses OpenAI Vision API (primary) + Tesseract (fallback) for maximum accuracy.
GPT-4o Vision reads dimensions from drawings much better than Tesseract.
"""
import os
import re
import json
import base64
from PIL import Image
import pytesseract

for tp in [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
           r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
    if os.path.exists(tp):
        pytesseract.pytesseract.tesseract_cmd = tp
        break

DIM_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(cm|mm|m|in|ft)?\s*"
    r"(dia|diameter|h|height|w|width|d|depth|thk|thickness|l|length)?", re.I
)

_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def _image_to_base64(path: str) -> str:
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode()


def _get_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.webp': 'image/webp', '.bmp': 'image/bmp'}.get(ext, 'image/png')


def _openai_ocr_sync(image_path: str) -> list:
    """Sync wrapper for OpenAI Vision OCR."""
    if not _OPENAI_API_KEY:
        return []
    try:
        import httpx
        b64 = _image_to_base64(image_path)
        mime = _get_mime(image_path)
        r = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {_OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "Extract ALL dimension labels. Return JSON array: [{\"value_cm\":number,\"tag\":\"dia|h|w|d\",\"raw\":\"text\"}]. Convert to cm."},
                    {"role": "user", "content": [{"type":"text","text":"Read all dimensions."},
                        {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}","detail":"high"}}]}
                ],
                "max_tokens": 1000,
                "response_format": {"type": "json_object"},
                "timeout": 30
            }
        )
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            data = json.loads(content)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                for key in ['dimensions', 'values', 'dims']:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                if data.get('value_cm'):
                    return [data]
        return []
    except Exception as e:
        print(f"[OCR] OpenAI error: {e}")
        return []


def _tesseract_ocr(image_path: str):
    """Fallback OCR via Tesseract."""
    try:
        text = pytesseract.image_to_string(Image.open(image_path))
    except Exception as e:
        return [], []
    lines = text.splitlines()
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
    return lines, dims


def ocr_dimensions(image_path: str):
    """Sync OCR: OpenAI Vision (primary) → Tesseract (fallback)."""
    ai_dims = _openai_ocr_sync(image_path)

    if ai_dims:
        for d in ai_dims:
            if 'value_cm' not in d and 'value' in d:
                d['value_cm'] = float(d['value'])
            d['value_cm'] = float(d.get('value_cm', d.get('value', 0)))
        dim_texts = [d.get('raw', '') for d in ai_dims]
        print(f"[OCR] OpenAI: {len(ai_dims)} dims")
        return dim_texts, ai_dims

    print("[OCR] Tesseract fallback")
    return _tesseract_ocr(image_path)
