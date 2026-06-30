"""
Crawl Result Processor
=======================
Processes assets downloaded by the crawler-worker:
  1. Downloads CAD files from URLs
  2. Parses DXF geometry
  3. Generates SVG preview, persisted to /tmp/cad_digitizer_outputs/
  4. Indexes geometry in Qdrant
  5. Uploads persistent files to Spaces
  6. Saves metadata to crawl_index.json (file-based, synced to Spaces)
"""

import os
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

import httpx

logger = logging.getLogger("crawl_processor")

OUT = Path("/tmp/cad_digitizer_outputs")
CRAWL_INDEX_PATH = OUT / "crawl_index.json"

SPACES_ENDPOINT = os.environ.get("SPACES_ENDPOINT", "https://sgp1.digitaloceanspaces.com")
SPACES_BUCKET = os.environ.get("SPACES_BUCKET", "homeatelierspaces")
SPACES_KEY = os.environ.get("SPACES_KEY", "")
SPACES_SECRET = os.environ.get("SPACES_SECRET", "")
SPACES_CDN_BASE = os.environ.get("SPACES_CDN_BASE", "")

def _spaces_upload(local_path: Path, remote_key: str) -> Optional[str]:
    """Upload a file to DigitalOcean Spaces. Returns CDN URL or None."""
    if not SPACES_KEY or not SPACES_SECRET:
        logger.warning("[CrawlProcessor] Spaces credentials not configured, skipping upload")
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
        client.upload_file(
            str(local_path), SPACES_BUCKET, remote_key,
            ExtraArgs={"ACL": "public-read", "ContentType": "image/svg+xml" if local_path.suffix == ".svg" else "application/json"},
        )
        cdn_base = SPACES_CDN_BASE or f"{SPACES_ENDPOINT}/{SPACES_BUCKET}"
        return f"{cdn_base}/{remote_key}"
    except Exception as e:
        logger.error(f"[CrawlProcessor] Spaces upload failed: {e}")
        return None


