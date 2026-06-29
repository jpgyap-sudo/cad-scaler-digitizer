"""
Shared DigitalOcean Spaces upload helper.

Same config/pattern as app/services/crawl_processor.py's _spaces_upload()
(verified working there) - factored out so other features (drawing
history, etc.) don't each reimplement boto3 setup independently.

Uses presigned GET URLs rather than public-read ACLs: the
"homeatelierspaces" bucket has public reads denied at the bucket level
(confirmed live - object-level ACL=public-read still 403s), and that's a
shared bucket also used by homeu-commerce, so changing its bucket-wide
access policy isn't something to do for one feature. Presigned URLs work
regardless of the bucket's public-access setting, at the cost of expiring
- callers must regenerate them on each read rather than storing a
permanent link.
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

_CONTENT_TYPES = {
    ".svg": "image/svg+xml",
    ".dxf": "application/dxf",
    ".json": "application/json",
    ".png": "image/png",
}

DEFAULT_EXPIRES_IN = 3600  # 1 hour - regenerated fresh on every /history read


def is_configured() -> bool:
    return bool(SPACES_KEY and SPACES_SECRET)


def _client():
    import boto3
    session = boto3.session.Session()
    return session.client(
        "s3", endpoint_url=SPACES_ENDPOINT,
        aws_access_key_id=SPACES_KEY,
        aws_secret_access_key=SPACES_SECRET,
        region_name="sgp1",
    )


def upload_file(local_path: Union[str, Path], remote_key: str) -> Optional[str]:
    """Upload a local file to Spaces. Returns the remote_key on success (the
    durable reference to store - generate a presigned_url() from it when
    actually needed, since the object itself isn't publicly readable), or
    None if Spaces isn't configured or the upload fails (never raises)."""
    if not is_configured():
        logger.warning("[SpacesClient] Credentials not configured, skipping upload")
        return None
    local_path = Path(local_path)
    if not local_path.exists():
        logger.warning(f"[SpacesClient] Local file not found: {local_path}")
        return None
    try:
        content_type = _CONTENT_TYPES.get(local_path.suffix.lower(), "application/octet-stream")
        _client().upload_file(
            str(local_path), SPACES_BUCKET, remote_key,
            ExtraArgs={"ContentType": content_type},
        )
        return remote_key
    except Exception as e:
        logger.error(f"[SpacesClient] Upload failed for {remote_key}: {e}")
        return None


def presigned_url(remote_key: str, expires_in: int = DEFAULT_EXPIRES_IN) -> Optional[str]:
    """Generate a time-limited signed GET URL for an already-uploaded
    object. Never raises - returns None on any failure (missing creds,
    boto3 error, etc.) so callers can degrade gracefully."""
    if not is_configured() or not remote_key:
        return None
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": SPACES_BUCKET, "Key": remote_key},
            ExpiresIn=expires_in,
        )
    except Exception as e:
        logger.error(f"[SpacesClient] Presign failed for {remote_key}: {e}")
        return None
