"""
Correction API — human-in-the-loop dimension-to-geometry assignment.

This enables Phase 2 of the accuracy upgrade:
  "click OCR dimension → assign to object edge/circle"
  "choose 'this is 80 cm diameter'"
  "choose 'this line is leader, not dimension'"
  "lock confirmed dimensions"
  "regenerate DXF"

The correction workflow:
1. User uploads image → accuracy pipeline runs → associations returned
2. User reviews associations in the UI
3. User can:
   a. Confirm an association (lock it)
   b. Correct a value (e.g. "this is 80, not 40")
   c. Re-classify a line role (e.g. "this is LEADER, not DIMENSION")
   d. Assign a dimension to a different geometry element
4. Corrections are recorded in the Central Brain for ML learning
5. DXF is regenerated with corrected values
"""

import json
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

# Directory for correction state
CORRECTIONS_DIR = Path(os.path.dirname(__file__)) / ".." / "corrections"
CORRECTIONS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Automatic retraining trigger
# After every CORRECTION_THRESHOLD correction submissions, train_classifier.py
# is spawned as a background subprocess, creating a self-improving feedback loop.
# ---------------------------------------------------------------------------
_correction_count = 0
_correction_threshold = 10
_correction_lock = threading.Lock()

def _trigger_retraining():
    """Spawn train_classifier.py as a non-blocking background subprocess."""
    try:
        script_path = Path(__file__).parent.parent.parent / "scripts" / "train_classifier.py"
        if not script_path.exists():
            # Fallback: try VPS container path
            script_path = Path("/app/scripts/train_classifier.py")
        env = os.environ.copy()
        env.setdefault("PYTHONPATH", str(Path(__file__).parent.parent.parent))
        subprocess.Popen(
            [sys.executable or "python3", str(script_path)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # Non-blocking; ignore failures silently


@dataclass
class DimensionCorrection:
    """A single user correction to a dimension."""
    session_id: str
    ocr_text: str
    original_value_cm: float
    corrected_value_cm: float
    assigned_to_entity_id: Optional[str] = None
    assigned_to_entity_type: Optional[str] = None  # "circle", "line", "polygon"
    is_locked: bool = False
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "ocr_text": self.ocr_text,
            "original_value_cm": self.original_value_cm,
            "corrected_value_cm": self.corrected_value_cm,
            "assigned_to_entity_id": self.assigned_to_entity_id,
            "assigned_to_entity_type": self.assigned_to_entity_type,
            "is_locked": self.is_locked,
            "note": self.note,
        }


@dataclass
class LineRoleCorrection:
    """User correction to a line's classified role."""
    session_id: str
    line_id: str  # Index or identifier in vision_lines
    original_role: str
    corrected_role: str  # "OBJECT_EDGE", "DIMENSION_LINE", "LEADER", etc.
    is_locked: bool = False

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "line_id": self.line_id,
            "original_role": self.original_role,
            "corrected_role": self.corrected_role,
            "is_locked": self.is_locked,
        }


def save_corrections(session_id: str,
                     dimension_corrections: List[DimensionCorrection],
                     line_role_corrections: List[LineRoleCorrection]):
    """Save user corrections for a session."""
    data = {
        "session_id": session_id,
        "dimension_corrections": [c.to_dict() for c in dimension_corrections],
        "line_role_corrections": [c.to_dict() for c in line_role_corrections],
    }
    path = CORRECTIONS_DIR / f"{session_id}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def load_corrections(session_id: str) -> Dict[str, Any]:
    """Load user corrections for a session."""
    path = CORRECTIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return {"session_id": session_id, "dimension_corrections": [], "line_role_corrections": []}
    with open(path) as f:
        return json.load(f)


