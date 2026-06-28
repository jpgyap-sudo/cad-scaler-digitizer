"""3-Stage Product Classifier — Family → Subtype → Nearest Template.

Pipeline:
  Stage 1 — Furniture Family Detection: OCR text + shapes → family name (101)
  Stage 2 — Subtype Detection: Within family, find specific product
  Stage 3 — Nearest Template: Visual DNA 32D search for top-3 matches

Integrates with:
  - resources/product_catalog/product_dna.json (per-product enriched DNA)
  - app/backend/product_search.py (visual DNA vector search)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("product_classifier")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CATALOG_DIR = Path(__file__).resolve().parents[2] / "resources" / "product_catalog"
DNA_PATH = CATALOG_DIR / "product_dna.json"
DNA_INDEX_PATH = CATALOG_DIR / "visual_dna_index.json"

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------
_PRODUCT_DNA_CACHE: Dict[str, Any] | None = None
_DNA_INDEX_CACHE: Dict[str, Any] | None = None

# ---------------------------------------------------------------------------
# Shape keyword mapping (family → expected shapes)
# ---------------------------------------------------------------------------
FAMILY_SHAPE_MAP: Dict[str, List[str]] = {
    # Sofas / seating
    "sofa": ["rectangle", "round"],
    "bench": ["rectangle"],
    "armchair": ["rectangle", "round"],
    "lounge_chair": ["rectangle", "round"],
    "ottoman": ["rectangle", "round", "square"],
    "pouf": ["round", "square"],
    "bar_stool": ["round", "square"],
    # Tables
    "dining_table": ["rectangle", "round", "oval"],
    "coffee_table": ["rectangle", "oval", "round"],
    "side_table": ["round", "rectangle"],
    "console_table": ["rectangle"],
    "pedestal_table": ["round", "oval"],
    "desk": ["rectangle"],
    # Lighting
    "pendant": ["round", "oval", "rectangle"],
    "chandelier": ["round", "oval"],
    "ceiling_fan": ["round"],
    "lamp": ["round", "rectangle"],
    "sconce": ["rectangle", "round"],
    # Storage
    "cabinet": ["rectangle"],
    "wardrobe": ["rectangle"],
    "sideboard": ["rectangle"],
    # Decor
    "rug": ["rectangle", "round", "oval"],
    "pillow": ["square", "rectangle"],
    "wall_panel": ["rectangle"],
    "stone": ["rectangle"],
    "sintered_stone": ["rectangle"],
    "bed": ["rectangle"],
    "headboard": ["rectangle"],
}

# Super-category mapping for cascade fallback (when no family matches)
FAMILY_CATEGORIES: Dict[str, List[str]] = {
    "sofa": ["sofa", "armchair", "lounge_chair", "bench", "ottoman", "sectional"],
    "chair": ["armchair", "dining_chair", "lounge_chair", "bar_stool", "accent_chair"],
    "table": ["dining_table", "coffee_table", "side_table", "console_table", "pedestal_table", "desk"],
    "desk": ["desk", "writing_desk", "computer_desk", "standing_desk"],
    "bed": ["bed", "headboard", "platform_bed", "sleigh_bed", "storage_bed"],
    "cabinet": ["cabinet", "wardrobe", "sideboard", "bookcase", "shelf", "nightstand"],
    "lighting": ["pendant", "chandelier", "ceiling_fan", "lamp", "sconce"],
    "rug": ["rug", "runner", "carpet"],
    "decor": ["pillow", "wall_panel", "vase", "decor"],
    "outdoor": ["outdoor_dining", "outdoor_lounger", "outdoor_sofa"],
}


def _load_dna() -> Dict[str, Any]:
    """Lazy-load per-product DNA."""
    global _PRODUCT_DNA_CACHE
    if _PRODUCT_DNA_CACHE is not None:
        return _PRODUCT_DNA_CACHE
    if DNA_PATH.exists():
        try:
            _PRODUCT_DNA_CACHE = json.loads(DNA_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load product DNA: {e}")
            _PRODUCT_DNA_CACHE = {}
    else:
        logger.warning(f"Product DNA not found: {DNA_PATH}")
        _PRODUCT_DNA_CACHE = {}
    return _PRODUCT_DNA_CACHE


def _load_dna_index() -> Dict[str, Any]:
    """Lazy-load family DNA index."""
    global _DNA_INDEX_CACHE
    if _DNA_INDEX_CACHE is not None:
        return _DNA_INDEX_CACHE
    if DNA_INDEX_PATH.exists():
        try:
            _DNA_INDEX_CACHE = json.loads(DNA_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load DNA index: {e}")
            _DNA_INDEX_CACHE = {}
    else:
        logger.warning(f"DNA index not found: {DNA_INDEX_PATH}")
        _DNA_INDEX_CACHE = {}
    return _DNA_INDEX_CACHE


# ---------------------------------------------------------------------------
# Stage 1 — Furniture Family Detection
# ---------------------------------------------------------------------------

def _known_families() -> List[str]:
    """Return all known family names from DNA index."""
    return list(_load_dna_index().keys())


def _score_family_match(family_name: str, text: str) -> float:
    """Score how well a family name matches OCR text."""
    family_lower = family_name.lower().replace("_", " ")
    text_lower = text.lower()

    score = 0.0

    # Direct substring match
    if family_lower in text_lower:
        score += 0.5
    elif text_lower in family_lower:
        score += 0.3

    # Word-level overlap
    family_words = set(family_lower.split())
    text_words = set(text_lower.split())
    overlap = family_words & text_words
    if overlap:
        score += min(len(overlap) * 0.15, 0.5)

    # Check for key discriminators
    for word in family_words:
        if len(word) > 3 and word in text_lower:
            score += 0.1

    return min(score, 1.0)


def _score_shape_match(family_name: str, detected_shapes: List[str]) -> float:
    """Score how well detected shapes match expected family shapes."""
    if not detected_shapes:
        return 0.0

    expected = FAMILY_SHAPE_MAP.get(family_name, [])
    if not expected:
        return 0.5  # neutral

    matches = 0
    for shape in detected_shapes:
        shape_lower = shape.lower().strip()
        for exp in expected:
            if exp in shape_lower or shape_lower in exp:
                matches += 1
                break

    return min(matches / len(detected_shapes), 1.0)


def detect_family(
    text: str = "",
    detected_shapes: Optional[List[str]] = None,
) -> Tuple[str, float]:
    """Stage 1: Detect furniture family from OCR text + detected shapes.

    Returns (family_name, confidence).
    """
    detected_shapes = detected_shapes or []
    families = _known_families()
    if not families:
        logger.warning("No known families loaded")
        return ("unknown", 0.0)

    scored: List[Tuple[float, str]] = []
    for family in families:
        text_score = _score_family_match(family, text)
        shape_score = _score_shape_match(family, detected_shapes)
        # Blend: 70% text, 30% shape
        combined = text_score * 0.7 + shape_score * 0.3
        if combined > 0.05:
            scored.append((combined, family))

    if not scored:
        # Fallback: try to find any family matching a category
        for family in families:
            text_score = _score_family_match(family, text)
            if text_score > 0:
                scored.append((text_score, family))

    if not scored:
        # Cascade fallback: try super-category matching via FAMILY_CATEGORIES
        text_lower = text.lower()
        for super_cat, sub_families in FAMILY_CATEGORIES.items():
            if super_cat in text_lower:
                candidates = [f for f in families if f in sub_families]
                if candidates:
                    for cf in candidates:
                        text_score = _score_family_match(cf, text)
                        if text_score > 0:
                            scored.append((text_score * 0.5, cf))
        if not scored:
            return ("unknown", 0.0)

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_family = scored[0]
    return (best_family, round(best_score, 4))


# ---------------------------------------------------------------------------
# Stage 2 — Subtype Detection (per-product match within family)
# ---------------------------------------------------------------------------

def detect_subtype(
    family: str,
    text: str = "",
    detected_shapes: Optional[List[str]] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Stage 2: Within a family, find specific subtype products.

    Returns sorted list of candidate products with scores.
    """
    detected_shapes = detected_shapes or []
    dna = _load_dna()

    # Find all products matching this family
    candidates: List[Dict[str, Any]] = []
    for handle, entry in dna.items():
        entry_family = entry.get("template_family", "")
        if entry_family == family:
            candidates.append(entry)
        elif entry.get("visual_dna_family", "") == family:
            candidates.append(entry)

    if not candidates:
        # Broader match: family substring
        for handle, entry in dna.items():
            entry_family = entry.get("template_family", "")
            if family in entry_family or entry_family in family:
                candidates.append(entry)

    if not candidates:
        logger.info(f"No candidates found for family: {family}")
        return []

    # Score each candidate
    scored: List[Tuple[float, Dict]] = []
    for entry in candidates:
        score = 0.0

        # Text match on title
        title = entry.get("title", "")
        title_score = _score_family_match(title, text)
        score += title_score * 0.5

        # Shape match
        shape_score = _score_shape_match(
            entry.get("template_family", ""), detected_shapes
        )
        score += shape_score * 0.3

        # Tag match
        tags = entry.get("tags", [])
        text_lower = text.lower()
        tag_matches = sum(1 for t in tags if t.lower() in text_lower)
        if tag_matches > 0:
            score += min(tag_matches * 0.1, 0.2)

        if score > 0.05:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, entry in scored[:top_k]:
        results.append({
            "handle": entry.get("handle", ""),
            "title": entry.get("title", ""),
            "template_family": entry.get("template_family", ""),
            "score": round(score, 4),
            "edge_profile": entry.get("edge_profile", ""),
            "symmetry": entry.get("symmetry", ""),
            "leg_count": entry.get("leg_count", 0),
            "material_primary": entry.get("material_primary", ""),
            "bounding_ratio": entry.get("bounding_ratio", ""),
        })

    return results


