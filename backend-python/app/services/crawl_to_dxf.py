"""
Crawl → Digitize → Validate Pipeline
=======================================
Given a product page URL:
  1. Crawls the page (stealth Playwright)
  2. Finds the best product hero image
  3. Downloads and digitizes it
  4. Validates against reference CAD
  5. Returns DXF + validation score

Single endpoint: POST /api/crawl-to-dxf
"""

import os
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("crawl_to_dxf")

# --- Image scoring ---

# Patterns that indicate good product hero images
_HERO_PATTERNS = ["_1000.", "_large.", "_hero.", "_1600x.", "_2000x."]
# Patterns indicating images to skip
_SWATCH_PATTERNS = ["swatch", "navtile", "nav-tile", "bath", "holiday", "cdf73", "eoss_web_navigation"]

def _score_image(filename: str, url: str) -> int:
    """Score an image URL — higher is better for product hero images."""
    low = filename.lower() + url.lower()
    score = 0

    # Penalize swatches and navigation tiles
    for pat in _SWATCH_PATTERNS:
        if pat in low:
            return -100

    # Reward hero image patterns
    for pat in _HERO_PATTERNS:
        if pat in low:
            score += 50

    # Reward product code patterns (letters+numbers like NK198, ML290)
    import re
    codes = re.findall(r'\b([A-Z]{2,3}\d{2,4})\b', filename)
    score += len(codes) * 20

    # Reward larger sizes
    if "_2000x" in low: score += 30
    elif "_1600x" in low: score += 20
    elif "_1000" in low: score += 10

    # Penalize if it contains common non-product keywords
    for kw in ["logo", "icon", "banner", "badge", "story", "about", "press", "sustainability", "career"]:
        if kw in low:
            score -= 30

    # Prefer .jpg over .png (product photos are typically jpg)
    if ".jpg" in low: score += 5

    return score


async def crawl_for_image(page_url: str) -> Optional[str]:
    """Crawl a product page (via HTTP) and return the best product hero image URL.
    Uses direct HTTP fetch + regex — no Playwright dependency needed.
    """
    import httpx
    import re

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(page_url, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"HTTP {resp.status_code} for {page_url}")
                return None
            html = resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch {page_url}: {e}")
        return None

    # Find all image URLs in the HTML
    candidates = []

    # Pattern for <img src="..."> and <source srcset="...">
    img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
    srcset_pattern = re.compile(r'<source[^>]+srcset=["\']([^"\']+)["\']', re.I)
    meta_pattern = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I)

    for match in img_pattern.finditer(html):
        url = match.group(1).strip()
        if url.startswith("//"): url = "https:" + url
        if url.startswith("/"): url = urlparse(page_url).scheme + "://" + urlparse(page_url).netloc + url
        if url.startswith("http"):
            candidates.append(url)

    for match in meta_pattern.finditer(html):
        url = match.group(1).strip()
        if url.startswith("http"):
            candidates.append(url)

    for match in srcset_pattern.finditer(html):
        parts = match.group(1).split(",")
        for part in parts:
            url = part.strip().split(" ")[0]
            if url.startswith("http"):
                candidates.append(url)

    # Deduplicate
    candidates = list(dict.fromkeys(candidates))

    if not candidates:
        logger.warning("No images found on page")
        return None

    # Score and select the best image
    scored = []
    for url in candidates:
        filename = url.split("/")[-1].split("?")[0]
        score = _score_image(filename, url)
        if score > 0:
            scored.append((score, url))

    scored.sort(key=lambda x: x[0], reverse=True)

    if scored:
        best_url = scored[0][1]
        logger.info(f"Best image: {best_url} (score={scored[0][0]})")
        return best_url

    # Fallback: return the first image (preferring og:image)
    fb = [u for u in candidates if "og:image" in str(u)] or candidates
    logger.info(f"Fallback image: {fb[0]}")
    return fb[0]


