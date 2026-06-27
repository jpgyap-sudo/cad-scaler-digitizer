"""Simple text-vector retrieval — TF-IDF cosine similarity search."""
import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Tuple


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def resource_text(resource: Dict[str, Any]) -> str:
    parts = [
        resource.get("id", ""),
        resource.get("name", ""),
        resource.get("category", ""),
        " ".join(resource.get("features", [])),
        " ".join(resource.get("tags", [])),
        resource.get("shopdrawing_note", "") or "",
        resource.get("shop_note", "") or "",
    ]
    return " ".join(parts)


def vectorize(text: str) -> Counter:
    return Counter(tokenize(text))


def cosine_similarity(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class SimpleRetriever:
    """In-memory TF-IDF retriever for resource library."""

    def __init__(self, resources: Iterable[Dict[str, Any]]):
        self.items: List[Tuple[Dict[str, Any], Counter]] = []
        for r in resources:
            self.items.append((r, vectorize(resource_text(r))))

    def search(self, query: str, category: str | None = None,
               limit: int = 10) -> List[Tuple[float, Dict[str, Any]]]:
        qv = vectorize(query)
        scored = []
        for r, rv in self.items:
            if category and r.get("category") != category:
                continue
            score = cosine_similarity(qv, rv)
            if score > 0:
                scored.append((score, r))
        return sorted(scored, key=lambda x: x[0], reverse=True)[:limit]

    def search_by_category(self, query: str, category: str,
                            limit: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        return self.search(query, category=category, limit=limit)
