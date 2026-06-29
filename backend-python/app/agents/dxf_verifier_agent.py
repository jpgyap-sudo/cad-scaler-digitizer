"""
DXF Verifier Agent — Semantic Cloud Verification of DXF Output
================================================================
Sends both the source product photo and the rendered DXF line drawing to
Gemini 2.5 Flash for semantic comparison. Gemini judges whether the DXF
correctly represents the product — not by comparing pixels, but by
understanding the MEANING of both representations.

Usage:
    from app.agents.dxf_verifier_agent import verify_dxf_with_gemini
    result = await verify_dxf_with_gemini(product_image_cv, dxf_raster_cv,
                                           furniture_type="rectangular_table",
                                           page_dimensions={"width_cm": 120, ...})

The output is a dict with:
    shape_match       (0.0-1.0): does the DXF outline match the product's shape?
    component_score   (0.0-1.0): are all visible components captured?
    proportion_score  (0.0-1.0): are component proportions correct?
    issues            (list[str]): specific discrepancies found
    explanation       (str): brief summary from Gemini
    performed         (bool): whether verification actually ran
"""

import os
import json
import base64
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger("dxf_verifier_agent")

# Gemini configuration loaded from environment
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_OCR_MODEL", "gemini-2.5-flash")


def _build_prompt(
    furniture_type: str,
    page_dimensions: Optional[dict],
) -> str:
    """Build the Gemini prompt for DXF verification."""
    dims_hint = ""
    if page_dimensions:
        w = page_dimensions.get("width_cm", 0)
        d = page_dimensions.get("depth_cm", 0) or page_dimensions.get("length_cm", 0)
        h = page_dimensions.get("overall_height_cm", 0)
        if w and h:
            dims_hint = f" Reported dimensions: {w:.0f}x{d:.0f}x{h:.0f}cm (widthxdepthxheight)."

    return f"""You are a CAD quality inspector. Compare the PRODUCT PHOTO (first image) against the DXF LINE DRAWING (second image).

Furniture type: {furniture_type or "unknown"}
{dims_hint}

Judge the DXF on these criteria and return ONLY valid JSON (no markdown):

{{
  "shape_match": <0.0-1.0: does the DXF outline match the product's shape? 1.0=perfect outline>,
  "component_score": <0.0-1.0: does the DXF capture all visible components (legs, back, arms, shelves, drawers, etc.)?>,
  "proportion_score": <0.0-1.0: are the proportions of each component correct relative to the whole?>,
  "issues": [<list of specific discrepancies as strings, max 5>],
  "explanation": "<brief summary of the biggest issue or 'DXF matches product correctly'>"
}}"""


def _render_to_jpeg_b64(img: Any, quality: int = 85) -> str:
    """Convert OpenCV image to base64-encoded JPEG."""
    import cv2
    _, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return base64.b64encode(buf.tobytes()).decode()


import hashlib

_SILHOUETTE_CACHE: dict[str, str] = {}  # md5 of image_url → SVG string


async def generate_silhouette_svg(
    image_data: bytes,
    furniture_type: str = "",
    width_cm: float = 100,
    height_cm: float = 80,
) -> dict:
    """Generate a clean SVG silhouette of the product using Gemini 2.5 Flash.

    Gemini traces the product outline from the photo and returns an SVG path.
    The result is cached by image MD5 to avoid re-calls for the same image.

    Returns:
        {"svg": "<svg>...</svg>", "cached": False, "error": None}
    """
    if not GEMINI_API_KEY:
        return {"svg": "", "error": "GEMINI_API_KEY not configured"}

    # Check cache
    md5 = hashlib.md5(image_data).hexdigest()
    cached = _SILHOUETTE_CACHE.get(md5)
    if cached:
        return {"svg": cached, "cached": True, "error": None}

    try:
        import base64
        b64 = base64.b64encode(image_data).decode()

        prompt = f"""You are a product outline tracer. Given a photo of a {furniture_type or "furniture product"}, trace its outermost silhouette and return ONLY valid SVG markup (no markdown, no explanation).

The SVG must be:
- 400x300 viewBox
- White background (#ffffff)
- A single <path> or group of <path> elements in dark gray (#1f2937) with stroke-width=2, fill=none
- Only the OUTERMOST contour(s) of the main product (ignore background items, shadows, small accessories)
- Use relative/absolute bezier curves (M, C, Q, L, Z) for smooth contour tracing
- The product should be centered and scaled to fill roughly 80% of the viewport
- If there are multiple separate components visible (e.g. 4 legs, a tabletop, a backrest), trace each as its own <path> in the same group

Return ONLY the raw SVG markup. No html wrapping, no markdown."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        payload = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            ]}]
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, params={"key": GEMINI_API_KEY}, json=payload)

        if resp.status_code != 200:
            return {"svg": "", "error": f"Gemini HTTP {resp.status_code}"}

        text = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            return {"svg": "", "error": "Empty Gemini response"}

        # Extract SVG from response (handle markdown wrapping)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()

        # Ensure it's valid SVG
        if "<svg" not in cleaned.lower():
            cleaned = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="100%" height="100%">
  <rect width="400" height="300" fill="#ffffff"/>
  <g transform="translate(10, 10)">{cleaned}</g>
</svg>"""

        _SILHOUETTE_CACHE[md5] = cleaned
        return {"svg": cleaned, "cached": False, "error": None}

    except Exception as e:
        logger.error(f"[DXFVerifier] Silhouette SVG failed: {e}")
        return {"svg": "", "error": str(e)}


