"""
Echo Drafter — Passive learning system that adapts to user corrections.

Every user action (dimension override, material change, component toggle,
type correction) is recorded. Hermes Claw analyzes correction patterns and
builds a personal preference model. Future drawings are pre-adjusted using
learned preferences, making the output more accurate without explicit training.

Architecture:
  User action → FeedbackRecorder → JSON preference store
                                      ↓
  Hermes Claw brain_analyze → Pattern extraction (periodic)
                                      ↓
  PreferenceModel → pre-applied to next CAD generation
                                      ↓
  OpenClaw → pre-flight adjustment suggestions

Data flow:
  1. record_correction(session_id, field, old_value, new_value, context)
  2. get_preferences(user_id) → returns learned adjustments
  3. apply_preferences(drawing_params) → returns adjusted params
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Storage paths
MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "memory")
PREFERENCES_DIR = os.path.join(MEMORY_DIR, "user_preferences")
CORRECTIONS_DIR = os.path.join(MEMORY_DIR, "corrections")

os.makedirs(PREFERENCES_DIR, exist_ok=True)
os.makedirs(CORRECTIONS_DIR, exist_ok=True)


@dataclass
class Correction:
    """A single user correction event."""
    session_id: str
    field: str            # e.g. "pedestal_diameter_cm", "material_tabletop"
    old_value: Any         # system default or previous value
    new_value: Any         # user-specified value
    context: Dict[str, Any] = field(default_factory=dict)  # furniture_type, ocred dimensions, etc.
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0  # how confident was the system before correction (0-1)


@dataclass
class PreferenceModel:
    """Learned user preferences for furniture CAD generation."""
    user_id: str
    dimension_multipliers: Dict[str, float] = field(default_factory=dict)
        # e.g. {"pedestal_diameter_cm": 1.15, "top_thickness_cm": 0.9}
    material_overrides: Dict[str, str] = field(default_factory=dict)
        # e.g. {"tabletop": "Solid European Oak", "pedestal_base": "Textured brass"}
    component_visibility: Dict[str, bool] = field(default_factory=dict)
        # e.g. {"metal_ring": true, "base_foot": false}
    furniture_type_weights: Dict[str, float] = field(default_factory=dict)
        # e.g. {"round_pedestal_table": 0.8, "rectangular_table": 0.15}
    output_preferences: Dict[str, str] = field(default_factory=dict)
        # e.g. {"primary_format": "pdf", "paper_size": "A3"}
    correction_count: int = 0
    last_updated: float = 0.0
    confidence: float = 0.3  # overall model confidence (increases with corrections)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "dimension_multipliers": self.dimension_multipliers,
            "material_overrides": self.material_overrides,
            "component_visibility": self.component_visibility,
            "furniture_type_weights": self.furniture_type_weights,
            "output_preferences": self.output_preferences,
            "correction_count": self.correction_count,
            "last_updated": self.last_updated,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PreferenceModel":
        return cls(
            user_id=data.get("user_id", "default"),
            dimension_multipliers=data.get("dimension_multipliers", {}),
            material_overrides=data.get("material_overrides", {}),
            component_visibility=data.get("component_visibility", {}),
            furniture_type_weights=data.get("furniture_type_weights", {}),
            output_preferences=data.get("output_preferences", {}),
            correction_count=data.get("correction_count", 0),
            last_updated=data.get("last_updated", 0.0),
            confidence=data.get("confidence", 0.3),
        )


def _get_model_path(user_id: str) -> str:
    safe_id = user_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return os.path.join(PREFERENCES_DIR, f"{safe_id}_preferences.json")


def _get_corrections_path(session_id: str) -> str:
    safe_id = session_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return os.path.join(CORRECTIONS_DIR, f"{safe_id}_corrections.json")


# ===== Recording =====

def record_correction(
    session_id: str,
    field: str,
    old_value: Any,
    new_value: Any,
    context: Optional[Dict] = None,
    user_id: str = "default",
) -> Correction:
    """
    Record a user correction to the learning layer.

    Called whenever the user:
    - Overrides a dimension
    - Changes a material description
    - Toggles component visibility
    - Corrects furniture type
    - Provides new notes
    """
    correction = Correction(
        session_id=session_id,
        field=field,
        old_value=old_value,
        new_value=new_value,
        context=context or {},
    )

    # Append to session corrections file
    path = _get_corrections_path(session_id)
    existing = []
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                existing = json.load(f)
        except Exception:
            pass

    existing.append({
        "session_id": correction.session_id,
        "field": correction.field,
        "old_value": str(correction.old_value)[:200],
        "new_value": str(correction.new_value)[:200],
        "context": correction.context,
        "timestamp": correction.timestamp,
        "confidence": correction.confidence,
    })

    with open(path, 'w') as f:
        json.dump(existing, f, indent=2)

    # Update preference model
    _update_preferences_from_correction(user_id, correction)

    return correction


def _update_preferences_from_correction(user_id: str, correction: Correction):
    """Incrementally update the user's preference model from a correction."""
    model = load_preferences(user_id)
    model.correction_count += 1
    model.last_updated = time.time()

    # Update confidence: each correction adds ~0.05 confidence, max 0.95
    model.confidence = min(0.95, model.correction_count * 0.04 + 0.2)

    field = correction.field

    # === Dimension corrections: learn multiplier or record measurement ===
    if field.endswith("_cm") and isinstance(correction.new_value, (int, float)):
        if correction.new_value and correction.new_value > 0:
            if isinstance(correction.old_value, (int, float)) and correction.old_value > 0:
                # Correction: learn multiplier from old→new ratio
                multiplier = correction.new_value / correction.old_value
                prev = model.dimension_multipliers.get(field, 1.0)
                alpha = 0.3  # learning rate
                new_mult = prev * (1 - alpha) + multiplier * alpha
                model.dimension_multipliers[field] = round(new_mult, 3)
            else:
                # New measurement (no old_value): record as-is with multiplier 1.0
                if field not in model.dimension_multipliers:
                    model.dimension_multipliers[field] = 1.0

    # === Material corrections: record preferred material ===
    if field.startswith("material_"):
        component = field.replace("material_", "")
        model.material_overrides[component] = str(correction.new_value)[:100]

    # === Visibility corrections: record toggle ===
    if field.startswith("visibility_"):
        component = field.replace("visibility_", "")
        model.component_visibility[component] = bool(correction.new_value)

    # === Furniture type corrections: update weights ===
    if field == "furniture_type":
        ftype = str(correction.new_value)
        model.furniture_type_weights[ftype] = model.furniture_type_weights.get(ftype, 0) + 1

    save_preferences(user_id, model)


