"""Product Catalog Search — Visual DNA matching + semantic similarity + Qdrant learning.

Searches 259 Shopify product templates by:
  - Visual DNA feature vectors (shape, base, leg, materials)
  - Text keywords (title, handle, tags, family)
  - Combined visual + text scoring
  - Qdrant semantic embeddings (if available)
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import uuid as uuid_lib
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("product_search")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CATALOG_DIR = Path(__file__).resolve().parents[3] / "resources" / "product_catalog"
REGISTRY_PATH = CATALOG_DIR / "_registry.json"
DNA_INDEX_PATH = CATALOG_DIR / "visual_dna_index.json"
LEARNED_PATH = CATALOG_DIR / "learned_products.jsonl"

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "product_templates"

# ---------------------------------------------------------------------------
# Visual DNA dimension encoding
# ---------------------------------------------------------------------------
TOP_SHAPES = ["rectangular", "round", "oval", "square", "irregular", "organic"]
BASE_TYPES = ["legs", "pedestal", "plinth", "wall_mounted", "floor", "ceiling"]
LEG_TYPES = ["four_leg", "single_pedestal", "dual_pedestal", "sled_base", "plinth", "no_legs", "cylindrical", "tapered"]
CATEGORIES = [
    "sofa", "chair", "table", "lighting", "storage", "material",
    "rug", "pillow", "panel", "fan", "ottoman", "seating", "bed",
    "support", "furniture",
]

VECTOR_SIZE = 26


# ---------------------------------------------------------------------------
# Cached loader
# ---------------------------------------------------------------------------
_CATALOG_CACHE: Dict[str, Any] | None = None


def load_catalog() -> Dict[str, Any]:
    """Lazy-load registry + visual DNA index. Returns {"registry","dna_index","count"}."""
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    registry: list[dict] = []
    if REGISTRY_PATH.exists():
        try:
            registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load registry: {e}")
            registry = []
    else:
        logger.warning(f"Registry not found: {REGISTRY_PATH}")

    dna_index: dict = {}
    if DNA_INDEX_PATH.exists():
        try:
            dna_index = json.loads(DNA_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load DNA index: {e}")
            dna_index = {}
    else:
        logger.warning(f"DNA index not found: {DNA_INDEX_PATH}")

    _CATALOG_CACHE = {"registry": registry, "dna_index": dna_index, "count": len(registry)}
    return _CATALOG_CACHE


def invalidate_cache() -> None:
    """Force reload on next call (e.g. after learning new products)."""
    global _CATALOG_CACHE
    _CATALOG_CACHE = None


# ---------------------------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------------------------

def _one_hot(value: str, options: List[str], dims: int) -> List[float]:
    """One-hot encode a string value into `dims` slots (zero-padded).

    Uses modular binning when len(options) > dims to compress categories
    into the available dimensions without index-out-of-range.
    """
    vec = [0.0] * dims
    try:
        raw_idx = options.index(value.lower().strip())
        # If options exceed dims, use modular binning
        if raw_idx < len(options) and raw_idx < dims:
            vec[raw_idx] = 1.0
        else:
            # Fall back to hash-based assignment
            import hashlib
            h = int(hashlib.md5(value.lower().encode()).hexdigest(), 16)
            vec[h % dims] = 1.0
    except (ValueError, AttributeError):
        pass  # unknown — all zeros
    return vec


def build_visual_dna_vector(features: Dict[str, Any]) -> List[float]:
    """Build a 26D vector from analysis features or DNA index entry.

    Feature keys: top_shape, base_type, leg_type, symmetry, category,
                  components, materials, tags
    """
    vec: list[float] = []

    # Dim 0-5: top_shape (6 options)
    vec.extend(_one_hot(features.get("top_shape", ""), TOP_SHAPES, 6))
    # Dim 6-11: base_type (6 options)
    vec.extend(_one_hot(features.get("base_type", ""), BASE_TYPES, 6))
    # Dim 12-15: leg_type compressed (8 -> 4D via top-4 hot)
    leg_vec = _one_hot(features.get("leg_type", ""), LEG_TYPES, 4)
    vec.extend(leg_vec)
    # Dim 16: symmetry (1.0 symmetric, 0.0 asymmetric)
    sym = str(features.get("symmetry", "symmetric")).lower().strip()
    vec.append(1.0 if sym in ("symmetric", "symmetrical") else 0.0)
    # Dim 17-20: category 4D
    cat_vec = _one_hot(features.get("category_hint", features.get("category", "")), CATEGORIES, 4)
    vec.extend(cat_vec)
    # Dim 21-22: normalized component count (max 15)
    comps = features.get("components", [])
    if isinstance(comps, list):
        vec.append(min(len(comps) / 15.0, 1.0))
    else:
        vec.append(0.0)
    # Dim 23-24: material diversity (max 5)
    mats = features.get("materials", [])
    if isinstance(mats, list):
        vec.append(min(len(mats) / 5.0, 1.0))
        vec.append(1.0 if "stone" in str(mats).lower() or "metal" in str(mats).lower() else 0.0)
    else:
        vec.extend([0.0, 0.0])
    # Dim 25: archetype score (normalized from DNA entry)
    arch = features.get("archetype_score", 0.5)
    vec.append(min(float(arch), 1.0))

    # Pad to VECTOR_SIZE
    while len(vec) < VECTOR_SIZE:
        vec.append(0.0)
    return vec[:VECTOR_SIZE]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(av * bv for av, bv in zip(a, b))
    na = math.sqrt(sum(av * av for av in a))
    nb = math.sqrt(sum(bv * bv for bv in b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Visual DNA search
# ---------------------------------------------------------------------------

def _build_reason(query: Dict[str, Any], dna: Dict[str, Any], vec_sim: float) -> str:
    """Explain why two entries match."""
    reasons: list[str] = []
    for key, label in [("top_shape", "top_shape"), ("base_type", "base"), ("leg_type", "leg_type")]:
        qv = str(query.get(key, "")).lower().strip()
        dv = str(dna.get(key, "")).lower().strip()
        if qv and dv and qv == dv:
            reasons.append(f"{label} matches ({qv})")
        elif qv and dv:
            reasons.append(f"{label}: {qv} vs {dv}")

    qcat = str(query.get("category_hint", query.get("category", ""))).lower().strip()
    dcat = str(dna.get("category_hint", "")).lower().strip()
    if qcat and dcat:
        if qcat == dcat:
            reasons.append(f"category matches ({qcat})")
        else:
            reasons.append(f"category: {qcat} vs {dcat}")

    if not reasons:
        reasons.append(f"cosine_similarity={vec_sim:.3f}")
    return "; ".join(reasons)


def search_by_visual_dna(
    analysis_features: Dict[str, Any],
    top_k: int = 5,
    threshold: float = 0.0,
) -> List[Dict[str, Any]]:
    """Score all 101 families by cosine similarity of visual DNA vectors.

    Returns top_k matches sorted descending, each with:
      family, score, reason, count, items, svg_skeleton
    """
    catalog = load_catalog()
    dna_index = catalog.get("dna_index", {})

    query_vec = build_visual_dna_vector(analysis_features)

    scored: list[tuple[float, str, dict]] = []
    for family, dna_entry in dna_index.items():
        dna_features = {
            "top_shape": dna_entry.get("top_shape", ""),
            "base_type": dna_entry.get("base_type", ""),
            "leg_type": dna_entry.get("leg_type", ""),
            "symmetry": dna_entry.get("symmetry", ""),
            "category_hint": dna_entry.get("category_hint", ""),
            "components": dna_entry.get("component_graph", []),
            "materials": dna_entry.get("materials", []),
            "archetype_score": dna_entry.get("archetype_score", 0.5),
        }
        dna_vec = build_visual_dna_vector(dna_features)
        sim = cosine_similarity(query_vec, dna_vec)
        scored.append((sim, family, dna_entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for sim, family, entry in scored[:top_k]:
        if sim < threshold:
            continue
        reason = _build_reason(analysis_features, entry, sim)
        items = entry.get("items", [])
        # Only return first 5 items per family to keep response size manageable
        top_items = items[:5]
        results.append({
            "family": family,
            "score": round(sim, 4),
            "reason": reason,
            "count": len(items),
            "items": top_items,
            "svg_skeleton": entry.get("svg_skeleton", {}),
            "archetype_score": entry.get("archetype_score", 0.5),
            "visual_dna": {
                "top_shape": entry.get("top_shape"),
                "base_type": entry.get("base_type"),
                "leg_type": entry.get("leg_type"),
                "symmetry": entry.get("symmetry"),
                "category_hint": entry.get("category_hint"),
                "materials": entry.get("materials"),
            },
        })

    return results


# ---------------------------------------------------------------------------
# Text search
# ---------------------------------------------------------------------------

def search_by_text(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Text search over catalog registry. Returns family-grouped results."""
    catalog = load_catalog()
    registry = catalog.get("registry", [])
    dna_index = catalog.get("dna_index", {})

    q = query.lower().strip()
    q_words = set(q.split())

    # Score each registry entry
    scored_entries: list[tuple[float, dict]] = []
    for entry in registry:
        score = 0.0
        title = str(entry.get("title", "")).lower()
        handle = str(entry.get("handle", "")).lower()
        family = str(entry.get("template_family", "")).lower()
        prod_type = str(entry.get("product_type", "")).lower()
        tags = [str(t).lower() for t in entry.get("tags", [])]

        # Exact match on handle
        if handle == q:
            score += 100.0
        elif q in handle:
            score += 60.0

        # Title match
        if title == q:
            score += 90.0
        elif q in title:
            score += 30.0

        # Family match
        if family == q:
            score += 50.0
        elif q in family:
            score += 20.0

        # Tag match
        for tag in tags:
            if q == tag:
                score += 20.0
            elif q in tag:
                score += 10.0

        # Word-level partial match
        for word in q_words:
            if len(word) > 2:
                if word in title:
                    score += 8.0
                if word in handle:
                    score += 5.0
                if word in family:
                    score += 4.0
                if word in prod_type:
                    score += 3.0

        if score > 0:
            scored_entries.append((score, entry))

    scored_entries.sort(key=lambda x: x[0], reverse=True)

    # Group top results by family
    families_found: dict[str, dict] = {}
    for score, entry in scored_entries:
        family = entry.get("template_family", "unknown")
        if family not in families_found:
            dna_fallback = dna_index.get(family, {})
            families_found[family] = {
                "family": family,
                "score": score,
                "reason": f"text match: query matches title/handle/tags",
                "count": 0,
                "items": [],
                "svg_skeleton": dna_fallback.get("svg_skeleton", {}),
                "archetype_score": dna_fallback.get("archetype_score", 0.5),
                "visual_dna": {
                    "top_shape": dna_fallback.get("top_shape"),
                    "base_type": dna_fallback.get("base_type"),
                    "leg_type": dna_fallback.get("leg_type"),
                    "category_hint": dna_fallback.get("category_hint"),
                },
            }
        families_found[family]["count"] += 1
        families_found[family]["items"].append({
            "title": entry.get("title"),
            "handle": entry.get("handle"),
            "file": f"templates/{entry.get('file', '')}",
        })
        # Update score to max
        if score > families_found[family]["score"]:
            families_found[family]["score"] = score

    results = sorted(families_found.values(), key=lambda x: x["score"], reverse=True)
    # Truncate items in each family to 5
    for r in results:
        r["items"] = r["items"][:5]
    return results[:top_k]


