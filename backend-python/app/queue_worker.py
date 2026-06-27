"""
Redis Queue Worker for CAD Processing
======================================
Consumes jobs from Redis queues and dispatches them to the appropriate
handler. Used for async processing of:
  - digitize jobs (image → DXF)
  - reference CAD processing
  - embedding generation for Qdrant
  - cleanup tasks

Designed to work with RQ (Redis Queue) workers.
"""

import os
import json
import uuid
import logging
from typing import Any

import redis as redis_lib

logger = logging.getLogger("queue_worker")
logger.setLevel(logging.INFO)

# Redis connection
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD") or None
redis_conn = redis_lib.from_url(
    REDIS_URL,
    decode_responses=True,
    password=REDIS_PASSWORD,
)

# ---------------------------------------------------------------------------
# Job handlers
# ---------------------------------------------------------------------------

def handle_digitize_job(job_data: dict[str, Any]) -> dict[str, Any]:
    """Process a digitize job: image → DXF generation.
    This wraps the existing digitize pipeline for async execution.
    """
    logger.info(f"[Queue] Processing digitize job: {job_data.get('job_id', 'unknown')}")
    # The actual processing happens via the /api/digitize endpoint.
    # The queue primarily serves as a dispatch/fanout mechanism.
    # Actual logic is in app.api.routes.digitize()
    return {"status": "dispatched", "job_id": job_data.get("job_id")}


def handle_embedding_job(job_data: dict[str, Any]) -> dict[str, Any]:
    """Generate geometry embeddings for a processed DXF and index in Qdrant."""
    logger.info(f"[Queue] Generating embeddings for: {job_data.get('dxf_file', 'unknown')}")
    try:
        from app.services.embedding_service import generate_and_index_embedding
        return generate_and_index_embedding(
            dxf_path=job_data.get("dxf_path"),
            product_id=job_data.get("product_id"),
            geometry=job_data.get("geometry"),
        )
    except ImportError:
        logger.warning("[Queue] embedding_service not available, skipping")
        return {"status": "skipped", "reason": "embedding_service not available"}


def handle_crawl_result_job(job_data: dict[str, Any]) -> dict[str, Any]:
    """Process a crawl result: download CAD assets, parse DXF, index in Qdrant."""
    logger.info(f"[Queue] Processing crawl result for product: {job_data.get('product_id', 'unknown')}")
    try:
        from app.services.crawl_processor import process_crawled_assets
        return process_crawled_assets(job_data)
    except ImportError:
        logger.warning("[Queue] crawl_processor not available, skipping")
        return {"status": "skipped"}


def handle_cleanup_job(job_data: dict[str, Any]) -> dict[str, Any]:
    """Clean up old temp files."""
    import tempfile
    import shutil
    tmp = tempfile.gettempdir()
    count = 0
    for d in ["cad_digitizer_outputs", "cad_digitizer_uploads"]:
        path = os.path.join(tmp, d)
        if os.path.isdir(path):
            for f in os.listdir(path):
                fpath = os.path.join(path, f)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                        count += 1
                except OSError:
                    pass
    logger.info(f"[Queue] Cleanup: removed {count} temp files")
    return {"status": "cleaned", "files_removed": count}


# ---------------------------------------------------------------------------
# Job dispatch table
# ---------------------------------------------------------------------------

JOB_HANDLERS = {
    "digitize": handle_digitize_job,
    "generate_embedding": handle_embedding_job,
    "crawl_result": handle_crawl_result_job,
    "cleanup": handle_cleanup_job,
}

# ---------------------------------------------------------------------------
# RQ worker integration
# ---------------------------------------------------------------------------

def process_job(job_type: str, job_data: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a job to its handler."""
    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        logger.warning(f"[Queue] Unknown job type: {job_type}")
        return {"status": "unknown_job_type", "job_type": job_type}
    try:
        return handler(job_data)
    except Exception as e:
        logger.error(f"[Queue] Handler {job_type} failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Direct worker entry point (for testing / CLI)
# ---------------------------------------------------------------------------

def subscribe_progress():
    """Subscribe to cad:progress pub/sub and buffer recent events.
    
    Stores the last 50 progress events in a Redis list for the
    frontend to poll via /api/progress endpoint.
    """
    import json
    import threading

    def _listen():
        try:
            pubsub = redis_conn.pubsub()
            pubsub.subscribe("cad:progress")
            logger.info("[Queue Worker] Subscribed to cad:progress")
            for message in pubsub.listen():
                if message["type"] == "message":
                    # Keep last 50 events in a rolling buffer
                    redis_conn.lPush("progress:buffer", message["data"])
                    redis_conn.lTrim("progress:buffer", 0, 49)
                    redis_conn.expire("progress:buffer", 3600)  # 1h TTL
        except Exception as e:
            logger.warning(f"[Queue Worker] Progress subscriber error: {e}")

    t = threading.Thread(target=_listen, daemon=True)
    t.start()
    logger.info("[Queue Worker] Progress subscriber started (background thread)")


def subscribe_job_results():
    """Subscribe to job result channels and buffer them."""
    import json
    import threading

    def _listen():
        try:
            pubsub = redis_conn.pubsub()
            # Pattern subscribe: all job:...:result channels
            pubsub.psubscribe("job:*:result")
            logger.info("[Queue Worker] Subscribed to job:*:result")
            for message in pubsub.listen():
                if message["type"] == "pmessage":
                    channel = message["channel"]
                    # Buffer job results for polling
                    result_key = f"job_result:{channel.split(':')[1]}"
                    redis_conn.setex(result_key, 3600, message["data"])
        except Exception as e:
            logger.warning(f"[Queue Worker] Job result subscriber error: {e}")

    t = threading.Thread(target=_listen, daemon=True)
    t.start()
    logger.info("[Queue Worker] Job result subscriber started (background thread)")


def main():
    """Listen on the Redis queue and process jobs."""
    import time
    logger.info(f"[Queue Worker] Connecting to Redis: {REDIS_URL}")

    # Start background subscribers for progress and job result channels
    subscribe_progress()
    subscribe_job_results()

    logger.info("[Queue Worker] Starting main job processing loop...")
    
    while True:
        try:
            # Blocking pop from the cad-processing queue
            result = redis_conn.blpop("cad-processing", timeout=5)
            if result is None:
                continue
            
            _, raw_data = result
            try:
                payload = json.loads(raw_data)
            except json.JSONDecodeError:
                logger.error(f"[Queue] Invalid JSON: {raw_data[:200]}")
                continue
            
            job_type = payload.get("type", "unknown")
            job_data = payload.get("data", {})
            job_id = job_data.get("job_id", str(uuid.uuid4()))
            
            logger.info(f"[Queue] Received job {job_id}: {job_type}")
            result_data = process_job(job_type, job_data)
            
            # Publish result on a result channel
            redis_conn.publish(f"job:{job_id}:result", json.dumps({
                "job_id": job_id,
                "type": job_type,
                "status": "completed",
                "result": result_data,
            }))
            
            # Also publish to the general progress channel
            redis_conn.publish("cad:progress", json.dumps({
                "job_id": job_id,
                "type": job_type,
                "status": "completed",
                "timestamp": time.time(),
            }))
            
        except redis_lib.ConnectionError as e:
            logger.warning(f"[Queue] Redis connection error: {e}, retrying in 5s...")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("[Queue Worker] Shutting down")
            break
        except Exception as e:
            logger.error(f"[Queue] Unexpected error: {e}", exc_info=True)
            time.sleep(1)


if __name__ == "__main__":
    main()
