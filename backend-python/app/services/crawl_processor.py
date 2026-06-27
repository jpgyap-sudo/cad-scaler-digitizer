"""
Crawl Result Processor
=======================
Processes assets downloaded by the crawler-worker:
  1. Downloads CAD files from URLs
  2. Parses DXF geometry
  3. Generates SVG preview
  4. Indexes geometry in Qdrant
  5. Saves metadata to Postgres
"""

import os
import json
import tempfile
import logging
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("crawl_processor")

# Python Worker base URL (self-reference)
WORKER_BASE = os.environ.get("PYTHON_WORKER_URL", "http://localhost:8001")


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
    """Download and parse a CAD file, generate preview, index in Qdrant."""
    logger.info(f"[CrawlProcessor] Processing CAD: {url}")
    result = {
        "asset_id": asset_id,
        "url": url,
        "status": "pending",
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        local_path = tmp_path / "source.dxf"

        try:
            # Download the file
            response = httpx.get(url, timeout=120, follow_redirects=True)
            response.raise_for_status()
            local_path.write_bytes(response.content)

            # Parse DXF
            from app.cad.dxf_parser import parse_dxf
            geometry = parse_dxf(str(local_path))

            # Save geometry JSON
            geo_path = tmp_path / "geometry.json"
            geo_path.write_text(json.dumps(geometry, indent=2), encoding="utf-8")

            # Generate SVG preview
            preview_path = tmp_path / "preview.svg"
            from app.cad.preview_svg import generate_preview_svg
            generate_preview_svg(geometry, str(preview_path))

            # Index in Qdrant
            try:
                from app.services.embedding_service import index_geometry
                index_result = index_geometry(
                    geometry=geometry,
                    product_id=product_id,
                    metadata={"asset_id": asset_id, "source_url": url},
                )
                result["embedding"] = index_result
            except Exception as e:
                logger.warning(f"[CrawlProcessor] Embedding failed: {e}")
                result["embedding"] = {"status": "failed"}

            result["status"] = "completed"
            result["entity_count"] = geometry.get("counts", {}).get("entityCount", 0)
            result["bbox"] = geometry.get("bbox")

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
    # For now, just mark as completed. Future: generate thumbnails, OCR, etc.
    return result
