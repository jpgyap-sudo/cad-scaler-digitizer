"""
Silhouette Gallery — stores one representative Gemini-traced SVG per furniture type.
Updated automatically when a new product is crawled and Gemini generates a silhouette.
Persistence: JSON file in /tmp/cad_digitizer_outputs/silhouette_gallery.json
"""

import json
import os
import logging
from pathlib import Path

logger = logging.getLogger("silhouette_gallery")

GALLERY_PATH = Path(os.environ.get("CAD_OUTPUT_DIR", "/tmp/cad_digitizer_outputs")) / "silhouette_gallery.json"

_gallery: dict[str, dict] = {}
_loaded = False


def _load():
    global _gallery, _loaded
    if _loaded:
        return
    try:
        if GALLERY_PATH.exists():
            _gallery.update(json.loads(GALLERY_PATH.read_text(encoding="utf-8")))
    except Exception as e:
        logger.warning(f"[SilhouetteGallery] Load failed: {e}")
    _loaded = True


def _save():
    try:
        GALLERY_PATH.write_text(json.dumps(_gallery, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[SilhouetteGallery] Save failed: {e}")


def get_gallery() -> dict[str, dict]:
    """Return all gallery entries: {furniture_type: {svg, product_name, handle}}"""
    _load()
    return dict(_gallery)


def update_gallery(furniture_type: str, svg: str, product_name: str = "", handle: str = "") -> None:
    """Update or add a silhouette for a furniture type. Keeps the latest."""
    if not furniture_type or not svg:
        return
    _load()
    _gallery[furniture_type] = {
        "svg": svg,
        "product_name": product_name or f"{furniture_type}",
        "handle": handle,
        "updated_at": __import__("datetime").datetime.now().isoformat(),
    }
    _save()


def get_silhouette(furniture_type: str) -> str:
    """Get the SVG silhouette for a furniture type, or empty string."""
    _load()
    entry = _gallery.get(furniture_type)
    return entry.get("svg", "") if entry else ""