def apply_dimension_corrections(
    associations: List[Dict],
    corrections: List[Dict]
) -> List[Dict]:
    """
    Apply user corrections to dimension associations.

    Updates values, locks, and entity assignments based on user input.
    """
    corrected = list(associations)
    correction_map = {c.get("ocr_text", ""): c for c in corrections}

    for i, assoc in enumerate(corrected):
        text = assoc.get("text", "")
        if text in correction_map:
            corr = correction_map[text]
            assoc["value_cm"] = corr.get("corrected_value_cm", assoc["value_cm"])
            assoc["confidence"] = 0.98  # User-confirmed = high confidence
            assoc["evidence"] = assoc.get("evidence", []) + ["user_corrected"]
            assoc["source"] = "user_confirmed"
            if corr.get("assigned_to_entity_id"):
                assoc["assigned_entity_id"] = corr["assigned_to_entity_id"]
                assoc["assigned_entity_type"] = corr["assigned_to_entity_type"]

    return corrected


def apply_line_role_corrections(
    line_classification: Dict,
    corrections: List[Dict]
) -> Dict:
    """Apply user corrections to line role classification."""
    result = dict(line_classification)
    corr_map = {c.get("line_id", ""): c for c in corrections}

    for role_key in ["object_edges", "dimension_lines", "extension_lines",
                     "leaders", "centerlines", "hatches", "hidden_lines", "unknown"]:
        lines = result.get(role_key, [])
        for i, line in enumerate(lines):
            line_id = f"{role_key}_{i}"
            if line_id in corr_map:
                corr = corr_map[line_id]
                # Move line to correct role bucket
                new_role = corr.get("corrected_role", "")
                if new_role != role_key:
                    # Will be moved in post-processing
                    line["_move_to"] = new_role

    return result


# ===== API Endpoint Handlers =====

def handle_correction_submission(session_id: str,
                                  dimension_corrections: List[dict],
                                  line_role_corrections: List[dict]) -> dict:
    """
    Handle a user correction submission.

    Args:
        session_id: The drawing session ID
        dimension_corrections: List of correction dicts
        line_role_corrections: List of line role correction dicts

    Returns:
        Summary of what was corrected
    """
    # Build dataclasses from dicts, injecting session_id and filtering only
    # known fields for safety (the API endpoint receives session_id as a
    # separate form field, not inside each correction dict).
    dc_fields = {f.name for f in DimensionCorrection.__dataclass_fields__.values()}
    rc_fields = {f.name for f in LineRoleCorrection.__dataclass_fields__.values()}
    dim_corrections = [
        DimensionCorrection(**{k: v for k, v in c.items()
                                if k in dc_fields and k != 'session_id'},
                             session_id=session_id)
        for c in dimension_corrections
    ]
    role_corrections = [
        LineRoleCorrection(**{k: v for k, v in c.items()
                               if k in rc_fields and k != 'session_id'},
                            session_id=session_id)
        for c in line_role_corrections
    ]

    path = save_corrections(session_id, dim_corrections, role_corrections)

    # Increment correction counter and trigger retraining at threshold
    global _correction_count
    with _correction_lock:
        _correction_count += len(dim_corrections) + len(role_corrections)
        retraining_triggered = False
        if _correction_count >= _correction_threshold:
            _correction_count = 0
            retraining_triggered = True
            _trigger_retraining()

    return {
        "session_id": session_id,
        "corrections_saved": len(dim_corrections) + len(role_corrections),
        "path": str(path),
        "retraining_triggered": retraining_triggered,
        "message": f"Saved {len(dim_corrections)} dimension + {len(role_corrections)} line corrections",
    }


def handle_correction_reset(session_id: str) -> dict:
    """Reset all corrections for a session."""
    path = CORRECTIONS_DIR / f"{session_id}.json"
    if path.exists():
        os.remove(path)
    return {"session_id": session_id, "status": "reset"}


# Public API
def submit_corrections(session_id: str,
                       dimension_corrections: List[dict],
                       line_role_corrections: List[dict]) -> dict:
    """Main entry point: submit user corrections."""
    return handle_correction_submission(session_id, dimension_corrections, line_role_corrections)


def get_corrections(session_id: str) -> dict:
    """Main entry point: get saved corrections for a session."""
    return load_corrections(session_id)


def reset_corrections(session_id: str) -> dict:
    """Main entry point: reset all corrections."""
    return handle_correction_reset(session_id)
