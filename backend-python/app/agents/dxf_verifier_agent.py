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
import asyncio
import base64
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger("dxf_verifier_agent")

# Gemini configuration loaded from environment
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_OCR_MODEL", "gemini-2.5-pro")


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
import re

_SILHOUETTE_CACHE: dict[str, tuple[str, str]] = {}  # md5 → (svg, dxf_polyline_json)


def _silhouette_cache_key(md5: str) -> tuple[bool, str, str]:
    """Check cache. Returns (cached, svg, dxf_coords)."""
    if md5 in _SILHOUETTE_CACHE:
        svg, coords = _SILHOUETTE_CACHE[md5]
        return True, svg, coords
    return False, "", ""


def _svg_to_dxf_polyline(svg_text: str) -> str:
    """Extract M/L/C/Q path commands from SVG and approximate as polyline vertices.
    
    Returns JSON string of [[x1,y1],[x2,y2],...] suitable for DXF POLYLINE.
    Curves (C, Q, S) are sampled at ~10 segments each.
    """
    paths = re.findall(r'd="([^"]+)"', svg_text, re.I)
    if not paths:
        return "[]"

    points = []
    for d in paths:
        tokens = re.findall(r'[MmLlCcQqSsZz]|-?\d+(?:\.\d+)?|-?\d+\.\d+', d)
        i = 0
        current_x = current_y = 0.0
        start_x = start_y = 0.0

        while i < len(tokens):
            cmd = tokens[i]
            i += 1

            if cmd == 'M':
                if i + 1 < len(tokens):
                    current_x = float(tokens[i]); current_y = float(tokens[i + 1])
                    start_x, start_y = current_x, current_y
                    points.append([current_x, current_y])
                    i += 2
            elif cmd == 'm':
                if i + 1 < len(tokens):
                    current_x += float(tokens[i]); current_y += float(tokens[i + 1])
                    start_x, start_y = current_x, current_y
                    points.append([current_x, current_y])
                    i += 2
            elif cmd == 'L':
                if i + 1 < len(tokens):
                    current_x = float(tokens[i]); current_y = float(tokens[i + 1])
                    points.append([current_x, current_y])
                    i += 2
            elif cmd == 'l':
                if i + 1 < len(tokens):
                    current_x += float(tokens[i]); current_y += float(tokens[i + 1])
                    points.append([current_x, current_y])
                    i += 2
            elif cmd in ('C', 'c', 'Q', 'q', 'S', 's'):
                # Approximate curve with line segments
                if cmd == 'C' and i + 5 < len(tokens):
                    cp1x, cp1y = float(tokens[i]), float(tokens[i+1])
                    cp2x, cp2y = float(tokens[i+2]), float(tokens[i+3])
                    end_x = float(tokens[i+4]); end_y = float(tokens[i+5])
                    _add_cubic_approx(points, current_x, current_y, cp1x, cp1y, cp2x, cp2y, end_x, end_y)
                    current_x, current_y = end_x, end_y
                    i += 6
                elif cmd == 'c' and i + 5 < len(tokens):
                    cp1x = current_x + float(tokens[i]); cp1y = current_y + float(tokens[i+1])
                    cp2x = current_x + float(tokens[i+2]); cp2y = current_y + float(tokens[i+3])
                    end_x = current_x + float(tokens[i+4]); end_y = current_y + float(tokens[i+5])
                    _add_cubic_approx(points, current_x, current_y, cp1x, cp1y, cp2x, cp2y, end_x, end_y)
                    current_x, current_y = end_x, end_y
                    i += 6
                elif cmd == 'Q' and i + 3 < len(tokens):
                    cpx, cpy = float(tokens[i]), float(tokens[i+1])
                    end_x = float(tokens[i+2]); end_y = float(tokens[i+3])
                    _add_quad_approx(points, current_x, current_y, cpx, cpy, end_x, end_y)
                    current_x, current_y = end_x, end_y
                    i += 4
                elif cmd == 'q' and i + 3 < len(tokens):
                    cpx = current_x + float(tokens[i]); cpy = current_y + float(tokens[i+1])
                    end_x = current_x + float(tokens[i+2]); end_y = current_y + float(tokens[i+3])
                    _add_quad_approx(points, current_x, current_y, cpx, cpy, end_x, end_y)
                    current_x, current_y = end_x, end_y
                    i += 4
                else:
                    break
            elif cmd == 'Z' or cmd == 'z':
                if points and len(points) > 1 and (abs(points[-1][0] - start_x) > 0.01 or abs(points[-1][1] - start_y) > 0.01):
                    points.append([start_x, start_y])

    import json
    return json.dumps(points)


