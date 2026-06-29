"""
OCR Module: Uses OpenAI Vision API (primary) + Tesseract (fallback) for maximum accuracy.
GPT-4o Vision reads dimensions from drawings much better than Tesseract.
"""
import os
import re
import json
import base64
from pathlib import Path
from PIL import Image
import cv2
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
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
_GEMINI_MODEL = os.environ.get("GEMINI_OCR_MODEL", "gemini-2.5-flash")

# Laplacian variance below this is treated as "too blurry to read small text
# reliably" - a sharp technical drawing/photo typically scores in the
# hundreds to thousands; a soft/blurry phone photo often falls below 100.
BLUR_THRESHOLD = 100.0


def blur_score(image_path: str) -> float:
    """Laplacian variance — a standard, fast blur metric. Higher = sharper."""
    img = cv2.imread(image_path)
    if img is None:
        return BLUR_THRESHOLD  # unreadable -> don't block on enhancement, let OCR try as-is
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _unsharp_mask(img, amount: float = 1.5, sigma: float = 3.0):
    """Standard unsharp mask: boost edge contrast by subtracting a blurred
    copy. Verified empirically (see test below) to actually raise the
    Laplacian-variance sharpness score, unlike a naive single pass combined
    with cubic upscaling (which nets *negative* — bicubic interpolation
    smooths more than one sharpen pass recovers)."""
    blurred = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1 + amount, blurred, -amount, 0)


def _enhance_for_ocr(image_path: str) -> str:
    """Upscale + sharpen a blurry image so OCR has a better chance of reading
    small dimension text. Writes to a sibling '*_enhanced' file and returns
    its path — the original is left untouched since geometry detection
    (line/circle finding) runs on the original separately.

    Order matters: upscaling with INTER_CUBIC before sharpening measurably
    *reduces* sharpness (bicubic is a smoothing interpolant) enough to
    overwhelm a single unsharp-mask pass. Using INTER_LANCZOS4 (sharper
    interpolation kernel) for the upscale, then applying the unsharp mask
    twice afterward, reliably improves the blur score across mild-to-severe
    blur levels (tested at multiple Gaussian blur kernel/sigma combinations).
    """
    img = cv2.imread(image_path)
    if img is None:
        return image_path
    h, w = img.shape[:2]
    scale = 2.0 if max(h, w) < 2000 else 1.5
    upscaled = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    sharpened = _unsharp_mask(_unsharp_mask(upscaled, amount=1.5), amount=1.5)
    p = Path(image_path)
    out_path = str(p.with_name(p.stem + '_enhanced' + p.suffix))
    cv2.imwrite(out_path, sharpened)
    return out_path


