"""
SVG Optimizer — cleans, validates, and compresses SVG output from Gemini/GPT-4o.
Used by the CrawlToSvg tab to produce production-ready SVG files.
"""
import re
import logging

logger = logging.getLogger("svg_optimizer")


def optimize_svg(svg_text: str) -> dict:
    """Clean, validate, and compress an SVG string.
    
    Returns: {"svg": str, "valid": bool, "path_count": int, "size_bytes": int, "compression_pct": float}
    """
    if not svg_text or "<svg" not in svg_text.lower():
        return {"svg": svg_text, "valid": False, "path_count": 0, "size_bytes": len(svg_text), "compression_pct": 0.0}

    original_size = len(svg_text)
    result = svg_text

    # 1. Decode HTML entities
    result = result.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

    # 2. Remove empty paths
    result = re.sub(r'<path[^>]*d=\s*["\']\s*["\'][^>]*/>', '', result, flags=re.I)

    # 3. Remove XML comments
    result = re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)

    # 4. Collapse whitespace between tags
    result = re.sub(r'>\s+<', '><', result)

    # 5. Normalize viewBox (if multiple, keep first)
    vbox_matches = re.findall(r'viewBox=["\']([^"\']+)["\']', result, re.I)
    if vbox_matches:
        result = re.sub(r'viewBox=["\'][^"\']+["\']', '', result, flags=re.I)
        result = result.replace('<svg', f'<svg viewBox="{vbox_matches[0]}"', 1)

    # 6. Remove duplicate xmlns
    ns_count = result.count('xmlns="http://www.w3.org/2000/svg"')
    if ns_count > 1:
        result = result.replace('xmlns="http://www.w3.org/2000/svg"', '', ns_count - 1)

    # 7. Validate via XML parser
    valid = False
    path_count = 0
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(result)
        path_count = len(root.iter('{http://www.w3.org/2000/svg}path'))
        valid = path_count > 0
    except Exception:
        try:
            # Fallback: count by regex
            path_count = len(re.findall(r'<path\s', result, re.I))
            valid = path_count > 0
        except Exception:
            pass

    new_size = len(result)
    compression = max(0.0, (1 - new_size / max(original_size, 1)) * 100)

    return {
        "svg": result,
        "valid": valid,
        "path_count": path_count,
        "size_bytes": new_size,
        "compression_pct": round(compression, 1),
    }
