"""
Reference Library Retriever
============================
Queries the Node Reference Library API and Qdrant to find similar
reference products for a given furniture type or geometry signature.

Used by the digitizer pipeline to retrieve relevant CAD profiles
that inform dimension estimation and template selection.
"""

import os
import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger("reference_retriever")

NODE_API_URL = os.environ.get("NODE_API_URL", "http://node-api:4000")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")


async def get_product_references(
    manufacturer: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch product references from the Node API."""
    try:
        params = {"take": limit}
        if manufacturer:
            params["manufacturer"] = manufacturer
        if category:
            params["category"] = category

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{NODE_API_URL}/product-references",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning(f"[ReferenceRetriever] Failed to fetch references: {e}")
        return []


async def get_reference_assets(product_id: str) -> list[dict[str, Any]]:
    """Get assets for a specific product reference."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{NODE_API_URL}/product-references/{product_id}",
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("assets", [])
    except Exception as e:
        logger.warning(f"[ReferenceRetriever] Failed to fetch assets: {e}")
        return []


async def search_similar_geometry(
    geometry_features: list[float],
    limit: int = 10,
    score_threshold: float = 0.6,
) -> list[dict[str, Any]]:
    """Search for similar CAD geometries in Qdrant using feature vectors.
    
    Args:
        geometry_features: 22D feature vector from embedding_service
        limit: Max results
        score_threshold: Minimum similarity score
    
    Returns:
        List of matched products with similarity scores
    """
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=QDRANT_URL)
        results = client.search(
            collection_name="cad_geometry",
            query_vector=geometry_features,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            {
                "id": hit.id,
                "score": hit.score,
                "product_id": hit.payload.get("product_id"),
                "entity_count": hit.payload.get("entity_count"),
            }
            for hit in results
        ]
    except ImportError:
        logger.warning("[ReferenceRetriever] qdrant_client not available")
        return []
    except Exception as e:
        logger.warning(f"[ReferenceRetriever] Qdrant search failed: {e}")
        return []


async def find_reference_for_classification(
    furniture_type: str,
    detected_dimensions: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Find the best matching reference product for a classified furniture type.
    
    Uses dimension similarity to rank references.
    Returns the best match or None.
    """
    references = await get_product_references(category=furniture_type, limit=20)
    if not references:
        return None

    # Score by dimension proximity
    scored = []
    for ref in references:
        score = 0.0
        ref_geo = ref.get("geometryProfile") or {}
        ref_bbox = ref_geo.get("bbox") or {}

        for dim in detected_dimensions:
            tag = dim.get("tag", "").lower()
            val = dim.get("value_cm", 0)
            if not val:
                continue

            if "width" in tag or "diameter" in tag:
                ref_w = ref_bbox.get("width", 0)
                if ref_w:
                    score += 1.0 - min(abs(val - ref_w) / ref_w, 1.0)
            elif "height" in tag:
                ref_h = ref_bbox.get("height", 0)
                if ref_h:
                    score += 1.0 - min(abs(val - ref_h) / ref_h, 1.0)

        if score > 0:
            scored.append((score, ref))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0]
    return {
        "product": best[1],
        "similarity_score": round(best[0] / max(len(detected_dimensions), 1), 3),
    }