def _parse_gemini_response(response_text: str) -> dict:
    """Parse Gemini's JSON response, handling markdown wrapping."""
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
    if cleaned.rstrip().endswith("```"):
        cleaned = cleaned.rstrip()[:-3]
    cleaned = cleaned.strip()

    result = json.loads(cleaned)
    return {
        "shape_match": min(1.0, max(0.0, float(result.get("shape_match", 0.5)))),
        "component_score": min(1.0, max(0.0, float(result.get("component_score", 0.5)))),
        "proportion_score": min(1.0, max(0.0, float(result.get("proportion_score", 0.5)))),
        "issues": result.get("issues", [])[:5],
        "explanation": result.get("explanation", ""),
        "performed": True,
    }


async def verify_dxf_with_gemini(
    product_image: Any,
    dxf_raster: Any,
    furniture_type: str = "",
    page_dimensions: Optional[dict] = None,
) -> dict:
    """Verify DXF correctness by sending both images to Gemini 2.5 Flash.

    Args:
        product_image: OpenCV image (numpy array) of the source product photo
        dxf_raster: OpenCV image (numpy array) of the rendered DXF
        furniture_type: The expected furniture type (e.g. 'rectangular_table')
        page_dimensions: Dict with width_cm, depth_cm, overall_height_cm

    Returns:
        dict with shape_match, component_score, proportion_score, issues, explanation, performed
    """
    import cv2

    if not GEMINI_API_KEY:
        logger.warning("[DXFVerifier] GEMINI_API_KEY not configured")
        return {
            "shape_match": 0.5, "component_score": 0.5, "proportion_score": 0.5,
            "issues": ["GEMINI_API_KEY not configured"], "explanation": "",
            "performed": False,
        }

    try:
        # Resize DXF to match product image dimensions
        h, w = product_image.shape[:2]
        dxf_resized = cv2.resize(dxf_raster, (w, h))

        # Encode both images to base64 JPEG
        prod_b64 = _render_to_jpeg_b64(product_image)
        dxf_b64 = _render_to_jpeg_b64(dxf_resized)

        # Build prompt
        prompt = _build_prompt(furniture_type, page_dimensions)

        # Call Gemini
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": prod_b64}},
                    {"inline_data": {"mime_type": "image/jpeg", "data": dxf_b64}},
                ]
            }]
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, params={"key": GEMINI_API_KEY}, json=payload)

        if resp.status_code != 200:
            logger.error(f"[DXFVerifier] Gemini HTTP {resp.status_code}: {resp.text[:200]}")
            return {
                "shape_match": 0.5, "component_score": 0.5, "proportion_score": 0.5,
                "issues": [f"Gemini HTTP {resp.status_code}"], "explanation": "",
                "performed": False,
            }

        raw = resp.json()
        candidates = raw.get("candidates", [])
        if not candidates:
            return {
                "shape_match": 0.5, "component_score": 0.5, "proportion_score": 0.5,
                "issues": ["No candidates in Gemini response"], "explanation": "",
                "performed": False,
            }

        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            return {
                "shape_match": 0.5, "component_score": 0.5, "proportion_score": 0.5,
                "issues": ["Empty Gemini response"], "explanation": "",
                "performed": False,
            }

        result = _parse_gemini_response(text)
        logger.info(
            f"[DXFVerifier] {furniture_type}: shape={result['shape_match']:.2f} "
            f"comp={result['component_score']:.2f} prop={result['proportion_score']:.2f} "
            f"issues={len(result['issues'])}"
        )
        return result

    except Exception as e:
        logger.error(f"[DXFVerifier] Verification failed: {e}")
        return {
            "shape_match": 0.5, "component_score": 0.5, "proportion_score": 0.5,
            "issues": [f"Verification error: {e}"], "explanation": "",
            "performed": False,
        }
