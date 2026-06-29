"""
Crawl Result Processor
=======================
Processes assets downloaded by the crawler-worker:
  1. Downloads CAD files from URLs
  2. Parses DXF geometry
  3. Generates SVG preview, persisted to /tmp/cad_digitizer_outputs/
  4. Indexes geometry in Qdrant
  5. Uploads persistent files to Spaces
  6. Saves metadata to Postgres
"""

import os
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("crawl_processor")

OUT = Path("/tmp/cad_digitizer_outputs")

SPACES_ENDPOINT = os.environ.get("SPACES_ENDPOINT", "https://sgp1.digitaloceanspaces.com")
SPACES_BUCKET = os.environ.get("SPACES_BUCKET", "homeatelierspaces")
SPACES_KEY = os.environ.get("SPACES_KEY", "")
SPACES_SECRET = os.environ.get("SPACES_SECRET", "")
SPACES_CDN_BASE = os.environ.get("SPACES_CDN_BASE", "")

# Postgres connection via brain_sync (lazy imported)

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


def _persist_metadata(product_id: str, asset_id: str, url: str,
                       geo_url: str, svg_url: str, entity_count: int,
                       bbox: Any, embedding_result: Any) -> None:
    """Save crawl result metadata to Postgres (Prisma-compatible schema)."""
    try:
        from app.backend.brain_sync import _execute
        import uuid as uuid_lib

        ref_id = f"crawl-{product_id}"
        ref_meta = json.dumps({
            "source_url": url, "asset_id": asset_id,
            "entity_count": entity_count, "bbox": bbox,
            "embedding": embedding_result,
            "geometry_url": geo_url, "preview_svg_url": svg_url,
        })
        # ProductReference: PascalCase table, quoted identifers
        ref_sql = '''
            INSERT INTO "ProductReference" (id, manufacturer, "productName", slug, category, metadata)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                metadata = EXCLUDED.metadata,
                "updatedAt" = NOW()
        '''
        slug = product_id.replace(" ", "-").lower()[:60]
        _execute(ref_sql, (ref_id, "crawler", f"crawled-{product_id}", slug, "dxf", ref_meta),
                 commit=True)

        # ReferenceAsset: PascalCase with relation FK
        def _insert_asset(aid: str, asset_type: str, cdn_url: str, fname: str, meta: dict) -> None:
            asset_sql = '''
                INSERT INTO "ReferenceAsset" (id, "productReferenceId", "assetType", "fileName", "spaceKey", "cdnUrl", "processedStatus", metadata)
                VALUES (%s, %s, %s::"AssetType", %s, %s, %s, %s::"ProcessingStatus", %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET "cdnUrl" = EXCLUDED."cdnUrl", "processedStatus" = 'DONE'::"ProcessingStatus"
            '''
            _execute(asset_sql, (aid, ref_id, asset_type, fname, f"cad-reference-library/{aid}", cdn_url, 'DONE', json.dumps(meta)),
                     commit=True)

        _insert_asset(asset_id, 'DXF', url, f"{asset_id}.dxf",
                      {"source_url": url, "entity_count": entity_count, "processed": True})
        if geo_url:
            _insert_asset(f"{asset_id}-geo", 'GEOMETRY_JSON', geo_url, f"{asset_id}.json",
                          {"type": "parsed_geometry", "entity_count": entity_count})
        if svg_url:
            _insert_asset(f"{asset_id}-preview", 'SVG', svg_url, f"{asset_id}.svg",
                          {"type": "preview"})

        logger.info(f"[CrawlProcessor] Metadata persisted for {product_id}")
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