# ===== Preference Loading =====

def load_preferences(user_id: str = "default") -> PreferenceModel:
    """Load a user's learned preference model."""
    path = _get_model_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return PreferenceModel.from_dict(json.load(f))
        except Exception:
            pass
    return PreferenceModel(user_id=user_id)


def save_preferences(user_id: str, model: PreferenceModel):
    """Persist the preference model to disk."""
    path = _get_model_path(user_id)
    with open(path, 'w') as f:
        json.dump(model.to_dict(), f, indent=2)


# ===== Application =====

def apply_preferences(drawing_params: Dict[str, Any], user_id: str = "default") -> Dict[str, Any]:
    """
    Apply learned preferences to pre-adjust drawing parameters.

    Returns adjusted parameters that pre-empt user corrections.
    """
    model = load_preferences(user_id)
    if model.correction_count < 3:
        return drawing_params  # Not enough data yet

    adjusted = dict(drawing_params)

    # Apply dimension multipliers
    for field, multiplier in model.dimension_multipliers.items():
        if field in adjusted and adjusted[field] is not None:
            adjusted[field] = adjusted[field] * multiplier

    # Apply material overrides
    if "material_notes" not in adjusted:
        adjusted["material_notes"] = []
    for component, material in model.material_overrides.items():
        note = f"{component.upper()} — {material}"
        if note not in adjusted["material_notes"]:
            adjusted["material_notes"].append(note)

    # Apply visibility preferences
    if "visibility" not in adjusted:
        adjusted["visibility"] = {}
    adjusted["visibility"].update(model.component_visibility)

    return adjusted


