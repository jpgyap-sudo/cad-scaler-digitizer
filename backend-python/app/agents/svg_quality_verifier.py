"""
SVG Quality Verifier Agent
──────────────────────────
Sends rendered SVG + original product photo to Gemini Vision to score
shape accuracy, component completeness, and proportion correctness.
"""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
from typing import Optional

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_OCR_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_OCR_MODEL", "gemini-2.5-flash")

VERIFIER_PROMPT = """You are reviewing a CAD shop drawing against the original product photo.
Compare MEANING and STRUCTURE — not pixel-perfect match.

Score each 0.0-1.0:
- shape_match: Does the outline match? (round/rect/oval, single/dual pedestal, correct base type)
- component_score: Are all visible parts represented? (legs, tabletop thickness, backrest, shelves, drawers)
- proportion_score: Are relative sizes believable? (leg thickness vs tabletop width, height vs depth ratio)
- view_completeness: Are multiple orthographic views shown? (top + front = good; top + front + side = excellent)

For each specific issue, suggest a parameter correction if you can.

Return ONLY valid JSON:
{
  "shape_match": 0.0-1.0,
  "component_score": 0.0-1.0,
  "proportion_score": 0.0-1.0,
  "view_completeness": 0.0-1.0,
  "issues": ["string description of each problem"],
  "corrections": {
    "param_name": {"current": number_or_null, "suggested": number, "reason": "string"}
  },
  "overall_quality": 0.0-1.0
}"""


QUALITY_WEIGHTS = {
    "shape_match": 0.40,
    "component_score": 0.30,
    "proportion_score": 0.20,
    "view_completeness": 0.10,
}


async def verify_svg_quality(
    product_image_path: str,
    svg_path: str,
    furniture_type: str = "",
    dimensions: Optional[dict] = None,
) -> dict:
    """
    Compare SVG shop drawing against product photo using Gemini Vision.

    Returns dict with shape_match, component_score, proportion_score,
    view_completeness, issues list, corrections dict, overall_quality.
    """
    _default = {
        "shape_match": 0.75, "component_score": 0.75,
        "proportion_score": 0.75, "view_completeness": 0.75,
        "issues": [], "corrections": {}, "overall_quality": 0.75,
        "performed": False,
    }

    if not GEMINI_API_KEY:
        return {**_default, "issues": ["GEMINI_API_KEY not set — verification skipped"]}

    try:
        import httpx

        # Read and encode both images
        with open(product_image_path, "rb") as f:
            photo_b64 = base64.b64encode(f.read()).decode()

        # Convert SVG to PNG raster for Gemini (SVG text is not an image)
        svg_b64 = None
        svg_mime = "image/png"
        try:
            import cairosvg
            svg_png = cairosvg.svg2png(url=svg_path, output_width=800)
            svg_b64 = base64.b64encode(svg_png).decode()
        except Exception:
            # Fallback: send SVG as text in the prompt
            svg_text = Path(svg_path).read_text(encoding="utf-8")[:3000]
            svg_b64 = None

        parts = [
            {"text": VERIFIER_PROMPT},
            {"text": f"\nFurniture type: {furniture_type}"},
        ]
        if dimensions:
            parts.append({"text": f"\nCurrent dimensions (cm): {json.dumps(dimensions)}"})

        parts.append({"text": "\n\nIMAGE 1 — Original product photo:"})
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": photo_b64}})

        if svg_b64:
            parts.append({"text": "\nIMAGE 2 — Generated SVG shop drawing:"})
            parts.append({"inline_data": {"mime_type": svg_mime, "data": svg_b64}})
        else:
            parts.append({"text": f"\nSVG drawing (text):\n{svg_text}"})

        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                params={"key": GEMINI_API_KEY},
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
                },
            )

        if resp.status_code != 200:
            return {**_default, "issues": [f"Gemini HTTP {resp.status_code}"]}

        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(raw)

        # Compute weighted overall if not present
        if "overall_quality" not in result:
            result["overall_quality"] = sum(
                result.get(k, 0.75) * w for k, w in QUALITY_WEIGHTS.items()
            )

        result["performed"] = True
        return result

    except Exception as e:
        return {**_default, "issues": [f"Verifier error: {e}"], "performed": False}


def get_quality_tier(overall_quality: float) -> str:
    """Return 'accept' | 'warn' | 'reject' based on quality score."""
    if overall_quality >= 0.85:
        return "accept"
    elif overall_quality >= 0.65:
        return "warn"
    else:
        return "reject"
