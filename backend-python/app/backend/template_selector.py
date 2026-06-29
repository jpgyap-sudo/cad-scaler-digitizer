"""HomeU furniture template selector for cad-scaler-digitizer.

DUAL-PASS SEARCH:
  1. First searches 259 Shopify product templates via Visual DNA similarity.
  2. Falls back to 34 HomeU construction templates.
  3. Returns both results with confidence scores.

Scoring uses category, product title, tags, detected shapes, and component detections.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.backend.resource_paths import resolve_resources_dir

_RESOURCES_DIR = resolve_resources_dir(Path(__file__))
TEMPLATE_DIR = _RESOURCES_DIR / "furniture_templates"
CATALOG_DIR = _RESOURCES_DIR / "product_catalog"

# ---------------------------------------------------------------------------
# Legacy construction template loader
# ---------------------------------------------------------------------------

def load_templates(template_dir: Path = TEMPLATE_DIR) -> List[Dict[str, Any]]:
    templates = []
    for p in sorted(template_dir.glob("*.json")):
        if p.name.startswith("_registry"):
            continue
        with p.open("r", encoding="utf-8") as f:
            t = json.load(f)
        t["_file"] = str(p)
        templates.append(t)
    return templates


def _norm_list(values: Any) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    return [str(v).lower().replace("_", "-").strip() for v in values]


def score_template(template: Dict[str, Any], evidence: Dict[str, Any]) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []
    text = " ".join(_norm_list([evidence.get("title", ""), evidence.get("category", "")] + evidence.get("tags", [])))
    shapes = set(_norm_list(evidence.get("detected_shapes", [])))
    components = set(_norm_list(evidence.get("detected_components", [])))

    for kw in template.get("keywords", []):
        nkw = str(kw).lower().replace("_", "-")
        if nkw in text:
            score += 8
            reasons.append(f"keyword:{kw}")

    for clue in template.get("visual_signature", {}).get("positive", []):
        token = str(clue).lower().replace("_", "-")
        if token in shapes or token in components or token in text:
            score += 5
            reasons.append(f"positive:{clue}")

    for clue in template.get("visual_signature", {}).get("negative", []):
        token = str(clue).lower().replace("_", "-")
        if token in shapes or token in components or token in text:
            score -= 7
            reasons.append(f"negative:{clue}")

    for part in template.get("parts", []):
        name = str(part.get("name", "")).lower().replace("_", "-")
        if name in components:
            score += 3
            reasons.append(f"part:{name}")

    if evidence.get("aspect_ratio"):
        ar = float(evidence["aspect_ratio"])
        ar_rule = template.get("aspect_ratio_hint", {})
        if ar_rule:
            mn, mx = ar_rule.get("min", 0), ar_rule.get("max", 999)
            if mn <= ar <= mx:
                score += 6
                reasons.append("aspect-ratio-ok")
            else:
                score -= 3
                reasons.append("aspect-ratio-off")

    return score, reasons


# ---------------------------------------------------------------------------
# Product Catalog search (259 Shopify templates via Visual DNA)
# ---------------------------------------------------------------------------

def _build_features_from_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Convert evidence dict (from AI analysis) to visual DNA features."""
    features = {
        "top_shape": "",
        "base_type": "",
        "leg_type": "",
        "category_hint": "",
        "materials": [],
        "components": [],
        "symmetry": "symmetric",
    }
    text = str(evidence.get("title", "")).lower() + " " + str(evidence.get("category", "")).lower()
    text += " " + " ".join(str(t).lower() for t in evidence.get("tags", []))

    # Infer shape from detected shapes
    shapes = [s.lower() for s in evidence.get("detected_shapes", [])]
    if any(s in ("rectangular", "rectangle") for s in shapes):
        features["top_shape"] = "rectangular"
    elif any(s in ("round", "circle", "circular") for s in shapes):
        features["top_shape"] = "round"
    elif any(s in ("oval", "ellipse") for s in shapes):
        features["top_shape"] = "oval"
    elif any(s in ("square",) for s in shapes):
        features["top_shape"] = "square"

    # Infer category from text + tags
    cat_keywords = {
        "sofa": ["sofa", "settee", "couch", "loveseat"],
        "chair": ["chair", "armchair", "dining chair", "lounge chair"],
        "table": ["table", "coffee table", "dining table", "side table", "console table"],
        "lighting": ["light", "lamp", "chandelier", "pendant", "sconce"],
        "storage": ["cabinet", "sideboard", "drawer", "shelf", "wardrobe"],
        "bed": ["bed", "headboard"],
        "rug": ["rug", "carpet", "runner"],
    }
    for cat, keywords in cat_keywords.items():
        if any(kw in text for kw in keywords):
            features["category_hint"] = cat
            break

    # Materials from text
    mat_keywords = {
        "wood": ["wood", "walnut", "oak", "teak"],
        "metal": ["metal", "steel", "brass", "iron", "aluminum"],
        "fabric": ["fabric", "upholstered", "velvet", "linen", "cotton"],
        "leather": ["leather"],
        "glass": ["glass"],
        "marble": ["marble", "stone"],
    }
    for mat, keywords in mat_keywords.items():
        if any(kw in text for kw in keywords):
            features["materials"].append(mat)

    # Components from evidence
    comps = evidence.get("detected_components", [])
    if comps:
        features["components"] = comps if isinstance(comps, list) else [comps]

    return features


