"""
Shared DigitalOcean Spaces upload helper.

Same config/pattern as app/services/crawl_processor.py's _spaces_upload()
(verified working there) - factored out so other features (drawing
history, etc.) don't each reimplement boto3 setup independently.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger("spaces_client")

SPACES_ENDPOINT = os.environ.get("SPACES_ENDPOINT", "https://sgp1.digitaloceanspaces.com")
SPACES_BUCKET = os.environ.get("SPACES_BUCKET", "homeatelierspaces")
SPACES_KEY = os.environ.get("SPACES_KEY", "")
SPACES_SECRET = os.environ.get("SPACES_SECRET", "")
SPACES_CDN_BASE = os.environ.get("SPACES_CDN_BASE", "")

_CONTENT_TYPES = {
    ".svg": "image/svg+xml",
    ".dxf": "application/dxf",
    ".json": "application/json",
    ".png": "image/png",
}


def is_configured() -> bool:
    return bool(SPACES_KEY and SPACES_SECRET)


def upload_file(local_path: Union[str, Path], remote_key: str) -> Optional[str]:
    """Upload a local file to Spaces. Returns the public CDN URL, or None
    if Spaces isn't configured or the upload fails (never raises)."""
    if not is_configured():
        logger.warning("[SpacesClient] Credentials not configured, skipping upload")
        return None
    local_path = Path(local_path)
    if not local_path.exists():
        logger.warning(f"[SpacesClient] Local file not found: {local_path}")
        return None
    try:
        import boto3
        session = boto3.session.Session()
        client = session.client(
            "s3", endpoint_url=SPACES_ENDPOINT,
            aws_access_key_id=SPACES_KEY,
            aws_secret_access_key=SPACES_SECRET,
            region_name="sgp1",
        )
        content_type = _CONTENT_TYPES.get(local_path.suffix.lower(), "application/octet-stream")
        client.upload_file(
            str(local_path), SPACES_BUCKET, remote_key,
            ExtraArgs={"ACL": "public-read", "ContentType": content_type},
        )
        cdn_base = SPACES_CDN_BASE or f"{SPACES_ENDPOINT}/{SPACES_BUCKET}"
        return f"{cdn_base}/{remote_key}"
    except Exception as e:
        logger.error(f"[SpacesClient] Upload failed for {remote_key}: {e}")
        return None
