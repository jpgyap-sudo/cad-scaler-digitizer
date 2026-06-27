"""Feedback storage — persists approved/rejected scenes for learning."""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from .schema import ParametricSceneGraph

FEEDBACK_DIR = Path(os.environ.get("FEEDBACK_DIR", str(Path(__file__).parent.parent.parent / "data" / "feedback")))
VALIDATION_DIR = Path(os.environ.get("VALIDATION_DIR", str(Path(__file__).parent.parent.parent / "data" / "validation")))


def save_feedback(
    scene: ParametricSceneGraph,
    approved: bool,
    comment: str = "",
    user_id: str = "default",
) -> str:
    """Save a user feedback entry for a scene graph.
    
    Returns the feedback file path.
    """
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    entry = {
        "timestamp": timestamp,
        "product_type": scene.product_type,
        "approved": approved,
        "comment": comment,
        "user_id": user_id,
        "component_count": len(scene.components),
        "material_count": len(scene.materials),
        "warnings": scene.warnings,
    }
    fname = f"{'approved' if approved else 'rejected'}_{scene.product_type}_{timestamp}.json"
    fpath = FEEDBACK_DIR / fname
    fpath.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    print(f"[Feedback] Saved: {fpath}")
    return str(fpath)


def save_validation_scene(
    scene: ParametricSceneGraph,
    label: str = "auto_generated",
) -> str:
    """Save a scene graph as a validation fixture.
    
    These can be used to regression-test the constraint solver
    and generator pipeline.
    """
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"scene_{scene.product_type}_{label}_{timestamp}.json"
    fpath = VALIDATION_DIR / fname
    data = json.loads(scene.model_dump_json())
    data["_meta"] = {"label": label, "saved": timestamp}
    fpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(fpath)


def load_feedback_history(limit: int = 20) -> list[Dict[str, Any]]:
    """Load recent feedback entries."""
    if not FEEDBACK_DIR.exists():
        return []
    entries = []
    for fpath in sorted(FEEDBACK_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            entries.append(json.loads(fpath.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return entries


def get_feedback_stats() -> Dict[str, Any]:
    """Get aggregated feedback statistics."""
    entries = load_feedback_history(limit=1000)
    total = len(entries)
    approved = sum(1 for e in entries if e.get("approved"))
    return {
        "total": total,
        "approved": approved,
        "rejected": total - approved,
        "approval_rate": round(approved / max(total, 1), 2),
        "product_types": list(set(e.get("product_type", "") for e in entries)),
    }
