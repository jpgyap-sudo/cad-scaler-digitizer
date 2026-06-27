"""
Digitizer Config — bridge between training feedback and the digitizer pipeline.
The digitizer imports get_param() instead of using hardcoded OpenCV values.
When the training feedback system adjusts parameters, they take effect 
on the NEXT digitize call without restarting the container.
"""

import os
import json
import logging
from typing import Any, Optional

logger = logging.getLogger("digitizer_config")

# In-memory cache, loaded once from DB at first call
_cache: dict[str, Any] = {}
_cache_loaded = False

# Defaults matching the original hardcoded values in routes.py
_DEFAULTS: dict[str, Any] = {
    "canny_low": 50,
    "canny_high": 150,
    "edge_dilation_kernel": 3,
    "min_contour_area": 50,
    "scale_correction_factor": 1.0,
    "ocr_confidence_threshold": 0.5,
    "line_merge_distance": 10,
    "scale_correction_width_cm": 1.0,
    "scale_correction_overall_height_cm": 1.0,
    "scale_correction_depth_cm": 1.0,
}


def _load_from_db():
    """Load parameter state from Postgres into local cache."""
    global _cache_loaded
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT param_key, param_value FROM digitizer_parameters
            ORDER BY updated_at DESC
        """)
        for row in cur.fetchall():
            key = row[0]
            val = row[1]
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            _cache[key] = val
        cur.close()
        conn.close()
        _cache_loaded = True
        logger.debug(f"Loaded {len(_cache)} params from DB")
    except Exception as e:
        logger.warning(f"Could not load digitizer params from DB: {e}")
        _cache_loaded = True  # Don't retry on every call


def get_param(key: str, default: Optional[Any] = None) -> Any:
    """Get a digitizer parameter, falling back to hardcoded default.
    
    Called by the digitize function instead of using hardcoded values.
    First call loads from DB; subsequent calls use cache.
    """
    global _cache_loaded
    if not _cache_loaded:
        _load_from_db()

    # Check DB-loaded value first
    if key in _cache:
        return _cache[key]

    # Check our defaults
    if key in _DEFAULTS:
        return _DEFAULTS[key]

    # Use caller-provided default
    return default


def get_canny_thresholds() -> tuple[int, int]:
    """Get the current Canny edge detection thresholds.
    
    Call this instead of hardcoding cv2.Canny(img, 50, 150).
    The training feedback system adjusts these based on comparison errors.
    """
    low = int(get_param("canny_low", 50))
    high = int(get_param("canny_high", 150))
    return (low, high)


def get_scale_correction(dim_key: str) -> float:
    """Get scale correction factor for a dimension.
    
    If the comparison agent detects that all sofas are detected 5% too wide,
    the training feedback adjusts scale_correction_width_cm to 0.95.
    """
    param_key = f"scale_correction_{dim_key}"
    return float(get_param(param_key, 1.0))
