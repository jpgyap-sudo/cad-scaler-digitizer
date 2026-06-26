"""
Anti-Hallucination Validator — enforce VISIBLE/ESTIMATED/UNKNOWN rules
at the PER-ENTITY level (not just per-component).

Upgraded from component-level validation to per-DXF-entity validation:
  Every DXF entity (line, circle, polygon, text, dimension) carries:
  - source: "measured_from_pixels | ocr_confirmed | user_confirmed |
             ratio_estimated | default_template"
  - confidence: 0.0-1.0
  - evidence: ["ocr_box_id:12", "line_id:45", "scale_factor:0.5"]

Visibility rules:
  VISIBLE   (confidence >= 0.70) -> draw SOLID on OBJECT layer
  ESTIMATED (0.30 <= confidence < 0.70) -> draw DASHED/HIDDEN, label as "EST."
  UNKNOWN   (confidence < 0.30) -> DO NOT DRAW

Backward-compatible: accepts old Dict[str, float] format and converts automatically.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Any

Visibility = Literal["VISIBLE", "ESTIMATED", "UNKNOWN"]


@dataclass
class EntityVerdict:
    """Rendering decision for a single DXF entity."""
    entity_id: str
    entity_type: str               # "line", "circle", "polygon", "text", "dimension"
    name: str                      # Human-readable component name
    confidence: float              # 0.0 - 1.0
    source: str                    # "measured", "ocr_confirmed", "user_confirmed", "ratio", "default"
    visibility: Visibility
    layer: str                     # DXF layer to use
    linetype: str                  # CONTINUOUS, HIDDEN, DASHED
    action: str                    # "draw_solid", "draw_dashed", "draw_with_note", "skip"
    note: str = ""                 # Annotation if estimated
    evidence: List[str] = field(default_factory=list)  # E.g. ["ocr_box:12", "line:34"]

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "confidence": round(self.confidence, 2),
            "source": self.source,
            "visibility": self.visibility,
            "layer": self.layer,
            "linetype": self.linetype,
            "action": self.action,
            "note": self.note,
            "evidence": self.evidence[:3],
        }


@dataclass
class ValidationResult:
    """Complete validation pass over all entities in a drawing."""
    furniture_type: str
    entity_verdicts: Dict[str, EntityVerdict]
    rejected_entities: List[str]      # Entity IDs skipped
    estimated_entities: List[str]     # Entity IDs drawn dashed
    visible_entities: List[str]       # Entity IDs drawn solid
    summary: str = ""

    @property
    def components(self):
        """Backward-compatible access for old callers (dxf_exporter).
        Maps entity_verdicts -> old callers iterate vr.components[name].visibility."""
        return self.entity_verdicts

    def to_dict(self) -> dict:
        return {
            "furniture_type": self.furniture_type,
            "entity_verdicts": {k: v.to_dict() for k, v in self.entity_verdicts.items()},
            "rejected_entities": self.rejected_entities,
            "estimated_entities": self.estimated_entities,
            "visible_entities": self.visible_entities,
            "rejected_count": len(self.rejected_entities),
            "estimated_count": len(self.estimated_entities),
            "visible_count": len(self.visible_entities),
            "summary": self.summary,
        }

    def is_entity_visible(self, entity_id: str) -> bool:
        """Check if a specific entity should be drawn."""
        verdict = self.entity_verdicts.get(entity_id)
        if not verdict:
            return True  # Default to visible if not validated
        return verdict.visibility != "UNKNOWN"

    def is_entity_estimated(self, entity_id: str) -> bool:
        """Check if a specific entity is estimated (dashed)."""
        verdict = self.entity_verdicts.get(entity_id)
        if not verdict:
            return False
        return verdict.visibility == "ESTIMATED"

    def get_source(self, entity_id: str) -> str:
        """Get source metadata for a DXF entity."""
        verdict = self.entity_verdicts.get(entity_id)
        return verdict.source if verdict else "unknown"


# ===== Confidence thresholds =====
VISIBLE_THRESHOLD = 0.70    # >= 0.70: draw solid
ESTIMATED_THRESHOLD = 0.30  # >= 0.30: draw dashed/labeled
# < 0.30: UNKNOWN, skip entirely


def classify_visibility(confidence: float) -> Visibility:
    """Map confidence score to visibility class."""
    if confidence >= VISIBLE_THRESHOLD:
        return "VISIBLE"
    elif confidence >= ESTIMATED_THRESHOLD:
        return "ESTIMATED"
    else:
        return "UNKNOWN"


def layer_for_entity(entity_type: str, visibility: Visibility, name: str) -> str:
    """Choose the correct DXF layer based on entity type and visibility."""
    if visibility == "UNKNOWN":
        return "HIDDEN"
    name_lower = name.lower()
    type_lower = entity_type.lower()
    if "dimension" in type_lower or "dim" in name_lower:
        return "DIMENSION"
    if "leader" in type_lower or name_lower in ("leader", "callout"):
        return "LEADER"
    if "center" in type_lower or "axis" in name_lower:
        return "CENTER"
    if "hatch" in type_lower or "texture" in name_lower:
        return "HATCH"
    if "text" in type_lower or "label" in name_lower:
        return "MTEXT"
    if "title" in name_lower or "border" in name_lower:
        return "TITLE"
    return "OBJECT"


def linetype_for_visibility(visibility: Visibility) -> str:
    if visibility == "VISIBLE":
        return "CONTINUOUS"
    elif visibility == "ESTIMATED":
        return "HIDDEN"
    else:
        return "HIDDEN"


def action_for_visibility(visibility: Visibility) -> str:
    if visibility == "VISIBLE":
        return "draw_solid"
    elif visibility == "ESTIMATED":
        return "draw_dashed"
    else:
        return "skip"


def validate_entities(
    furniture_type: str,
    entity_confidences: Dict[str, Dict[str, Any]],
    known_visible_entities: Optional[List[str]] = None,
) -> ValidationResult:
    """
    Validate all entities against anti-hallucination rules.

    Args:
        furniture_type: canonical type (e.g. 'round_pedestal_table')
        entity_confidences: {entity_id: {"confidence": float, "source": str,
                                          "entity_type": str, "name": str,
                                          "evidence": List[str]}}
        known_visible_entities: list of entity IDs confirmed by user

    Returns:
        ValidationResult with rendering decisions for each entity
    """
    visible_set = set(known_visible_entities or [])
    entity_verdicts: Dict[str, EntityVerdict] = {}
    rejected_entities: List[str] = []
    estimated_entities: List[str] = []
    visible_entities: List[str] = []

    for entity_id, meta in entity_confidences.items():
        conf = meta.get("confidence", 0.0)
        source = meta.get("source", "unknown")
        entity_type = meta.get("entity_type", "unknown")
        name = meta.get("name", entity_id)
        evidence = meta.get("evidence", [])

        if entity_id in visible_set:
            conf = max(conf, 0.85)
            source = "user_confirmed"

        visibility = classify_visibility(conf)
        layer = layer_for_entity(entity_type, visibility, name)
        ltype = linetype_for_visibility(visibility)
        action = action_for_visibility(visibility)

        note = ""
        if visibility == "ESTIMATED":
            note = f"ESTIMATED ({source}) — verify against source"
        elif visibility == "UNKNOWN":
            note = f"SKIPPED — not in source (confidence {conf:.2f}, source: {source})"

        verdict = EntityVerdict(
            entity_id=entity_id,
            entity_type=entity_type,
            name=name,
            confidence=conf,
            source=source,
            visibility=visibility,
            layer=layer,
            linetype=ltype,
            action=action,
            note=note,
            evidence=evidence,
        )
        entity_verdicts[entity_id] = verdict

        if visibility == "VISIBLE":
            visible_entities.append(entity_id)
        elif visibility == "ESTIMATED":
            estimated_entities.append(entity_id)
        else:
            rejected_entities.append(entity_id)

    summary = (
        f"{furniture_type}: {len(visible_entities)} visible entities, "
        f"{len(estimated_entities)} estimated, {len(rejected_entities)} rejected"
    )

    return ValidationResult(
        furniture_type=furniture_type,
        entity_verdicts=entity_verdicts,
        rejected_entities=rejected_entities,
        estimated_entities=estimated_entities,
        visible_entities=visible_entities,
        summary=summary,
    )


# Public API

def validate_furniture_drawing(
    furniture_type: str,
    entity_confidences: Optional[Dict[str, Any]] = None,
    known_visible_entities: Optional[List[str]] = None,
) -> ValidationResult:
    """
    Main entry point: validate all entities before CAD generation.
    Accepts NEW format: Dict[str, Dict] with confidence/source/evidence.
    Also accepts OLD format: Dict[str, float] for backward compatibility.
    """
    if not entity_confidences:
        entity_confidences = {}

    # Backward compatibility: if values are floats (old format), convert
    first_val = next(iter(entity_confidences.values())) if entity_confidences else None
    if isinstance(first_val, (int, float)):
        converted = {}
        for name, conf in entity_confidences.items():
            converted[name] = {
                "confidence": float(conf),
                "source": "ratio_estimated" if float(conf) < 0.7 else "ocr_confirmed",
                "entity_type": "polygon",
                "name": name,
                "evidence": [],
            }
        return validate_entities(furniture_type, converted, known_visible_entities)

    return validate_entities(furniture_type, entity_confidences, known_visible_entities)
