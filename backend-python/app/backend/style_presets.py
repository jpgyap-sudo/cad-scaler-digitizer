"""
Style Presets — save/load furniture drawing preferences as named presets.

Inspired by Scan2CAD's "conversion settings" pattern.
Combined with Echo Drafter's learned preferences.

Users save their preferred materials, dimensions, finishes, and component
visibility as named presets. On next upload, select a preset to pre-apply
everything without chatting or adjusting sliders.

Presets stored as JSON files in memory/user_preferences/presets/.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

PRESETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "memory", "user_preferences", "presets")
os.makedirs(PRESETS_DIR, exist_ok=True)


@dataclass
class StylePreset:
    """A named furniture drawing style preset."""
    name: str                                    # e.g. "Modern Round Table"
    furniture_type: str = "round_pedestal_table"  # default furniture type
    materials: Dict[str, str] = field(default_factory=dict)  # component -> material
    dimensions: Dict[str, float] = field(default_factory=dict)  # component -> cm
    visibility: Dict[str, bool] = field(default_factory=dict)   # component -> shown
    notes: List[str] = field(default_factory=list)
    finish_notes: List[str] = field(default_factory=list)      # finish specifications
    created: str = ""
    updated: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "furniture_type": self.furniture_type,
            "materials": self.materials,
            "dimensions": self.dimensions,
            "visibility": self.visibility,
            "notes": self.notes,
            "finish_notes": self.finish_notes,
            "created": self.created,
            "updated": self.updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StylePreset":
        return cls(
            name=data.get("name", "Untitled"),
            furniture_type=data.get("furniture_type", "round_pedestal_table"),
            materials=data.get("materials", {}),
            dimensions=data.get("dimensions", {}),
            visibility=data.get("visibility", {}),
            notes=data.get("notes", []),
            finish_notes=data.get("finish_notes", []),
            created=data.get("created", ""),
            updated=data.get("updated", ""),
        )


def _safe_name(name: str) -> str:
    """Sanitize preset name for filesystem."""
    return name.replace("/", "_").replace("\\", "_").replace("..", "_").replace(" ", "_")[:60]


def save_preset(preset: StylePreset) -> str:
    """Save a style preset. Returns the filename."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    if not preset.created:
        preset.created = now
    preset.updated = now

    fname = f"{_safe_name(preset.name)}.json"
    path = os.path.join(PRESETS_DIR, fname)
    with open(path, 'w') as f:
        json.dump(preset.to_dict(), f, indent=2)
    return fname


def load_preset(name: str) -> Optional[StylePreset]:
    """Load a named style preset."""
    fname = f"{_safe_name(name)}.json"
    path = os.path.join(PRESETS_DIR, fname)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return StylePreset.from_dict(json.load(f))
        except Exception:
            pass
    return None


def list_presets() -> List[StylePreset]:
    """List all saved style presets."""
    presets = []
    if os.path.exists(PRESETS_DIR):
        for f in sorted(os.listdir(PRESETS_DIR)):
            if f.endswith(".json"):
                p = load_preset(f.replace(".json", ""))
                if p:
                    presets.append(p)
    return presets


def delete_preset(name: str) -> bool:
    """Delete a style preset by name."""
    fname = f"{_safe_name(name)}.json"
    path = os.path.join(PRESETS_DIR, fname)
    if os.path.exists(path):
        os.unlink(path)
        return True
    return False


def preset_from_chat_state(state: dict, name: str) -> StylePreset:
    """Create a StylePreset from a chat DrawingState."""
    return StylePreset(
        name=name,
        furniture_type=state.get("furniture_type", "round_pedestal_table"),
        materials=dict(state.get("materials", {})),
        dimensions=dict(state.get("dimensions", {})),
        visibility=dict(state.get("visibility", {})),
        notes=list(state.get("notes", [])),
        finish_notes=[n for n in state.get("notes", []) if "finish" in n.lower() or "coat" in n.lower()],
    )


def preset_from_echo_drafter(user_id: str, name: str) -> Optional[StylePreset]:
    """Create a StylePreset from Echo Drafter learned preferences."""
    try:
        from app.backend.feedback_learner import load_preferences
        model = load_preferences(user_id)
        if model.correction_count < 3:
            return None  # Not enough data

        dims = {}
        for field, mult in model.dimension_multipliers.items():
            # Store the multiplier as a learned dimension hint
            dims[f"{field}_multiplier"] = round(mult, 3)

        return StylePreset(
            name=name,
            furniture_type=max(model.furniture_type_weights, key=model.furniture_type_weights.get)
                if model.furniture_type_weights else "round_pedestal_table",
            materials=dict(model.material_overrides),
            dimensions=dims,
            visibility=dict(model.component_visibility),
        )
    except Exception:
        return None


def apply_preset_to_template(preset: StylePreset) -> dict:
    """Convert a StylePreset to template parameters for DXF generation."""
    params = {
        "furniture_type": preset.furniture_type,
        "material_notes": [],
    }

    # Material notes
    for comp, mat in preset.materials.items():
        params["material_notes"].append(f"{comp.upper()} — {mat}")

    # Finish notes
    params["material_notes"].extend(preset.finish_notes)

    # Dimension overrides (real cm values, not multipliers)
    for key, val in preset.dimensions.items():
        if not key.endswith("_multiplier") and val > 0:
            params[key] = val

    return params