def select_template_dual(
    evidence: Dict[str, Any],
    min_confidence: float = 18.0,
    top_k: int = 3,
) -> Dict[str, Any]:
    """Dual-pass template selection:

    1. Search product catalog (259 templates) by Visual DNA similarity.
    2. Fall back to 34 construction templates by keyword scoring.
    3. Return combined results with confidence.
    """
    result = {
        "catalog_matches": [],
        "construction_matches": [],
        "selected": None,
        "confidence": 0.0,
        "needs_confirmation": True,
        "source": "none",
    }

    # ---- Pass 1: Product catalog via Visual DNA ----
    try:
        from app.backend.product_search import search_by_visual_dna, search_by_text

        features = _build_features_from_evidence(evidence)

        if any(features.get(k) for k in ("top_shape", "category_hint", "base_type")):
            catalog_results = search_by_visual_dna(features, top_k=top_k)
        else:
            # No visual features — try text search
            text = str(evidence.get("title", "")) + " " + str(evidence.get("category", ""))
            catalog_results = search_by_text(text, top_k=top_k) if text.strip() else []

        result["catalog_matches"] = catalog_results

        # If a catalog match has high confidence, select it
        if catalog_results and catalog_results[0]["score"] > 0.5:
            top = catalog_results[0]
            confidence = min(0.99, top["score"])
            result["selected"] = {
                "source": "product_catalog",
                "family": top["family"],
                "score": top["score"],
                "reason": top["reason"],
                "archetype_score": top.get("archetype_score", 0.5),
                "items": top.get("items", []),
            }
            result["confidence"] = confidence
            result["needs_confirmation"] = confidence < 0.7
            result["source"] = "product_catalog"
    except ImportError:
        pass  # product_search not available — skip pass 1
    except Exception as e:
        print(f"[TemplateSelector] Catalog search failed: {e}")

    # ---- Pass 2: Construction templates (legacy scoring) ----
    try:
        scored = []
        for t in load_templates():
            s, r = score_template(t, evidence)
            scored.append((s, t, r))
        scored.sort(key=lambda x: x[0], reverse=True)

        if scored:
            best_score, best, reasons = scored[0]
            result["construction_matches"] = [
                {"template_id": t.get("template_id", t.get("_file", "")), "score": s, "reasons": r[:8]}
                for s, t, r in scored[:top_k]
            ]

            # Only use construction template if no catalog match or catalog confidence is low
            if result["selected"] is None:
                construction_confidence = min(0.99, max(0.0, best_score / 60.0))
                result["selected"] = {
                    "source": "construction_template",
                    "template_id": best.get("template_id"),
                    "score": best_score,
                    "reason": reasons[:5],
                    "construction_confidence": construction_confidence,
                }
                result["confidence"] = construction_confidence
                result["needs_confirmation"] = best_score < min_confidence
                result["source"] = "construction_template"
    except Exception as e:
        print(f"[TemplateSelector] Construction template search failed: {e}")

    return result


# ---- Legacy single-pass interface (backward compat) ----

def select_template(evidence: Dict[str, Any], min_confidence: float = 18.0) -> Dict[str, Any]:
    """Legacy single-pass: construction templates only.

    Calls the dual-pass search and returns construction template results.
    """
    result = select_template_dual(evidence, min_confidence)
    if result["construction_matches"]:
        top = result["construction_matches"][0]
        return {
            "selected_template_id": top["template_id"],
            "confidence": min(0.99, max(0.0, top["score"] / 60.0)),
            "needs_confirmation": top["score"] < min_confidence,
            "reason_codes": top["reasons"],
            "top_candidates": result["construction_matches"],
        }
    return {
        "selected_template_id": "none",
        "confidence": 0.0,
        "needs_confirmation": True,
        "reason_codes": [],
        "top_candidates": [],
    }


if __name__ == "__main__":
    example = {"title": "Round Stone Nesting Coffee Tables", "category": "center table", "tags": ["round", "stone", "nesting"], "detected_shapes": ["circle"], "detected_components": ["tabletop", "base"]}
    print("=== Legacy single-pass ===")
    print(json.dumps(select_template(example), indent=2))
    print("\n=== Dual-pass ===")
    print(json.dumps(select_template_dual(example), indent=2))