# ---------------------------------------------------------------------------
# Combined search
# ---------------------------------------------------------------------------

def search_combined(params: Dict[str, Any], top_k: int = 5) -> Dict[str, Any]:
    """Blend visual DNA + text search results.

    params can have:
      - text: str
      - shape: str (top_shape)
      - base: str (base_type)
      - leg: str (leg_type)
      - category: str
      - materials: list[str]
      - symmetry: str
      - components: list[str]
    """
    text_query = params.get("text") or params.get("q") or ""
    has_visual = any(k in params for k in ("shape", "base", "leg", "category"))

    # Build visual features from params
    visual_features = {}
    if params.get("shape"):
        visual_features["top_shape"] = params["shape"]
    if params.get("base"):
        visual_features["base_type"] = params["base"]
    if params.get("leg"):
        visual_features["leg_type"] = params["leg"]
    if params.get("category"):
        visual_features["category_hint"] = params["category"]
    if params.get("materials"):
        visual_features["materials"] = params["materials"] if isinstance(params["materials"], list) else [params["materials"]]
    if params.get("symmetry"):
        visual_features["symmetry"] = params["symmetry"]
    if params.get("components"):
        visual_features["components"] = params["components"] if isinstance(params["components"], list) else [params["components"]]
    if params.get("tags"):
        visual_features["tags"] = params["tags"] if isinstance(params["tags"], list) else [params["tags"]]

    visual_results = []
    text_results = []

    if visual_features:
        visual_results = search_by_visual_dna(visual_features, top_k=top_k)

    if text_query:
        text_results = search_by_text(text_query, top_k=top_k)

    if not visual_results and not text_results:
        return {"results": [], "total": 0, "mode": "none"}

    if visual_results and text_results:
        # Blend: 70% visual, 30% text
        visual_weight = 0.7
        text_weight = 0.3

        # Normalize scores in each set
        v_max = max(r["score"] for r in visual_results) or 1.0
        t_max = max(r["score"] for r in text_results) or 1.0

        # Merge by family
        merged: dict[str, dict] = {}
        for r in visual_results:
            r["blend_score"] = (r["score"] / v_max) * visual_weight
            merged[r["family"]] = r
        for r in text_results:
            ts = (r["score"] / t_max) * text_weight
            if r["family"] in merged:
                merged[r["family"]]["blend_score"] += ts
                merged[r["family"]]["reason"] = "visual+text match"
            else:
                r["blend_score"] = ts
                merged[r["family"]] = r

        results = sorted(merged.values(), key=lambda x: x.get("blend_score", 0), reverse=True)
        mode = "blended"
    elif visual_results:
        results = visual_results
        mode = "visual_dna"
    else:
        results = text_results
        mode = "text"

    return {"results": results[:top_k], "total": len(results), "mode": mode}