def assess_image_quality(image_path: str) -> dict:
    """Cheap quality check for surfacing in API responses (doesn't enhance)."""
    score = blur_score(image_path)
    return {"blur_score": round(score, 1), "is_blurry": score < BLUR_THRESHOLD,
            "threshold": BLUR_THRESHOLD}


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
                    {"role": "system", "content": "Extract ALL dimension labels from this furniture drawing. For each one, use the nearby label text to pick the most specific tag: 'top_dia' (tabletop/overall diameter), 'base_dia' (base plate / pedestal foot / glide diameter), 'neck_dia' (neck/collar/narrowest-point diameter), 'collar_dia' (metal collar plate diameter), 'height' (overall height), 'width', 'depth', 'thickness'. If a diameter's context is unclear, use 'dia'. Return JSON array: [{\"value_cm\":number,\"tag\":\"top_dia|base_dia|neck_dia|collar_dia|height|width|depth|thickness|dia\",\"raw\":\"original text incl. nearby label\"}]. Convert all values to cm."},
                    {"role": "user", "content": [{"type":"text","text":"Read all dimensions."},
                        {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}","detail":"high"}}]}
                ],
                "max_tokens": 1000,
                "response_format": {"type": "json_object"},
                # NOTE: 'timeout' must NOT go in the JSON body — OpenAI rejects
                # it with HTTP 400 "Unrecognized request argument supplied:
                # timeout", which made this call fail for EVERY image and
                # silently fall back to Tesseract (which misreads digits, e.g.
                # 80 -> 60). It belongs on the httpx call instead.
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[OCR] OpenAI HTTP {r.status_code}: {r.text[:200]}")
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


def _gemini_ocr_sync(image_path: str) -> list:
    """Sync wrapper for Google Gemini Vision OCR - same tag taxonomy as
    _openai_ocr_sync, used as the primary vision OCR when GEMINI_API_KEY
    is set (OpenAI's key has been failing auth - see [OCR] OpenAI HTTP 401
    in logs)."""
    if not _GEMINI_API_KEY:
        return []
    try:
        import httpx
        b64 = _image_to_base64(image_path)
        mime = _get_mime(image_path)
        prompt = (
            "Extract ALL dimension labels from this furniture drawing. For each one, "
            "use the nearby label text to pick the most specific tag: 'top_dia' "
            "(tabletop/overall diameter), 'base_dia' (base plate / pedestal foot / glide "
            "diameter), 'neck_dia' (neck/collar/narrowest-point diameter), 'collar_dia' "
            "(metal collar plate diameter), 'height' (overall height), 'width', 'depth', "
            "'thickness'. If a diameter's context is unclear, use 'dia'. Convert all "
            "values to cm. Respond with a JSON object: "
            "{\"dimensions\":[{\"value_cm\":number,\"tag\":\"top_dia|base_dia|neck_dia|"
            "collar_dia|height|width|depth|thickness|dia\",\"raw\":\"original text incl. "
            "nearby label\"}]}"
        )
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{_GEMINI_MODEL}:generateContent",
            params={"key": _GEMINI_API_KEY},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": b64}},
                ]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[OCR] Gemini HTTP {r.status_code}: {r.text[:200]}")
            return []
        content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ["dimensions", "values", "dims"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            if data.get("value_cm"):
                return [data]
        return []
    except Exception as e:
        print(f"[OCR] Gemini error: {e}")
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
    """Sync OCR: Gemini Vision (primary) -> OpenAI Vision (fallback) ->
    Tesseract (last resort), first one that returns results wins.

    Gemini is primary as of 2026-06-29 (per product decision - a working
    OpenAI key was restored, but Gemini stays primary with OpenAI as the
    fallback rather than reverting the order). Tesseract is the last
    resort: it reads digits fine but can't tag them without an inline
    "H=" style label right next to the number, so most fields fall back
    to ratio estimates/defaults when only Tesseract ran.

    Auto-enhances (upscale + sharpen) the image first if it scores as too
    blurry for reliable small-text reading - misread dimension labels (e.g.
    "80" read as "60") are often a blur/resolution problem, not a model
    problem. The enhanced copy is only used for this OCR pass and cleaned up
    afterward; geometry detection elsewhere still uses the original file.
    """
    ocr_path = image_path
    enhanced_path = None
    try:
        score = blur_score(image_path)
        if score < BLUR_THRESHOLD:
            enhanced_path = _enhance_for_ocr(image_path)
            ocr_path = enhanced_path
            print(f"[OCR] Blur score {score:.1f} < {BLUR_THRESHOLD} - using enhanced copy for OCR")
    except Exception as e:
        print(f"[OCR] Blur check/enhance failed: {e}")

    try:
        ai_dims = _gemini_ocr_sync(ocr_path)
        ai_source = "Gemini"
        if not ai_dims:
            ai_dims = _openai_ocr_sync(ocr_path)
            ai_source = "OpenAI"

        if ai_dims:
            for d in ai_dims:
                if 'value_cm' not in d and 'value' in d:
                    d['value_cm'] = float(d['value'])
                d['value_cm'] = float(d.get('value_cm', d.get('value', 0)))
            dim_texts = [d.get('raw', '') for d in ai_dims]
            # OpenAI returns only the structured dimension labels, which
            # starves the furniture classifier of the descriptive keywords it
            # keys on (e.g. "PEDESTAL", "WOOD TOP", "DIA"). Tesseract reads ALL
            # visible text (even if it garbles digits — which don't matter for
            # keyword classification), so use its full text lines for the
            # classifier while keeping OpenAI's accurate dimension VALUES.
            tess_lines = []
            try:
                tess_lines, _ = _tesseract_ocr(ocr_path)
            except Exception:
                pass
            text_lines = list(dict.fromkeys([t for t in (dim_texts + tess_lines) if t.strip()]))
            print(f"[OCR] {ai_source}: {len(ai_dims)} dims (+{len(tess_lines)} text lines for classification)")
            return text_lines, ai_dims

        print("[OCR] Tesseract fallback")
        return _tesseract_ocr(ocr_path)
    finally:
        if enhanced_path and enhanced_path != image_path:
            try: os.remove(enhanced_path)
            except Exception: pass
