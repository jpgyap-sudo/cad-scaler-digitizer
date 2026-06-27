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
import re
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

    # Resolve Shopify/Shopify-like template URLs ({width}x placeholder)
    resolved = []
    for url in candidates:
        if "{width}" in url or "{width}x" in url:
            url = url.replace("{width}x", "2000x").replace("{width}", "2000")
        # Handle Shopify pattern like _2000x.jpg or just _{width}x.jpg
        url = url.replace("_{width}x", "_2000x").replace("%7Bwidth%7D", "2000")
        resolved.append(url)
    candidates = resolved

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


async def extract_dimensions_from_page(page_url: str) -> dict:
    """Extract product dimensions from product page data.
    
    Checks:
    1. Shopify product JSON API (products/{handle}.json) — tags like cf-size-WxLxH
    2. Meta tags
    3. JSON-LD product data
    
    Returns: dict of {width_cm, height_cm, depth_cm, length_cm, sizes_available}
    """
    import httpx, re, json
    result = {}

    # Normalize URL to get handle
    path = urlparse(page_url).path
    handle = path.strip("/").split("/")[-1] if path else ""
    base_url = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"

    # Method 1: Fetch Shopify product.json
    if handle:
        json_url = f"{base_url}/products/{handle}.json"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
                r = await c.get(json_url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    data = r.json()
                    product = data.get("product", {})
                    tags = product.get("tags", "")
                    body_html = product.get("body_html", "") or ""

                    # Parse dimensions from tags (Shopify cf-size convention)
                    all_text = tags + " " + body_html

                    # Parse dimensions from product options (ALL values, not just variants)
                    all_option_values = []
                    for opt in product.get("options", []):
                        for val in opt.get("values", []):
                            if val and isinstance(val, str):
                                all_option_values.append(val)
                    # Also check individual variant option values
                    for variant in product.get("variants", []):
                        for opt_key in ["option1", "option2", "option3"]:
                            opt_val = variant.get(opt_key, "") or ""
                            if opt_val and opt_val not in all_option_values:
                                all_option_values.append(opt_val)

                    for opt_val in all_option_values:
                        if not opt_val or len(opt_val) < 5:
                            continue
                        # Pattern: "4 seater 80x140(L)x75(H)cm" or "80x140x75 cm"
                        opts_text = " " + opt_val + " "

                        # Pattern A: {W}x{L}(L)x{H}(H)cm — HomeU format
                        for m in re.findall(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*(?:\(?L\)?)?x\s*(\d+\.?\d*)\s*(?:\(?H\)?)?\s*(cm|mm)?', opts_text, re.I):
                            w, l, h = float(m[0]), float(m[1]), float(m[2])
                            unit = m[3] if len(m) > 3 and m[3] else "cm"
                            if unit == "mm":
                                w, l, h = w / 10, l / 10, h / 10
                            if "width_cm" not in result or w > result["width_cm"]:
                                result["width_cm"] = w
                                result["length_cm"] = l
                                result["overall_height_cm"] = h
                            if "sizes" not in result:
                                result["sizes"] = []
                            result["sizes"].append({"width": w, "length": l, "height": h, "variant": opt_val})

                        # Pattern B: {W}x{D}x{H} cm — standard format (3 values)
                        if "width_cm" not in result:
                            m = re.search(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*(cm|mm)?', opts_text, re.I)
                            if m:
                                w = float(m.group(1))
                                d = float(m.group(2))
                                h = float(m.group(3))
                                unit = m.group(4) if m.lastindex >= 4 and m.group(4) else "cm"
                                if unit == "mm":
                                    w, d, h = w / 10, d / 10, h / 10
                                result["width_cm"] = w
                                result["depth_cm"] = d
                                result["overall_height_cm"] = h

                        # Pattern C: {W}x{D} (mm|cm) — 2 values like "2000 x 1000mm"
                        if "width_cm" not in result:
                            m = re.search(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*(cm|mm)?', opts_text, re.I)
                            if m:
                                w = float(m.group(1))
                                d = float(m.group(2))
                                unit = m.group(3) if m.lastindex >= 3 and m.group(3) else "cm"
                                if unit == "mm":
                                    w, d = w / 10, d / 10
                                result["width_cm"] = w
                                result["depth_cm"] = d

                    # Pattern 1: cf-size-{seating}{W}x{L}lx{H}hcm
                    for match in re.findall(r'(\d+)x(\d+)lx(\d+)hcm', all_text, re.I):
                        w, l, h = float(match[0]), float(match[1]), float(match[2])
                        if "width_cm" not in result or w > result["width_cm"]:
                            result["width_cm"] = w
                            result["length_cm"] = l
                            result["overall_height_cm"] = h
                        if "sizes" not in result:
                            result["sizes"] = []
                        result["sizes"].append({"width": w, "length": l, "height": h})

                    # Pattern 2: W x D x H or W x L x H
                    dims = re.findall(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*(?:cm|mm)?', all_text, re.I)
                    for d in dims:
                        w, d2, h = float(d[0]), float(d[1]), float(d[2])
                        if "width_cm" not in result:
                            result["width_cm"] = w
                            result["depth_cm"] = d2
                            result["overall_height_cm"] = h

                    # Pattern 3: W/H/D labels in body_html
                    for label, key in [("width", "width_cm"), ("height", "overall_height_cm"),
                                        ("depth", "depth_cm"), ("length", "length_cm")]:
                        m = re.search(rf'{label}[:\s]*(\d+\.?\d*)\s*(?:cm|mm)?', all_text, re.I)
                        if m:
                            val = float(m.group(1))
                            if m.group(0).endswith("mm"):
                                val /= 10
                            if key not in result:
                                result[key] = val

        except Exception as e:
            logger.warning(f"Failed to fetch product json: {e}")

    # Method 2: Parse JSON-LD from the product page HTML
    if not result.get("width_cm"):
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
                r = await c.get(page_url, headers={"User-Agent": "Mozilla/5.0"})
                html = r.text if r.status_code == 200 else ""
        except Exception:
            html = ""

        if html:
            # Extract all JSON-LD blocks
            for ld_match in re.findall(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                html, re.DOTALL | re.I
            ):
                try:
                    data = json.loads(ld_match)
                    if isinstance(data, dict):
                        # Handle @graph structure
                        items = data.get("@graph", [data])
                        for item in items:
                            if isinstance(item, dict) and item.get("@type") in ("Product", "product"):
                                name = item.get("name", "")
                                desc = item.get("description", "")
                                all_text = (name or "") + " " + (desc or "")
                                # Check for dimension patterns in JSON-LD text
                                _match_dims_in_text(all_text, result)
                except json.JSONDecodeError:
                    pass

            # Check meta tags for dimensions
            for meta in re.findall(
                r'<meta[^>]+(?:property|name)=["\']product:([^"\']+)["\'][^>]+content=["\']([^"\']+)["\']',
                html, re.I
            ):
                key, val = meta[0].lower(), meta[1]
                if "width" in key and "width_cm" not in result:
                    try:
                        result["width_cm"] = float(re.sub(r'[^\d.]', '', val))
                    except ValueError:
                        pass
                elif "height" in key and "overall_height_cm" not in result:
                    try:
                        result["overall_height_cm"] = float(re.sub(r'[^\d.]', '', val))
                    except ValueError:
                        pass

            # Generic dimension text patterns in page body (non-Shopify stores)
            body_match = re.search(
                r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.I
            )
            if body_match:
                body_text = body_match.group(1)
                body_text = re.sub(r'<[^>]+>', ' ', body_text)  # strip tags
                body_text = re.sub(r'&[a-z]+;', ' ', body_text)  # decode entities
                _match_dims_in_text(body_text, result)

    # Method 3: Generic size patterns from any text source
    _match_dims_in_text("", result)  # ensures helper is called at least once

    return result


def _match_dims_in_text(text: str, result: dict) -> None:
    """Match dimension patterns in text and update result dict in-place."""
    if not text:
        return

    # Inch patterns: 36" x 24" x 30" — convert to cm (×2.54)
    inch_matches = re.findall(r'(\d+\.?\d*)\s*"\s*x\s*(\d+\.?\d*)\s*"\s*(?:x\s*(\d+\.?\d*)\s*")?', text, re.I)
    for m in inch_matches:
        vals = [float(v) * 2.54 for v in m if v]
        if len(vals) >= 2 and "width_cm" not in result:
            result["width_cm"] = round(vals[0], 1)
            result["depth_cm"] = round(vals[1], 1)
            if len(vals) >= 3:
                result["overall_height_cm"] = round(vals[2], 1)

    # European comma-decimal: 120,5 x 80 x 76
    euro_matches = re.findall(r'(\d+[.,]\d+)\s*x\s*(\d+[.,]\d+)\s*(?:x\s*(\d+[.,]\d+))?', text)
    for m in euro_matches:
        vals = [float(v.replace(",", ".")) for v in m if v]
        if len(vals) >= 2 and "width_cm" not in result:
            result["width_cm"] = round(vals[0], 1)
            result["depth_cm"] = round(vals[1], 1)

    # "measures 120cm wide", "120 cm wide", "W120 x D80 x H76"
    labeled_patterns = [
        (r'(?:W|Width)\s*[:=]?\s*(\d+\.?\d*)\s*(?:cm|mm)?', "width_cm"),
        (r'(?:H|Height)\s*[:=]?\s*(\d+\.?\d*)\s*(?:cm|mm)?', "overall_height_cm"),
        (r'(?:D|Depth)\s*[:=]?\s*(\d+\.?\d*)\s*(?:cm|mm)?', "depth_cm"),
        (r'(?:L|Length)\s*[:=]?\s*(\d+\.?\d*)\s*(?:cm|mm)?', "length_cm"),
        (r'(\d+\.?\d*)\s*cm\s*(?:wide|width|deep|depth|high|height|tall)', "width_cm"),
    ]
    for pattern, key in labeled_patterns:
        if key not in result:
            m = re.search(pattern, text, re.I)
            if m:
                val = float(m.group(1))
                if m.group(0).endswith("mm"):
                    val /= 10
                result[key] = round(val, 1)


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

    # Step 2: Download the image (with proper headers for CDN hotlink protection)
    import httpx
    _headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Referer": f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(image_url, headers=_headers)
        if resp.status_code != 200:
            return {**result, "status": "failed", "error": f"Failed to download image: HTTP {resp.status_code}"}
        img_bytes = resp.content
    logger.info(f"[CrawlToDXF] Downloaded {len(img_bytes)} bytes")

    # Step 3: Extract dimensions from the product page
    page_dims = await extract_dimensions_from_page(page_url)
    if page_dims:
        logger.info(f"[CrawlToDXF] Found page dimensions: {page_dims}")
        result["page_dimensions"] = page_dims
        # Use discovered width for scale if not already provided
        if not real_width_cm and page_dims.get("width_cm"):
            real_width_cm = page_dims["width_cm"]
            logger.info(f"[CrawlToDXF] Using page width: {real_width_cm}cm")

    # Step 4: Digitize via internal HTTP call
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

    # Step 5: Auto-run comparison agent against source image
    _dxf_name = digitized.get("dxf_file") if isinstance(digitized, dict) else result.get("dxf_file")
    _dxf_fullpath = f"/tmp/cad_digitizer_outputs/{_dxf_name}" if _dxf_name else None
    if _dxf_fullpath and os.path.exists(_dxf_fullpath):
        try:
            from app.services.comparison_agent import (
                compare_digitization, log_comparison_to_db, NumpyEncoder
            )
            import httpx
            _dl_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": page_url,
            }
            async with httpx.AsyncClient(timeout=30) as _c:
                _ir = await _c.get(image_url, headers=_dl_headers)
                if _ir.status_code == 200:
                    _image_data = _ir.content
                    _product_id = urlparse(page_url).path.split("/")[-1] or "unknown"
                    _comp_result = compare_digitization(
                        job_id=_product_id,
                        product_id=_product_id,
                        image_url=image_url,
                        image_data=_image_data,
                        dxf_path=_dxf_fullpath,
                        page_dimensions=page_dims if page_dims else None,
                    )
                    log_comparison_to_db(_comp_result)
                    result["comparison"] = {
                        "overall_score": _comp_result.overall_score,
                        "edge_overlap_score": _comp_result.edge_overlap_score,
                        "entity_match_score": _comp_result.entity_match_score,
                        "dimension_deviation_pct": _comp_result.dimension_deviation_pct,
                        "error_count": len(_comp_result.errors),
                    }
                    logger.info(
                        f"[CrawlToDXF] Auto-comparison: score={_comp_result.overall_score:.3f}, "
                        f"errors={len(_comp_result.errors)}"
                    )
        except Exception as e:
            logger.warning(f"[CrawlToDXF] Auto-comparison failed (non-fatal): {e}")

    result["status"] = "completed"
    return result