def get_adjustment_hints(user_id: str = "default") -> List[Dict]:
    """
    Return human-readable hints about what the model learned.

    Used by OpenClaw pre-flight analysis to suggest adjustments.
    """
    model = load_preferences(user_id)
    hints = []

    for field, mult in model.dimension_multipliers.items():
        if abs(mult - 1.0) > 0.02:
            direction = "wider" if mult > 1 else "narrower"
            hints.append({
                "type": "dimension",
                "field": field,
                "adjustment": f"{direction} by {abs(mult - 1) * 100:.0f}%",
                "confidence": model.confidence,
            })

    for component, material in model.material_overrides.items():
        hints.append({
            "type": "material",
            "component": component,
            "preferred": material,
            "confidence": model.confidence,
        })

    for component, visible in model.component_visibility.items():
        hints.append({
            "type": "visibility",
            "component": component,
            "preferred": "visible" if visible else "hidden",
            "confidence": model.confidence,
        })

    if model.furniture_type_weights:
        top_type = max(model.furniture_type_weights, key=model.furniture_type_weights.get)
        hints.append({
            "type": "furniture_type",
            "preferred": top_type,
            "frequency": model.furniture_type_weights[top_type],
            "confidence": model.confidence,
        })

    return hints


# ===== Session Management =====

def get_session_corrections(session_id: str) -> List[Dict]:
    """Retrieve all corrections for a session."""
    path = _get_corrections_path(session_id)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def get_all_users() -> List[str]:
    """List all users with preference models."""
    users = []
    if os.path.exists(PREFERENCES_DIR):
        for f in os.listdir(PREFERENCES_DIR):
            if f.endswith("_preferences.json"):
                users.append(f.replace("_preferences.json", ""))
    return users


# ===== Public API =====

def learn_from_chat(
    session_id: str,
    previous_state: Dict,
    new_state: Dict,
    user_id: str = "default",
) -> List[Correction]:
    """
    Compare chat state before/after and record all corrections.

    Call this after each chat message that changes the drawing state.
    """
    corrections = []
    prev = previous_state or {}
    curr = new_state or {}

    # Detect dimension changes
    prev_dims = prev.get("dimensions", {})
    curr_dims = curr.get("dimensions", {})
    for key in set(list(prev_dims.keys()) + list(curr_dims.keys())):
        old = prev_dims.get(key)
        new = curr_dims.get(key)
        if old != new and new is not None:
            corrections.append(record_correction(
                session_id, key, old, new,
                context={"furniture_type": curr.get("furniture_type")},
                user_id=user_id,
            ))

    # Detect material changes
    prev_mats = prev.get("materials", {})
    curr_mats = curr.get("materials", {})
    for key in set(list(prev_mats.keys()) + list(curr_mats.keys())):
        old = prev_mats.get(key)
        new = curr_mats.get(key)
        if old != new and new is not None:
            corrections.append(record_correction(
                session_id, f"material_{key}", old, new,
                context={"furniture_type": curr.get("furniture_type")},
                user_id=user_id,
            ))

    # Detect visibility changes
    prev_vis = prev.get("visibility", {})
    curr_vis = curr.get("visibility", {})
    for key in set(list(prev_vis.keys()) + list(curr_vis.keys())):
        old = prev_vis.get(key)
        new = curr_vis.get(key)
        if old != new and new is not None:
            corrections.append(record_correction(
                session_id, f"visibility_{key}", old, new,
                context={"furniture_type": curr.get("furniture_type")},
                user_id=user_id,
            ))

    # Detect furniture type changes
    if prev.get("furniture_type") != curr.get("furniture_type") and curr.get("furniture_type"):
        corrections.append(record_correction(
            session_id, "furniture_type",
            prev.get("furniture_type"), curr.get("furniture_type"),
            user_id=user_id,
        ))

    return corrections