def _load_crawl_index() -> dict:
    """Load crawl index from local JSON file. Re-downloads from Spaces if missing."""
    if CRAWL_INDEX_PATH.exists():
        try:
            return json.loads(CRAWL_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Try to restore from Spaces
    if SPACES_KEY and SPACES_SECRET:
        try:
            import boto3
            session = boto3.session.Session()
            client = session.client("s3", endpoint_url=SPACES_ENDPOINT,
                aws_access_key_id=SPACES_KEY, aws_secret_access_key=SPACES_SECRET, region_name="sgp1")
            obj = client.get_object(Bucket=SPACES_BUCKET, Key="cad-reference-library/crawl_index.json")
            data = json.loads(obj["Body"].read().decode())
            CRAWL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
            CRAWL_INDEX_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return data
        except Exception:
            pass
    return {}


def _save_crawl_index(index: dict) -> None:
    """Save crawl index to local JSON and sync to Spaces."""
    try:
        CRAWL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        CRAWL_INDEX_PATH.write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")
        if SPACES_KEY and SPACES_SECRET:
            import boto3
            session = boto3.session.Session()
            client = session.client("s3", endpoint_url=SPACES_ENDPOINT,
                aws_access_key_id=SPACES_KEY, aws_secret_access_key=SPACES_SECRET, region_name="sgp1")
            client.upload_file(str(CRAWL_INDEX_PATH), SPACES_BUCKET, "cad-reference-library/crawl_index.json",
                ExtraArgs={"ACL": "public-read", "ContentType": "application/json"})
    except Exception as e:
        logger.warning(f"[CrawlProcessor] Crawl index save failed: {e}")


def _persist_metadata(product_id: str, asset_id: str, url: str,
                       geo_url: str, svg_url: str, entity_count: int,
                       bbox: Any, embedding_result: Any) -> None:
    """Save crawl result metadata to crawl_index.json (file-based, synced to Spaces)."""
    try:
        index = _load_crawl_index()
        entry = {
            "product_id": product_id,
            "asset_id": asset_id,
            "source_url": url,
            "geometry_url": geo_url or "",
            "preview_svg_url": svg_url or "",
            "entity_count": entity_count,
            "bbox": bbox,
            "embedding": embedding_result,
            "timestamp": datetime.utcnow().isoformat(),
        }
        index[product_id] = entry
        _save_crawl_index(index)
        logger.info(f"[CrawlProcessor] Metadata persisted for {product_id} ({len(index)} total entries)")
    except Exception as e:
        logger.error(f"[CrawlProcessor] Metadata persist failed: {e}")


def process_crawled_assets(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Process a batch of crawled assets.
    Called by the RQ worker when a crawl_result job is received.
    """
    assets = payload.get("assets", [])
    product_id = payload.get("product_id", "unknown")
    results = []

    for asset in assets:
        asset_type = asset.get("assetType", "")
        url = asset.get("cdnUrl") or asset.get("sourceUrl", "")
        asset_id = asset.get("id", "")

        if asset_type in ("DXF", "DWG"):
            result = _process_cad_file(url, asset_id, product_id)
            results.append(result)
        elif asset_type == "IMAGE":
            result = _process_image(url, asset_id, product_id)
            results.append(result)

    return {
        "product_id": product_id,
        "assets_processed": len(results),
        "results": results,
    }


def _process_cad_file(url: str, asset_id: str, product_id: str) -> dict[str, Any]:
    """Download and parse a CAD file, generate preview, persist to Spaces and Postgres."""
    logger.info(f"[CrawlProcessor] Processing CAD: {url}")
    result = {
        "asset_id": asset_id,
        "url": url,
        "status": "pending",
    }

    job_id = f"{uuid.uuid4().hex[:12]}"
    out_dir = OUT / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Download the file
        local_path = out_dir / "source.dxf"
        response = httpx.get(url, timeout=120, follow_redirects=True)
        response.raise_for_status()
        local_path.write_bytes(response.content)

        # Parse DXF
        from app.cad.dxf_parser import parse_dxf
        geometry = parse_dxf(str(local_path))

        # Save geometry JSON (persistent - outside temp dir)
        geo_path = out_dir / "geometry.json"
        geo_path.write_text(json.dumps(geometry, indent=2), encoding="utf-8")

        # Generate SVG preview (persistent)
        preview_path = out_dir / "preview.svg"
        from app.cad.preview_svg import generate_preview_svg
        generate_preview_svg(geometry, str(preview_path))

        # Index in Qdrant
        embedding_result = None
        try:
            from app.services.embedding_service import index_geometry
            embedding_result = index_geometry(
                geometry=geometry,
                product_id=product_id,
                metadata={"asset_id": asset_id, "source_url": url},
            )
            result["embedding"] = embedding_result
        except Exception as e:
            logger.warning(f"[CrawlProcessor] Embedding failed: {e}")
            result["embedding"] = {"status": "failed"}

        # Upload to Spaces
        geo_url = _spaces_upload(geo_path, f"cad-reference-library/{job_id}/geometry.json")
        svg_url = _spaces_upload(preview_path, f"cad-reference-library/{job_id}/preview.svg")

        # Persist to Postgres
        entity_count = geometry.get("counts", {}).get("entityCount", 0)
        _persist_metadata(product_id, asset_id, url, geo_url, svg_url,
                          entity_count, geometry.get("bbox"), embedding_result)

        result["status"] = "completed"
        result["entity_count"] = entity_count
        result["bbox"] = geometry.get("bbox")
        result["geo_url"] = geo_url
        result["svg_url"] = svg_url

    except Exception as e:
        logger.error(f"[CrawlProcessor] Processing failed: {e}")
        result["status"] = "failed"
        result["error"] = str(e)

    return result


def _process_image(url: str, asset_id: str, product_id: str) -> dict[str, Any]:
    """Process a crawled image (download and generate thumbnail info)."""
    result = {
        "asset_id": asset_id,
        "url": url,
        "status": "completed",
        "type": "image",
    }
    logger.info(f"[CrawlProcessor] Image processed: {url}")
    return result
