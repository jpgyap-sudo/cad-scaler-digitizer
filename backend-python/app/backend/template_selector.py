"""HomeU furniture template selector for cad-scaler-digitizer.
Drop this file into your backend/service layer and point TEMPLATE_DIR to resources/furniture_templates.
It scores templates using category, product title, tags, detected shapes, and component detections.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Path: backend-python/app/backend/template_selector.py
# Resources are at: project_root/resources/furniture_templates/
TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "resources" / "furniture_templates"


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


def select_template(evidence: Dict[str, Any], min_confidence: float = 18.0) -> Dict[str, Any]:
    scored = []
    for t in load_templates():
        s, r = score_template(t, evidence)
        scored.append((s, t, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best, reasons = scored[0]
    return {
        "selected_template_id": best["template_id"],
        "confidence": min(0.99, max(0.0, best_score / 60.0)),
        "needs_confirmation": best_score < min_confidence,
        "reason_codes": reasons,
        "top_candidates": [
            {"template_id": t["template_id"], "score": s, "reasons": r[:8]} for s, t, r in scored[:5]
        ],
    }


if __name__ == "__main__":
    example = {"title": "Round Stone Nesting Coffee Tables", "category": "center table", "tags": ["round", "stone", "nesting"], "detected_shapes": ["circle"], "detected_components": ["tabletop", "base"]}
    print(json.dumps(select_template(example), indent=2))
