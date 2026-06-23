"""
Hybrid Engine: Combines OpenCV (geometry) + OpenAI Vision (semantic understanding)
for maximum accuracy.

Pipeline:
1. OpenCV detects lines, circles, rectangles (exact geometry)
2. OpenAI Vision analyzes the image for furniture type, dimensions, views
3. Cross-validation merges results with confidence scoring
"""
import base64
import json
import os
import re
from pathlib import Path
from typing import Optional, List, Tuple, Any

import cv2
import numpy as np
import httpx
from PIL import Image

from .vision import (
    load_gray, preprocess, detect_lines, detect_circles,
    detect_rectangles, ocr_dimensions, normalize_lines
)
from .furniture_classifier import classify_furniture
from .dxf_writer import (
    save_generic, save_round_pedestal_table,
    save_rectangular_table, save_cabinet, save_sofa
)

# Dimension regex for parsing AI responses
DIM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(cm|mm|m|in|ft)?\s*(dia|diameter|h|height|w|width|d|depth|thk|thickness|l|length)?", re.I)

AI_SYSTEM_PROMPT = """You are a professional CAD engineer analyzing a furniture drawing.

You see the same image that OpenCV processes. Your job is to provide semantic understanding:

1. FURNITURE TYPE: Identify the furniture (round_pedestal_table, rectangular_table, sofa, cabinet, bed_headboard, chair, or generic_2d_furniture)
2. DIMENSIONS: Extract ALL dimension annotations from the image (width, height, depth, diameter, etc.)
3. VIEWS: Identify which views are present (top, front, side)
4. CORRECTIONS: Note any errors in the OpenCV detection (missing lines, wrong circles, etc.)

Return valid JSON:
{
  "furniture_type": "string",
  "confidence": 0.0-1.0,
  "dimensions": [{"name": "string", "value_cm": number, "unit": "cm", "raw": "string"}],
  "views_detected": ["top", "front"],
  "scale_notes": "string",
  "opencv_corrections": "string"
}"""


def _image_to_base64(path: str) -> str:
    """Convert image to base64 for OpenAI API."""
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def _get_image_mime(path: str) -> str:
    ext = Path(path).suffix.lower()
    mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.webp': 'image/webp', '.bmp': 'image/bmp', '.tiff': 'image/tiff'}
    return mime_map.get(ext, 'image/png')


async def analyze_with_openai(image_path: str, api_key: str) -> dict:
    """
    Send image to OpenAI Vision API for semantic analysis.
    Returns structured understanding of the drawing.
    """
    try:
        image_b64 = _image_to_base64(image_path)
        mime = _get_image_mime(image_path)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": AI_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Analyze this furniture drawing and provide structured data as JSON."},
                                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}", "detail": "high"}}
                            ]
                        }
                    ],
                    "max_tokens": 2000,
                    "response_format": {"type": "json_object"}
                }
            )

            if response.status_code != 200:
                print(f"[Hybrid] OpenAI API error {response.status_code}: {response.text[:200]}")
                return {"error": f"API error: {response.status_code}"}

            data = response.json()
            content = data['choices'][0]['message']['content']
            result = json.loads(content)
            result['_raw_response'] = content
            return result

    except Exception as e:
        print(f"[Hybrid] OpenAI analysis failed: {e}")
        return {"error": str(e)}


def _merge_dimensions(opencv_dims: list, ai_dims: list) -> list:
    """Merge dimensions from both sources, deduplicating by raw text."""
    seen = set()
    merged = []

    # AI dims take priority (better OCR)
    for d in ai_dims:
        raw = d.get('raw', '')
        if raw and raw not in seen:
            seen.add(raw)
            merged.append(d)

    # OpenCV dims fill gaps
    for d in opencv_dims:
        raw = d.get('raw', '')
        if raw and raw not in seen:
            seen.add(raw)
            merged.append(d)

    return merged


def _pick_dimension(dims: list, tags: list, fallback: Optional[float] = None) -> Optional[float]:
    """Pick first dimension matching any of the given tags."""
    for d in dims:
        tag = d.get('tag', '')
        if any(t in tag for t in tags):
            return d.get('value_cm', d.get('value', None))
    if fallback is not None:
        return fallback
    vals = [d.get('value_cm', d.get('value', 0)) for d in dims]
    return vals[0] if vals else None