# ---------------------------------------------------------------------------
# Semantic search via Qdrant
# ---------------------------------------------------------------------------

def _text_to_embedding(text: str, dims: int = 32) -> List[float]:
    """Simple bag-of-words hash embedding (no external model needed).

    Generates a deterministic dims-dimensional vector from text hashing.
    """
    words = text.lower().split()
    vec = [0.0] * dims
    for word in words:
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        idx = h % dims
        vec[idx] += 1.0
    # Normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _deterministic_uuid(text: str) -> str:
    """Create a deterministic UUID from text content."""
    digest = hashlib.sha256(text.encode()).hexdigest()[:32]
    return str(uuid_lib.uuid5(uuid_lib.NAMESPACE_DNS, digest))


def _get_qdrant_client():
    """Try to create a Qdrant client, return None if unavailable."""
    try:
        from qdrant_client import QdrantClient
        return QdrantClient(url=QDRANT_URL)
    except ImportError:
        logger.info("qdrant_client not installed")
        return None
    except Exception as e:
        logger.warning(f"Qdrant connection failed: {e}")
        return None


def search_semantic(
    query: str,
    top_k: int = 5,
    qdrant_client=None,
) -> List[Dict[str, Any]]:
    """Search product templates in Qdrant by semantic embedding."""
    client = qdrant_client or _get_qdrant_client()
    if client is None:
        # Fallback: simple text search
        logger.info("Qdrant unavailable, falling back to text search")
        return search_by_text(query, top_k=top_k)

    try:
        from qdrant_client.http.exceptions import UnexpectedResponse

        # Check collection exists
        try:
            client.get_collection(QDRANT_COLLECTION)
        except UnexpectedResponse:
            logger.info(f"Qdrant collection '{QDRANT_COLLECTION}' doesn't exist yet")
            return []

        query_vec = _text_to_embedding(query)
        hits = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vec,
            limit=top_k,
        )
        return [
            {
                "id": hit.id,
                "score": round(hit.score, 4),
                "product_id": hit.payload.get("product_id"),
                "family": hit.payload.get("family"),
                "title": hit.payload.get("title"),
                "handle": hit.payload.get("handle"),
            }
            for hit in hits
        ]
    except Exception as e:
        logger.warning(f"Qdrant semantic search failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Learn / persist a confirmed product
# ---------------------------------------------------------------------------

def learn_product(
    template_data: Dict[str, Any],
    corrections: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Save a confirmed product match to local storage + Qdrant.

    Generates an embedding from: Visual DNA + tags + components + title.
    Stores in:
      1. resources/product_catalog/learned_products.jsonl (always)
      2. Qdrant "product_templates" collection (if available)
    """
    # Apply corrections on top
    payload = dict(template_data)
    if corrections:
        payload.update(corrections)

    # Build text for embedding
    text_parts = [
        str(payload.get("title", "")),
        str(payload.get("template_family", "")),
        str(payload.get("handle", "")),
    ]
    tags = payload.get("tags", [])
    if isinstance(tags, list):
        text_parts.extend(str(t) for t in tags)
    components = payload.get("components", [])
    if isinstance(components, list):
        text_parts.extend(str(c) for c in components)

    # Add visual DNA if available
    dna_index = load_catalog().get("dna_index", {})
    family = payload.get("template_family", "")
    if family in dna_index:
        dna = dna_index[family]
        text_parts.append(str(dna.get("top_shape", "")))
        text_parts.append(str(dna.get("base_type", "")))
        text_parts.append(str(dna.get("leg_type", "")))
        mats = dna.get("materials", [])
        text_parts.extend(str(m) for m in mats)

    full_text = " ".join(text_parts)

    # 1. Save to local JSONL
    try:
        LEARNED_PATH.parent.mkdir(parents=True, exist_ok=True)
        learned_entry = {
            "id": _deterministic_uuid(str(payload.get("handle", full_text))),
            "title": payload.get("title"),
            "handle": payload.get("handle"),
            "template_family": family,
            "tags": tags,
            "text": full_text,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
        with open(LEARNED_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(learned_entry, ensure_ascii=False) + "\n")
        logger.info(f"Learned product saved to {LEARNED_PATH}")
        local_status = "saved"
    except Exception as e:
        logger.warning(f"Failed to save learned product locally: {e}")
        local_status = f"failed: {e}"

    # 2. Index in Qdrant
    qdrant_status = "not_attempted"
    client = _get_qdrant_client()
    if client:
        try:
            from qdrant_client.http.exceptions import UnexpectedResponse
            from qdrant_client.models import Distance, PointStruct, VectorParams

            vector = _text_to_embedding(full_text)
            point_id = _deterministic_uuid(str(payload.get("handle", full_text)))

            # Ensure collection exists
            try:
                client.get_collection(QDRANT_COLLECTION)
            except UnexpectedResponse:
                client.recreate_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=len(vector), distance=Distance.COSINE),
                )

            client.upsert(
                collection_name=QDRANT_COLLECTION,
                points=[PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "product_id": payload.get("id") or payload.get("handle"),
                        "title": payload.get("title"),
                        "handle": payload.get("handle"),
                        "family": family,
                        "tags": tags,
                    },
                )],
            )
            qdrant_status = f"indexed as {point_id}"
            logger.info(f"[Qdrant] Learned product indexed: {point_id}")
        except Exception as e:
            qdrant_status = f"failed: {e}"
            logger.warning(f"Qdrant index failed: {e}")
    else:
        qdrant_status = "skipped (no client)"

    return {
        "status": "learned",
        "id": _deterministic_uuid(str(payload.get("handle", full_text))),
        "local": local_status,
        "qdrant": qdrant_status,
        "family": family,
    }


# ---------------------------------------------------------------------------
# Similar product lookup
# ---------------------------------------------------------------------------

def get_similar(template_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Find products similar to a given template by its ID.

    template_id format: homeu_b{1-6}_{handle}
    """
    catalog = load_catalog()
    registry = catalog.get("registry", [])

    # Find template in registry
    target = None
    for entry in registry:
        if entry.get("id") == template_id or entry.get("handle") == template_id:
            target = entry
            break

    if not target:
        # Try text search
        text_results = search_by_text(template_id, top_k=1)
        if text_results and text_results[0].get("items"):
            return text_results

        return []

    # Build visual features from target
    family = target.get("template_family", "unknown")
    dna_index = catalog.get("dna_index", {})
    dna_entry = dna_index.get(family, {})

    features = {
        "top_shape": dna_entry.get("top_shape", ""),
        "base_type": dna_entry.get("base_type", ""),
        "leg_type": dna_entry.get("leg_type", ""),
        "symmetry": dna_entry.get("symmetry", ""),
        "category_hint": dna_entry.get("category_hint", ""),
        "materials": dna_entry.get("materials", []),
        "components": target.get("components", dna_entry.get("component_graph", [])),
        "archetype_score": dna_entry.get("archetype_score", 0.5),
    }

    return search_by_visual_dna(features, top_k=top_k)


# ---------------------------------------------------------------------------
# Family lookup
# ---------------------------------------------------------------------------

def get_family_visual_dna(family: str) -> Dict[str, Any]:
    """Return the full DNA index entry for a template family."""
    dna_index = load_catalog().get("dna_index", {})
    return dna_index.get(family, {})


# ---------------------------------------------------------------------------
# Convenience: full catalog info
# ---------------------------------------------------------------------------

def catalog_stats() -> Dict[str, Any]:
    """Return high-level catalog statistics."""
    catalog = load_catalog()
    dna_index = catalog.get("dna_index", {})
    families_with_items = sum(1 for v in dna_index.values() if v.get("items"))

    # Count per category
    category_counts: dict[str, int] = {}
    for v in dna_index.values():
        cat = v.get("category_hint", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "total_templates": catalog["count"],
        "total_families": len(dna_index),
        "families_with_items": families_with_items,
        "categories": category_counts,
        "batches": _count_per_batch(catalog["registry"]),
    }


def _count_per_batch(registry: list[dict]) -> dict:
    counts: dict[int, int] = {}
    for e in registry:
        b = e.get("batch", 0)
        counts[b] = counts.get(b, 0) + 1
    return dict(sorted(counts.items()))


# ---------------------------------------------------------------------------
# Main / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Catalog Stats ===")
    stats = catalog_stats()
    print(json.dumps(stats, indent=2))

    print("\n=== Visual DNA search: rectangular top, legs base, sofa category ===")
    results = search_by_visual_dna({
        "top_shape": "rectangular",
        "base_type": "legs",
        "category_hint": "sofa",
    })
    print(json.dumps(results, indent=2, ensure_ascii=False))

    print("\n=== Text search: 'modern sofa' ===")
    text_results = search_by_text("modern sofa")
    print(json.dumps(text_results, indent=2, ensure_ascii=False))

    print("\n=== Combined: oval table ===")
    combined = search_combined({"shape": "oval", "category": "table", "text": "coffee"})
    print(json.dumps(combined, indent=2, ensure_ascii=False))
