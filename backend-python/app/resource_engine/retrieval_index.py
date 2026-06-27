"""CAD Retrieval Index — embedding-based vector search with cloud API fallback.
Extends SimpleRetriever (TF-IDF) with actual embeddings for semantic search.

Supports: OpenAI text-embedding-3-small, Gemini text-embedding-004, local hash fallback
"""
import json
import math
import hashlib
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


# ===== Embedding Clients =====

class EmbeddingClient(ABC):
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        pass


class HashEmbeddingClient(EmbeddingClient):
    """Deterministic hash-based embedding — no API key needed. 384D."""
    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = text.lower().replace("/", " ").replace("_", " ").split()
        if not tokens:
            return vec
        for token in tokens:
            h = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            sign = 1 if (h >> 8) % 2 == 0 else -1
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class OpenAIEmbeddingClient(EmbeddingClient):
    """OpenAI text-embedding-3-small. Lazy import to avoid crash if not installed."""
    def __init__(self):
        self._client = None
        self.model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


class GeminiEmbeddingClient(EmbeddingClient):
    """Google Gemini text embedding. Lazy import to avoid crash if not installed."""
    def __init__(self):
        self._client = None
        self.model = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        results = []
        for t in texts:
            r = self._client.models.embed_content(model=self.model, content=t)
            results.append(r.embeddings[0].values)
        return results


def make_embedding_client() -> EmbeddingClient:
    """Factory: returns best available embedding client. Handles missing packages."""
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI  # noqa: test availability
            return OpenAIEmbeddingClient()
        except ImportError:
            pass
    if os.getenv("GEMINI_API_KEY"):
        try:
            from google import genai  # noqa: test availability
            return GeminiEmbeddingClient()
        except ImportError:
            pass
    return HashEmbeddingClient()


# ===== Retrieval Document Models =====

class RetrievalDocument:
    """A document in the retrieval index."""
    def __init__(self, id: str, source_type: str, path: str,
                 title: str, text: str, tags: List[str] = None,
                 metadata: Dict[str, Any] = None):
        self.id = id
        self.source_type = source_type  # resource_json, cad_dxf, generated
        self.path = path
        self.title = title
        self.text = text
        self.tags = tags or []
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "source_type": self.source_type, "path": self.path,
            "title": self.title, "text": self.text, "tags": self.tags,
            "metadata": self.metadata,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "RetrievalDocument":
        return RetrievalDocument(**d)


class SearchHit:
    """A search result with score."""
    def __init__(self, id: str, score: float, title: str, path: str,
                 source_type: str, text: str, tags: List[str] = None,
                 metadata: Dict[str, Any] = None):
        self.id = id
        self.score = score
        self.title = title
        self.path = path
        self.source_type = source_type
        self.text = text[:1200] if text else ""
        self.tags = tags or []
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "score": self.score, "title": self.title,
                "path": self.path, "source_type": self.source_type,
                "text": self.text, "tags": self.tags, "metadata": self.metadata}


# ===== Vector Index =====

def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(a[i] * a[i] for i in range(n)))
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n)))
    return dot / (na * nb) if na and nb else 0.0


class VectorIndex:
    """Persistent vector index with build/load/search."""

    def __init__(self, embedding_client: Optional[EmbeddingClient] = None):
        self.embedding = embedding_client or make_embedding_client()
        self.records: List[Dict[str, Any]] = []  # [{id, embedding, doc}]

    def build(self, documents: List[RetrievalDocument]) -> "VectorIndex":
        texts = [d.text for d in documents]
        vectors = self.embedding.embed_texts(texts)
        self.records = [
            {"id": doc.id, "embedding": vec, "doc": doc.to_dict()}
            for doc, vec in zip(documents, vectors)
        ]
        return self

    def add_document(self, doc: RetrievalDocument) -> "VectorIndex":
        vec = self.embedding.embed_texts([doc.text])[0]
        self.records.append({"id": doc.id, "embedding": vec, "doc": doc.to_dict()})
        return self

    def save(self, path: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.records, indent=2), encoding="utf-8")
        return path

    def load(self, path: str) -> "VectorIndex":
        p = Path(path)
        if not p.exists():
            return self
        self.records = json.loads(p.read_text(encoding="utf-8"))
        return self

    def search(self, query: str, limit: int = 10,
               source_type: Optional[str] = None) -> List[SearchHit]:
        qvec = self.embedding.embed_texts([query])[0]
        scored = []
        for r in self.records:
            if source_type and r.get("doc", {}).get("source_type") != source_type:
                continue
            score = cosine_similarity(qvec, r["embedding"])
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)

        hits = []
        for score, rec in scored[:limit]:
            d = rec["doc"]
            hits.append(SearchHit(
                id=d["id"], score=float(score), title=d["title"],
                path=d["path"], source_type=d["source_type"],
                text=d["text"], tags=d.get("tags", []),
                metadata=d.get("metadata", {}),
            ))
        return hits


# ===== Build index from resource library =====

def build_resource_index(library: Any, output_path: str) -> VectorIndex:
    """Build a vector index from the ResourceLibrary."""
    from .library import ResourceLibrary
    lib = library if isinstance(library, ResourceLibrary) else ResourceLibrary().load()

    docs = []
    for rid, res in lib.resources.items():
        text_parts = [
            res.get("name", ""), res.get("category", ""),
            " ".join(res.get("features", [])),
            res.get("shopdrawing_note", "") or "",
            res.get("shop_note", "") or "",
        ]
        text = " ".join(p for p in text_parts if p)

        docs.append(RetrievalDocument(
            id=rid,
            source_type="resource_json",
            path=res.get("_path", ""),
            title=res.get("name", rid),
            text=text,
            tags=res.get("features", []),
            metadata={"category": res.get("category", ""), "parameters": list(res.get("parameters", {}).keys())},
        ))

    index = VectorIndex().build(docs)
    index.save(output_path)
    return index


# ===== CAD Retrieval Service =====

class CADRetrievalService:
    """Full retrieval service: query, rank, and scene building."""

    def __init__(self, index_path: Optional[str] = None):
        INDEX_DIR = Path(os.getenv("RETRIEVAL_INDEX_DIR", "data/retrieval"))
        self.index_path = index_path or str(INDEX_DIR / "vector_index.json")
        self.index = VectorIndex().load(self.index_path)

    def query(self, query: str, limit: int = 10) -> List[SearchHit]:
        return self.index.search(query, limit=limit)

    def query_from_features(self, features: "CloudVisionFeatureSet",
                            limit: int = 10) -> List[SearchHit]:
        query = self._build_query(features)
        return self.index.search(query, limit=limit)

    def rebuild_index(self, library: Any = None) -> str:
        """Rebuild index from resource library and save."""
        from .library import ResourceLibrary
        lib = library or ResourceLibrary().load()
        return build_resource_index(lib, self.index_path).save(self.index_path)

    def _build_query(self, features) -> str:
        parts = [
            features.product_type,
            features.subtype or "",
            features.top_shape or "",
            features.support_type or "",
            features.material_top or "",
            features.material_base or "",
            " ".join(features.visible_parts),
            " ".join(features.style_keywords),
        ]
        return " ".join(x for x in parts if x)