async def process_hybrid(
    image_path: str,
    out_dir: str,
    job_id: str,
    openai_api_key: str,
    real_width_cm: Optional[float] = None,
    real_height_cm: Optional[float] = None,
    furniture_override: Optional[str] = None
) -> dict:
    """
    Hybrid pipeline: OpenCV geometry + OpenAI Vision understanding.
    1. OpenCV detects lines/circles/rectangles
    2. Tesseract/PaddleOCR reads text
    3. OpenAI analyzes image for furniture type + dimensions
    4. Results are cross-validated and merged
    5. DXF generated with best available data
    """
    # STEP 1: OpenCV detection
    img, gray = load_gray(image_path)
    binary = preprocess(gray)
    lines_raw = detect_lines(binary)
    lines = normalize_lines(lines_raw)
    circles = detect_circles(gray)
    rects = detect_rectangles(binary)
    ocr_lines, ocr_dims = ocr_dimensions(image_path)

    # STEP 2: OpenAI Vision analysis
    ai_result = await analyze_with_openai(image_path, openai_api_key)
    ai_error = ai_result.get('error')

    ai_furniture_type = ai_result.get('furniture_type', '') if not ai_error else ''
    ai_confidence = ai_result.get('confidence', 0) if not ai_error else 0
    ai_dimensions = ai_result.get('dimensions', []) if not ai_error else []
    ai_views = ai_result.get('views_detected', []) if not ai_error else []
    ai_corrections = ai_result.get('opencv_corrections', '') if not ai_error else ''

    # STEP 3: Furniture classification (AI preferred, OpenCV fallback)
    if furniture_override:
        furniture = {"type": furniture_override, "confidence": 1.0,
                     "required_dimensions": [], "missing_dimensions": []}
    elif ai_furniture_type and ai_confidence >= 0.5:
        furniture = {
            "type": ai_furniture_type,
            "confidence": ai_confidence,
            "required_dimensions": [],
            "missing_dimensions": [],
            "ai_source": True,
            "opencv_corrections": ai_corrections
        }
    else:
        cv_furniture = classify_furniture(ocr_lines, circles, lines, rects)
        furniture = {**cv_furniture, "ai_source": False}

    # STEP 4: Merge dimensions
    merged_dims = _merge_dimensions(ocr_dims, ai_dimensions)

    # STEP 5: Generate DXF
    out = Path(out_dir)
    dxf_name = f'{job_id}_hybrid.dxf'
    dxf_path = out / dxf_name
    warnings = []

    ftype = furniture['type']
    if ftype == 'round_pedestal_table':
        dia = real_width_cm or _pick_dimension(merged_dims, ['dia', 'diameter', 'width', 'w'], 80.0)
        height = real_height_cm or _pick_dimension(merged_dims, ['h', 'height'], 70.0)
        save_round_pedestal_table(str(dxf_path), top_dia_cm=dia, height_cm=height)
        warnings.append(f"Hybrid reconstruction: Ø{dia:.0f}cm x H{height:.0f}cm")
    elif ftype == 'rectangular_table':
        w = real_width_cm or _pick_dimension(merged_dims, ['w', 'width'], 120.0)
        h = real_height_cm or _pick_dimension(merged_dims, ['h', 'height'], 70.0)
        d = _pick_dimension(merged_dims, ['d', 'depth'], w * 0.67)
        save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
        warnings.append(f"Hybrid reconstruction: {w:.0f}x{d:.0f}x{h:.0f}cm")
    elif ftype == 'cabinet':
        w = real_width_cm or _pick_dimension(merged_dims, ['w', 'width'], 100.0)
        h = real_height_cm or _pick_dimension(merged_dims, ['h', 'height'], 180.0)
        d = _pick_dimension(merged_dims, ['d', 'depth'], 50.0)
        save_cabinet(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h)
    elif ftype == 'sofa':
        w = real_width_cm or _pick_dimension(merged_dims, ['w', 'width'], 200.0)
        h = real_height_cm or _pick_dimension(merged_dims, ['h', 'height'], 85.0)
        sh = _pick_dimension(merged_dims, ['seat', 'seat_height'], 45.0)
        d = _pick_dimension(merged_dims, ['d', 'depth'], 80.0)
        save_sofa(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, seat_height_cm=sh)
    else:
        # Generic: use OpenCV lines + circles + rectangles with scale
        scale = 0.1
        if real_width_cm and lines:
            xs = [p[0] for ln in lines for p in ln]
            if max(xs) > min(xs):
                scale = real_width_cm / (max(xs) - min(xs))
        elif merged_dims and lines:
            first_dim = merged_dims[0].get('value_cm', merged_dims[0].get('value', 0))
            xs = [p[0] for ln in lines for p in ln]
            pixel_length = max(xs) - min(xs) if xs else 1
            if pixel_length > 0:
                scale = first_dim / pixel_length
        save_generic(str(dxf_path), lines, circles, rects, scale)
        warnings.append(f"Generic tracing at scale {scale:.4f} cm/pixel")

    return {
        'job_id': job_id,
        'download': f'/api/download/{dxf_name}',
        'dxf_file': dxf_name,
        'furniture': furniture,
        'detected': {
            'lines': len(lines),
            'circles': len(circles),
            'rectangles': len(rects),
            'dimensions': merged_dims,
            'ocr_lines': ocr_lines[:30],
        },
        'warnings': warnings,
        'hybrid': {
            'enabled': True,
            'ai_available': ai_error is None,
            'ai_furniture': ai_furniture_type or 'N/A',
            'ai_confidence': ai_confidence,
            'views_detected': ai_views,
            'ai_error': ai_error or None,
        }
    }