# ---------------------------------------------------------------------------
# Stage 3 — Nearest Template (Visual DNA search)
# ---------------------------------------------------------------------------

def find_nearest_templates(
    family: str,
    subtype_handle: Optional[str] = None,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Stage 3: Find closest product templates using Visual DNA 32D search.

    Integrates with product_search.py.
    """
    try:
        from app.backend.product_search import search_by_visual_dna

        # Build visual features from family DNA
        dna_index = _load_dna_index()
        family_entry = dna_index.get(family, {})

        # If we have a specific subtype, use its enriched DNA
        if subtype_handle:
            dna = _load_dna()
            subtype_entry = dna.get(subtype_handle, {})
            if subtype_entry:
                # Override with subtype's enriched fields
                family_entry["edge_profile"] = subtype_entry.get("edge_profile", "")
                family_entry["thickness_profile"] = subtype_entry.get("thickness_profile", "")
                family_entry["leg_count"] = subtype_entry.get("leg_count", 0)
                family_entry["bounding_ratio"] = subtype_entry.get("bounding_ratio", "")

        features = {
            "top_shape": family_entry.get("top_shape", ""),
            "base_type": family_entry.get("base_type", ""),
            "leg_type": family_entry.get("leg_type", ""),
            "symmetry": family_entry.get("symmetry", "symmetric"),
            "category_hint": family_entry.get("category_hint", ""),
            "components": family_entry.get("component_graph", family_entry.get("components", [])),
            "materials": family_entry.get("materials", []),
            "archetype_score": family_entry.get("archetype_score", 0.5),
        }

        results = search_by_visual_dna(features, top_k=top_k)
        return results

    except ImportError:
        logger.warning("product_search not available, using fallback")
        return []
    except Exception as e:
        logger.warning(f"Visual DNA search failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def classify_product(
    text: str = "",
    detected_shapes: Optional[List[str]] = None,
    detected_components: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Full 3-Stage classification pipeline.

    Args:
        text: OCR-extracted text from the drawing
        detected_shapes: e.g. ["rectangle", "circle", "oval"]
        detected_components: e.g. ["seat", "backrest", "legs"]

    Returns:
        dict with stages:
          - family: detected family name
          - family_confidence: confidence score
          - subtypes: list of candidate products
          - matches: top-3 visual DNA matches
    """
    detected_shapes = detected_shapes or []
    detected_components = detected_components or []

    logger.info(
        f"Classifying: text='{text[:60]}...' shapes={detected_shapes}"
    )

    # Stage 1: Family
    family, family_conf = detect_family(text, detected_shapes)
    logger.info(f"Stage 1 — Family: {family} (confidence={family_conf})")

    # Stage 2: Subtype
    subtypes = detect_subtype(family, text, detected_shapes)
    logger.info(f"Stage 2 — Subtypes: {len(subtypes)} candidates")

    # Stage 3: Nearest template
    subtype_handle = subtypes[0].get("handle") if subtypes else None
    matches = find_nearest_templates(family, subtype_handle)
    logger.info(f"Stage 3 — Nearest: {len(matches)} matches")

    return {
        "family": family,
        "family_confidence": family_conf,
        "subtypes": subtypes,
        "matches": matches,
        "pipeline": "3-stage",
    }


# ---------------------------------------------------------------------------
# Main / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Product Classifier — 3-Stage Pipeline Demo")
    print("=" * 60)

    import sys
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore

    # Test cases
    test_cases = [
        ("modern sofa with plush cushions", ["rectangle"], ["seat", "backrest", "arms"]),
        ("round dining table 120cm diameter", ["circle"], ["top", "base"]),
        ("wall mounted ceiling fan with light", ["circle"], ["blades", "mount", "light"]),
        ("sintered stone slab 240x120", ["rectangle"], ["surface"]),
        ("bar stool 65cm height", ["round"], ["seat", "legs"]),
    ]

    for text, shapes, comps in test_cases:
        print(f"\n--- Input: '{text}' shapes={shapes}")
        result = classify_product(text, shapes, comps)
        print(f"  Family: {result['family']} (conf={result['family_confidence']})")
        print(f"  Subtypes: {len(result['subtypes'])}")
        if result["subtypes"]:
            top = result["subtypes"][0]
            print(f"    Top: {top.get('title','?')} (score={top['score']})")
        print(f"  Matches: {len(result['matches'])}")
        if result["matches"]:
            for m in result["matches"]:
                print(f"    {m['family']} score={m['score']}")