def _add_cubic_approx(pts, x0, y0, x1, y1, x2, y2, x3, y3, steps=10):
    for t in range(1, steps + 1):
        s = t / steps
        sx = (1-s)**3 * x0 + 3*(1-s)**2*s * x1 + 3*(1-s)*s**2 * x2 + s**3 * x3
        sy = (1-s)**3 * y0 + 3*(1-s)**2*s * y1 + 3*(1-s)*s**2 * y2 + s**3 * y3
        pts.append([sx, sy])


def _add_quad_approx(pts, x0, y0, x1, y1, x2, y2, steps=8):
    for t in range(1, steps + 1):
        s = t / steps
        sx = (1-s)**2 * x0 + 2*(1-s)*s * x1 + s**2 * x2
        sy = (1-s)**2 * y0 + 2*(1-s)*s * y1 + s**2 * y2
        pts.append([sx, sy])


async def generate_silhouette_svg(
    image_data: bytes,
    furniture_type: str = "",
    width_cm: float = 100,
    height_cm: float = 80,
) -> dict:
    """Generate SVG silhouette + DXF-compatible polyline coordinates.

    Gemini traces the product outline from the photo and returns:
    1. An SVG for frontend display
    2. A polyline vertex list for DXF HERO VIEW
    
    Returns:
        {"svg": "<svg>...", "dxf_coords": "[[x,y],...]", "cached": bool, "error": str}
    """
    if not GEMINI_API_KEY:
        return {"svg": "", "dxf_coords": "[]", "error": "GEMINI_API_KEY not configured"}

    md5 = hashlib.md5(image_data).hexdigest()
    cached, cached_svg, cached_coords = _silhouette_cache_key(md5)
    if cached:
        return {"svg": cached_svg, "dxf_coords": cached_coords, "cached": True, "error": None}

    try:
        b64 = base64.b64encode(image_data).decode()

        prompt = f"""You are a multi-view CAD extractor. Given a photo of a {furniture_type or "furniture product"}, extract ALL visible geometric information and organize it into FOUR views: FRONT, SIDE, TOP, and ISOMETRIC.

PRINCIPLE: From a single 3/4 perspective or front-facing photo, you can:
  - DIRECTLY OBSERVE the front view (the visible face)
  - PARTIALLY ESTIMATE the side view from edge profiles visible in perspective
  - PARTIALLY ESTIMATE the top view from the top surface contour visible in the photo
  - CONSTRUCT the isometric view as a 3D projection where WIDTH goes right-down at 30°, DEPTH goes right-up at 30°, and HEIGHT goes straight up — the front face of the isometric must MATCH the front view in the FRONT panel
  - Tag each component with {{"view": "front"|"side"|"top"|"isometric", "confidence": "observed"|"estimated"}}

Return ONLY valid JSON (no markdown) with this structure:
{{
  "svg": "<svg>...</svg>",
  "components": [{{"name": string, "view": string, "confidence": string, "polyline": [x1,y1, ...]}}, ...],
  "estimated_proportions": {{"width_px": number, "depth_px": number, "height_px": number}}
}}

SVG LAYOUT (1200x300):
- panels[0] x=0-280  (w=280 h=260) = FRONT view — observed from photo, draw at (30, 20)
- panels[1] x=310-590 (w=280 h=260) = SIDE view — estimated from edge profiles, draw at (340, 20)
- panels[2] x=620-890 (w=280 h=260) = TOP view — estimated from top surface, draw at (650, 20)
- panels[3] x=920-1180 (w=280 h=260) = ISOMETRIC — draw at (950, 20), with 260px height available
- Each panel has a thin #e5e7eb line divider at x=295, x=605, x=905

ISOMETRIC CONSTRUCTION (most important rule):
- The isometric must look like a 3D projection of the product
- Front face of isometric = same shape as the front view panel
- Depth edges go up-right at approximately 30 degrees
- Top face is a parallelogram (width x depth)
- Hidden/back edges use dashed style
- For tables: parallelogram tabletop with 4 vertical legs
- For chairs: seat + backrest with depth
- For cabinets: box with depth visible

SVG RULES:
- Each component is its OWN <path> with data-name, data-view, data-confidence attributes
- OBSERVED components: stroke="#1f2937" stroke-width="2" fill="none" — use M,C,Q,L,Z
- ESTIMATED components: stroke="#9ca3af" stroke-width="1.5" stroke-dasharray="4,2" fill="none"
- Center and scale to fill ~80% of each panel's width/height

COMPONENT NAMES: tabletop, left_leg, right_leg, back_left_leg, back_right_leg, seat, backrest, base — whatever fits the product

POLYLINE RULES:
- Each polyline: flat [x1,y1, x2,y2, ...] in the 1200x300 SVG coordinate space
- Curves sampled every ~5px as short straight segments
- Closed: first and last point identical; minimum 4 points

estimated_proportions: your best guess of the product's width_px, depth_px, height_px in pixel units (for scale reference of the isometric)

Example:
{{
  "svg": "<svg viewBox='0 0 1200 300' xmlns='http://www.w3.org/2000/svg'>...</svg>",
  "components": [
    {{"name": "tabletop", "view": "front", "confidence": "observed", "polyline": [60,100, 280,100, 280,130, 60,130, 60,100]}},
    {{"name": "tabletop", "view": "isometric", "confidence": "estimated", "polyline": [950,90, 1120,70, 1160,100, 990,120, 950,90]}},
    {{"name": "left_leg_front", "view": "isometric", "confidence": "estimated", "polyline": [960,120, 970,120, 970,250, 960,250, 960,120]}},
    {{"name": "right_leg_back", "view": "isometric", "confidence": "estimated", "polyline": [1145,82, 1155,82, 1155,212, 1145,212, 1145,82]}}
  ],
  "estimated_proportions": {{"width_px": 220, "depth_px": 70, "height_px": 140}}
}}

Return ONLY this JSON. No markdown, no explanation."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        payload = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            ]}]
        }

        _timeout = int(os.environ.get("GEMINI_TIMEOUT", "60"))
        _max_retries = int(os.environ.get("GEMINI_RETRIES", "5"))
        _fallback_model = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
        resp = None
        _model_used = GEMINI_MODEL
        for attempt in range(_max_retries):
            try:
                _active_model = _fallback_model if attempt >= 3 else _model_used
                _active_url = f"https://generativelanguage.googleapis.com/v1beta/models/{_active_model}:generateContent"
                async with httpx.AsyncClient(timeout=_timeout) as client:
                    resp = await client.post(_active_url, params={"key": GEMINI_API_KEY}, json=payload)
                if resp.status_code == 200:
                    break
                if resp.status_code not in (429, 500, 502, 503):
                    break
                _delay = min(2 ** attempt, 8)
                if attempt < _max_retries - 1:
                    await asyncio.sleep(_delay)
            except Exception:
                if attempt < _max_retries - 1:
                    await asyncio.sleep(min(2 ** attempt, 8))
                else:
                    raise
        if resp is None or resp.status_code != 200:
            code = resp.status_code if resp else "no_response"
            body = resp.text[:500] if resp and hasattr(resp, 'text') else "N/A"
            logger.error(f"[DXFVerifier] Gemini HTTP {code}: {body}")
            return {"svg": "", "dxf_coords": "[]", "error": f"Gemini HTTP {code}"}

        _raw = resp.json()
        text = _raw.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            logger.error(f"[DXFVerifier] Empty Gemini response. Full response: {json.dumps(_raw)[:500]}")
            return {"svg": "", "dxf_coords": "[]", "error": "Empty Gemini response"}

        # Parse JSON from response
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()

        import json as json_mod
        
        # Parse JSON response (multi-view format: {svg, components[{name, view, confidence, polyline}]})
        svg = ""
        views: dict[str, list] = {"front": [], "side": [], "top": [], "isometric": []}
        estimated_proportions = {}
        try:
            parsed = json_mod.loads(cleaned)
            svg = parsed.get("svg", "") or ""
            components = parsed.get("components", []) or []
            estimated_proportions = parsed.get("estimated_proportions", {})
            for comp in components:
                view = comp.get("view", "front")
                poly = comp.get("polyline", [])
                if isinstance(poly, list) and len(poly) > 2:
                    if view in views:
                        views[view].extend(poly)
                        views[view].append(poly[0])  # close
        except Exception:
            svg = cleaned

        # SVG fallback wrapper
        if svg and "<svg" not in svg.lower():
            svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="100%" height="100%">
  <rect width="400" height="300" fill="#ffffff"/>
  <g stroke="#1f2937" stroke-width="2" fill="none">{svg}</g></svg>"""

        # Build dxf_coords: [[x1,y1],[x2,y2],...] from all views for hero view
        dxf_flat = []
        for view_data in views.values():
            # view_data is flat [x1,y1,x2,y2,...] — convert to [[x1,y1],[x2,y2],...]
            flat_pts = list(view_data)
            for i in range(0, len(flat_pts) - 1, 2):
                dxf_flat.append([flat_pts[i], flat_pts[i+1]])

        if not dxf_flat and svg:
            # Fallback: extract polyline from SVG path data
            import re
            paths = re.findall(r'd="([^"]+)"', svg, re.I)
            for d in paths:
                tokens = re.findall(r'[MmLlCcQqSsZzHhVvLl]|-?\d+(?:\.\d+)?', d)
                pts = []
                cx = cy = sx = sy = 0.0
                i = 0
                while i < len(tokens):
                    cmd = tokens[i]; i += 1
                    if cmd == 'M' and i+1 < len(tokens):
                        cx, cy = float(tokens[i]), float(tokens[i+1]); i+=2
                        sx, sy = cx, cy; pts.append([cx, cy])
                    elif cmd == 'L' and i+1 < len(tokens):
                        cx, cy = float(tokens[i]), float(tokens[i+1]); i+=2
                        pts.append([cx, cy])
                    elif cmd in ('Z','z') and pts and (abs(pts[-1][0]-sx)>0.5 or abs(pts[-1][1]-sy)>0.5):
                        pts.append([sx, sy]); break
                    elif cmd in ('C','c') and i+5 < len(tokens):
                        if cmd == 'c':
                            ex = cx+float(tokens[i+4]); ey = cy+float(tokens[i+5])
                        else:
                            ex, ey = float(tokens[i+4]), float(tokens[i+5])
                        for s in range(1,13):
                            t = s/12; u=1-t
                            px = u**3*cx + 3*u**2*t*float(tokens[i]) + 3*u*t**2*float(tokens[i+2]) + t**3*ex
                            py = u**3*cy + 3*u**2*t*float(tokens[i+1]) + 3*u*t**2*float(tokens[i+3]) + t**3*ey
                            pts.append([px, py])
                        cx, cy = ex, ey; i+=6
                    elif cmd in ('Q','q') and i+3 < len(tokens):
                        if cmd == 'q':
                            ex = cx+float(tokens[i+2]); ey = cy+float(tokens[i+3])
                        else:
                            ex, ey = float(tokens[i+2]), float(tokens[i+3])
                        for s in range(1,10):
                            t = s/9; u=1-t
                            px = u**2*cx + 2*u*t*float(tokens[i]) + t**2*ex
                            py = u**2*cy + 2*u*t*float(tokens[i+1]) + t**2*ey
                            pts.append([px, py])
                        cx, cy = ex, ey; i+=4
                    elif cmd in ('H','h') and i < len(tokens):
                        cx = float(tokens[i]) if cmd=='H' else cx+float(tokens[i]); i+=1
                        pts.append([cx, cy])
                    elif cmd in ('V','v') and i < len(tokens):
                        cy = float(tokens[i]) if cmd=='V' else cy+float(tokens[i]); i+=1
                        pts.append([cx, cy])
                if len(pts) > 2:
                    dxf_flat.extend(pts)
                    dxf_flat.append(pts[0])

        dxf_coords = json_mod.dumps(dxf_flat)

        _SILHOUETTE_CACHE[md5] = (svg, dxf_coords)
        return {"svg": svg, "dxf_coords": dxf_coords, "views": views, "estimated_proportions": estimated_proportions, "cached": False, "error": None}

    except Exception as e:
        logger.error(f"[DXFVerifier] Silhouette SVG failed: {e}")
        return {"svg": "", "dxf_coords": "[]", "error": str(e)}


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

        _t = int(os.environ.get("GEMINI_TIMEOUT", "60"))
        _m_r = int(os.environ.get("GEMINI_RETRIES", "5"))
        _fallback_m = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
        resp = None
        for _att in range(_m_r):
            model = _fallback_m if _att >= 3 else GEMINI_MODEL
            u = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                async with httpx.AsyncClient(timeout=_t) as client:
                    resp = await client.post(u, params={"key": GEMINI_API_KEY}, json=payload)
                if resp.status_code == 200:
                    break
                if resp.status_code not in (429, 500, 502, 503):
                    break
                if _att < _m_r - 1:
                    await asyncio.sleep(min(2 ** _att, 8))
            except Exception:
                if _att < _m_r - 1:
                    await asyncio.sleep(min(2 ** _att, 8))
                else:
                    raise
        if resp is None or resp.status_code != 200:
            code = resp.status_code if resp else "no_response"
            logger.error(f"[DXFVerifier] Gemini HTTP {code}")
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
