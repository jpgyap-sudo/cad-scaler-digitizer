"""
Qdrant Embedding Service
========================
Generates geometry embeddings from processed DXF files and indexes them
in Qdrant for similarity search. Enables:
  - Find similar CAD files by geometry
  - Retrieve reference furniture by sketch matching
  - Auto-classify furniture based on nearest neighbors
"""

import os
import json
import logging
import hashlib
from typing import Any, Optional

logger = logging.getLogger("embedding_service")

# Qdrant client
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "cad_geometry"

# ---------------------------------------------------------------------------
# Embedding extraction from geometry data
# ---------------------------------------------------------------------------

def extract_geometry_features(geometry: dict[str, Any]) -> list[float]:
    """
    Extract a fixed-length feature vector from CAD geometry.
    Features:
      - Entity counts (normalized)
      - Bounding box aspect ratio
      - Line length distribution (mean, std)
      - Circle/arc prevalence
      - Layer entropy
    Returns a list of floats suitable for Qdrant indexing.
    """
    counts = geometry.get("counts", {})
    bbox = geometry.get("bbox") or {}
    entities = geometry.get("entities", [])

    features: list[float] = []

    # 1. Entity count features (normalized by log1p)
    import math
    features.append(math.log1p(counts.get("entityCount", 0)))
    features.append(math.log1p(counts.get("lineCount", 0)))
    features.append(math.log1p(counts.get("circleCount", 0)))
    features.append(math.log1p(counts.get("arcCount", 0)))
    features.append(math.log1p(counts.get("polylineCount", 0)))
    features.append(math.log1p(counts.get("textCount", 0)))

    # 2. Bounding box features
    bw = bbox.get("width", 0) or 0
    bh = bbox.get("height", 0) or 0
    features.append(math.log1p(bw))
    features.append(math.log1p(bh))
    features.append(bh / (bw + 1))  # aspect ratio

    # 3. Line length statistics
    line_lengths = []
    for e in entities:
        if e.get("type") == "line":
            start = e.get("start", [0, 0])
            end = e.get("end", [0, 0])
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            line_lengths.append(math.sqrt(dx*dx + dy*dy))

    if line_lengths:
        import statistics
        features.append(math.log1p(statistics.mean(line_lengths)))
        features.append(math.log1p(statistics.stdev(line_lengths) if len(line_lengths) > 1 else 0))
    else:
        features.extend([0.0, 0.0])

    # 4. Circle/arc prevalence
    total = max(counts.get("entityCount", 1), 1)
    features.append(counts.get("circleCount", 0) / total)
    features.append(counts.get("arcCount", 0) / total)

    # 5. Layer entropy (diversity of layers)
    layers: dict[str, int] = {}
    for e in entities:
        layer = e.get("layer", "0")
        layers[layer] = layers.get(layer, 0) + 1

    if layers:
        entropy = 0.0
        for count in layers.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        features.append(entropy / math.log2(len(layers) + 1))  # normalized
    else:
        features.append(0.0)

    # 6. Primitive type distribution (16D one-hot-ish vector)
    type_counts = {
        "line": 0, "circle": 0, "arc": 0, "polyline": 0,
        "text": 0, "dimension": 0, "rectangle": 0, "spline": 0,
    }
    for e in entities:
        t = e.get("type", "")
        if t in type_counts:
            type_counts[t] += 1

    for _, count in type_counts.items():
        features.append(count / total)

    # Total: 6 + 3 + 2 + 2 + 1 + 8 = 22 dimensions
    return features


def geometry_hash(geometry: dict[str, Any]) -> str:
    """Create a content-based hash for deduplication."""
    raw = json.dumps(geometry, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Qdrant index operations
# ---------------------------------------------------------------------------

def init_collection():
    """Ensure the CAD geometry collection exists in Qdrant."""
    from qdrant_client import QdrantClient
    from qdrant_client.http.exceptions import UnexpectedResponse
    from qdrant_client.models import Distance, VectorParams

    client = QdrantClient(url=QDRANT_URL)
    try:
        client.get_collection(COLLECTION_NAME)
        logger.info(f"[Qdrant] Collection '{COLLECTION_NAME}' exists")
    except UnexpectedResponse:
        # Collection doesn't exist — create it
        client.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=22,  # matches extract_geometry_features output
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"[Qdrant] Created collection '{COLLECTION_NAME}' with 22D vectors")
    except Exception as e:
        logger.warning(f"[Qdrant] Could not init collection: {e}")


def index_geometry(
    geometry: dict[str, Any],
    product_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Extract features from geometry and index in Qdrant."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct

        init_collection()
        client = QdrantClient(url=QDRANT_URL)

        vector = extract_geometry_features(geometry)
        point_id = geometry_hash(geometry)
        payload = {
            "product_id": product_id,
            "entity_count": geometry.get("counts", {}).get("entityCount", 0),
            "bbox": geometry.get("bbox"),
        }
        if metadata:
            payload.update(metadata)

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )],
        )
        logger.info(f"[Qdrant] Indexed {product_id} as point {point_id}")
        return {"status": "indexed", "point_id": point_id, "product_id": product_id}

    except ImportError:
        logger.warning("[Qdrant] qdrant_client not installed, skipping index")
        return {"status": "skipped", "reason": "qdrant_client not available"}
    except Exception as e:
        logger.error(f"[Qdrant] Index failed: {e}")
        return {"status": "failed", "error": str(e)}


def search_similar(
    geometry: dict[str, Any],
    limit: int = 10,
    score_threshold: float = 0.6,
) -> list[dict[str, Any]]:
    """Search for similar CAD geometries in Qdrant."""
    try:
        from qdrant_client import QdrantClient

        init_collection()
        client = QdrantClient(url=QDRANT_URL)

        vector = extract_geometry_features(geometry)
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            {
                "id": hit.id,
                "score": hit.score,
                "product_id": hit.payload.get("product_id"),
                "entity_count": hit.payload.get("entity_count"),
                "bbox": hit.payload.get("bbox"),
            }
            for hit in results
        ]

    except ImportError:
        logger.warning("[Qdrant] qdrant_client not installed")
        return []
    except Exception as e:
        logger.error(f"[Qdrant] Search failed: {e}")
        return []


def generate_and_index_embedding(
    dxf_path: str = None,
    product_id: str = None,
    geometry: dict[str, Any] = None,
) -> dict[str, Any]:
    """Generate and index an embedding for a given CAD file."""
    if not geometry:
        if not dxf_path:
            return {"status": "failed", "error": "No geometry or dxf_path provided"}
        # Parse the DXF to get geometry
        try:
            from app.cad.dxf_parser import parse_dxf
            geometry = parse_dxf(dxf_path)
        except Exception as e:
            return {"status": "failed", "error": f"DXF parse failed: {e}"}

    return index_geometry(
        geometry=geometry,
        product_id=product_id or "unknown",
        metadata={"dxf_path": dxf_path} if dxf_path else None,
    )