async def crawl_and_digitize(
    page_url: str,
    furniture_type: str = "furniture",
    real_width_cm: Optional[float] = None,
    reference_geometry: Optional[dict] = None,
) -> dict:
    """Full pipeline: crawl → digitize → validate → return DXF + score.

    Args:
        page_url: Product page URL to crawl
        furniture_type: Type hint for digitizer (sofa, table, chair, etc.)
        real_width_cm: Optional known width for scale calibration
        reference_geometry: Optional DXF geometry for validation

    Returns:
        dict with status, dxf_url, preview_url, dimensions, validation_score
    """
    result = {"status": "pending", "page_url": page_url}

    # Step 1: Crawl for the best product image
    logger.info(f"[CrawlToDXF] Crawling {page_url}")
    image_url = await crawl_for_image(page_url)
    if not image_url:
        return {**result, "status": "failed", "error": "No product image found on page"}
    result["image_url"] = image_url

    # Step 2: Download the image
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(image_url)
        if resp.status_code != 200:
            return {**result, "status": "failed", "error": f"Failed to download image: HTTP {resp.status_code}"}
        img_bytes = resp.content
    logger.info(f"[CrawlToDXF] Downloaded {len(img_bytes)} bytes")

    # Step 3: Digitize via internal HTTP call
    API_BASE = os.environ.get("PYTHON_WORKER_URL", "http://localhost:8001")
    files = {"file": ("product.png", img_bytes, "image/png")}
    params = {"furniture_type": furniture_type}
    if real_width_cm:
        params["real_width_cm"] = str(real_width_cm)

    async with httpx.AsyncClient(timeout=120) as client:
        digitize_resp = await client.post(
            f"{API_BASE}/api/digitize",
            files=files,
            data=params,
        )

    if digitize_resp.status_code != 200:
        err = digitize_resp.text[:200]
        return {**result, "status": "failed", "error": f"Digitize failed: {err}"}

    digitized = digitize_resp.json()
    dxf_file = digitized.get("dxf_file")
    preview_svg = digitized.get("preview_svg")
    download_url = digitized.get("download")

    # Extract dimensions from digitize result
    detected_dims = {}
    if digitized.get("detected_width_cm"):
        detected_dims["width_cm"] = float(digitized["detected_width_cm"])
    if digitized.get("detected_height_cm"):
        detected_dims["overall_height_cm"] = float(digitized["detected_height_cm"])
    if digitized.get("dimensions"):
        dims = digitized["dimensions"]
        if isinstance(dims, dict):
            for k, v in dims.items():
                if isinstance(v, (int, float)) and v > 0:
                    detected_dims[k] = float(v)

    result["dxf_file"] = dxf_file
    result["preview_svg"] = preview_svg
    result["download_url"] = download_url
    result["detected_dimensions"] = detected_dims

    # Step 4: Validate against reference geometry if provided
    validation_score = None
    hallucination_report = None

    if reference_geometry:
        try:
            from app.services.hallucination_verifier import verify_dimensions
            report = verify_dimensions(
                product_id=urlparse(page_url).path.split("/")[-1] or "unknown",
                furniture_type=furniture_type,
                detected_dims=detected_dims,
                reference_geometry=reference_geometry,
            )
            validation_score = report.overall_score
            hallucination_report = {
                "overall_score": report.overall_score,
                "verdicts": {k: {"verdict": v.verdict, "confidence": v.confidence} for k, v in report.verdicts.items()},
                "hallucination_count": report.hallucination_count,
                "verified_count": report.verified_count,
            }
            result["validation"] = hallucination_report
        except Exception as e:
            logger.warning(f"[CrawlToDXF] Validation failed: {e}")

    elif detected_dims:
        # Even without reference, run basic hallucination check
        try:
            from app.services.hallucination_verifier import verify_dimensions
            report = verify_dimensions(
                product_id=urlparse(page_url).path.split("/")[-1] or "unknown",
                furniture_type=furniture_type,
                detected_dims=detected_dims,
            )
            result["hallucination_check"] = {
                "overall_score": report.overall_score,
                "verdicts": {k: {"verdict": v.verdict, "confidence": v.confidence} for k, v in report.verdicts.items()},
            }
        except Exception as e:
            logger.warning(f"[CrawlToDXF] Hallucination check failed: {e}")

    result["status"] = "completed"
    return result
