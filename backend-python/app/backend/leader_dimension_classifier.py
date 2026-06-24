"""
Leader vs Dimension Classifier — distinguish annotation types.

Rules:
  DIMENSION = arrows on BOTH ends + numeric value (measurement)
  LEADER    = arrow on ONE end + material/text label (callout)
  CENTERLINE = long-dash-short-dash pattern + passes through center
  NOTE      = text only, no arrow

Prevents the common CAD error where material callouts are drawn
as dimensions and dimensions are mislabeled as leaders.
"""

from dataclasses import dataclass
from typing import List, Optional, Literal

AnnotationType = Literal["DIMENSION", "LEADER", "CENTERLINE", "NOTE"]


@dataclass
class AnnotationClass:
    """Classification result for one annotation entity."""
    text: str
    annotation_type: AnnotationType
    confidence: float
    numeric_value_cm: Optional[float] = None
    is_diameter: bool = False
    material_label: Optional[str] = None


@dataclass
class ClassificationResult:
    """Complete annotation classification for a drawing."""
    dimensions: List[AnnotationClass]   # Measurable sizes
    leaders: List[AnnotationClass]      # Material/label callouts
    centerlines: List[AnnotationClass]  # Center marks
    notes: List[AnnotationClass]        # Plain text

    def to_dict(self) -> dict:
        return {
            "dimensions": [
                {"text": a.text, "value_cm": a.numeric_value_cm, "is_diameter": a.is_diameter}
                for a in self.dimensions
            ],
            "leaders": [
                {"text": a.text, "material": a.material_label}
                for a in self.leaders
            ],
            "centerlines": [a.text for a in self.centerlines],
            "notes": [a.text for a in self.notes],
        }


# ===== Classification keywords =====

# Dimension indicators: these suggest a measurable dimension
DIMENSION_PATTERNS = [
    "cm", "mm", "m",           # Units
    "dia", "diameter", "%%c", "Ø",  # Diameter
    "h=", "w=", "d=",          # Dimension shorthand
    "height", "width", "depth",
    "radius", "r=",
]

# Leader/material indicators: these suggest a material or component label
MATERIAL_PATTERNS = [
    "wood", "metal", "steel", "brass", "copper",
    "glass", "marble", "stone", "concrete",
    "leather", "fabric", "upholstery",
    "veneer", "laminate", "mdf", "plywood",
    "textured", "hammered", "polished", "brushed",
    "finish", "coating", "paint",
    "stainless", "chrome", "black",
]

# Component labels that are leaders, not dimensions
COMPONENT_LABELS = [
    "top", "base", "pedestal", "neck", "column",
    "leg", "seat", "backrest", "armrest",
    "door", "drawer", "shelf", "handle",
    "foot", "ring", "band", "trim",
    "edge", "surface", "panel", "frame",
]

# Centerline indicators
CENTERLINE_PATTERNS = [
    "cl", "center", "centre",
    "axis", "symmetry",
]


def _extract_numeric(text: str) -> Optional[float]:
    """Extract numeric value from dimension text (e.g. '80 cm' -> 80.0)."""
    import re
    # Match patterns like: 80, 80.0, 80cm, Ø80
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:cm|mm|m)?', text.lower())
    if m:
        return float(m.group(1))
    # Match %%c80 pattern (diameter symbol)
    m = re.search(r'%%c(\d+(?:\.\d+)?)', text)
    if m:
        return float(m.group(1))
    return None


def _is_diameter(text: str) -> bool:
    """Check if dimension text indicates a diameter measurement."""
    text_lower = text.lower()
    return any(k in text_lower for k in ["dia", "diameter", "%%c", "ø"])


def _classify_single(text: str) -> AnnotationClass:
    """Classify a single annotation text string."""
    text_lower = text.lower().strip()
    numeric = _extract_numeric(text)
    is_dia = _is_diameter(text)

    # Rule 1: Contains material keywords → LEADER
    mat_matches = [m for m in MATERIAL_PATTERNS if m in text_lower]
    if mat_matches:
        return AnnotationClass(
            text=text,
            annotation_type="LEADER",
            confidence=0.90,
            material_label=mat_matches[0].title(),
        )

    # Rule 2: Contains component label keywords → LEADER
    comp_matches = [c for c in COMPONENT_LABELS if c in text_lower]
    if comp_matches and not numeric:
        return AnnotationClass(
            text=text,
            annotation_type="LEADER",
            confidence=0.75,
            material_label=comp_matches[0].title(),
        )

    # Rule 3: Has numeric value + unit/dimension pattern → DIMENSION
    if numeric:
        dim_matches = [d for d in DIMENSION_PATTERNS if d in text_lower]
        if dim_matches or "cm" in text_lower or "mm" in text_lower:
            return AnnotationClass(
                text=text,
                annotation_type="DIMENSION",
                confidence=0.95 if dim_matches else 0.70,
                numeric_value_cm=numeric,
                is_diameter=is_dia,
            )
        # Numeric but no unit pattern: weak dimension
        return AnnotationClass(
            text=text,
            annotation_type="DIMENSION",
            confidence=0.50,
            numeric_value_cm=numeric,
            is_diameter=is_dia,
        )

    # Rule 4: Contains centerline keywords → CENTERLINE
    if any(c in text_lower for c in CENTERLINE_PATTERNS):
        return AnnotationClass(
            text=text,
            annotation_type="CENTERLINE",
            confidence=0.80,
        )

    # Rule 5: Default → NOTE
    return AnnotationClass(
        text=text,
        annotation_type="NOTE",
        confidence=0.40,
    )


def classify_annotations(
    annotation_texts: List[str],
    ocr_dimensions: Optional[List[dict]] = None,
) -> ClassificationResult:
    """
    Classify all annotation texts in a drawing.

    Args:
        annotation_texts: list of text strings from OCR/AI
        ocr_dimensions: optional pre-parsed dimension dicts [{tag, value_cm}]

    Returns:
        ClassificationResult with categorized annotations
    """
    results = [_classify_single(t) for t in annotation_texts]

    # Merge with OCR dimensions if provided
    if ocr_dimensions:
        for dim in ocr_dimensions:
            tag = dim.get("tag", "")
            value = float(dim.get("value_cm", 0))
            if value > 0:
                results.append(AnnotationClass(
                    text=f"{tag} {value} cm",
                    annotation_type="DIMENSION",
                    confidence=0.90,
                    numeric_value_cm=value,
                    is_diameter="dia" in tag.lower() or "%%c" in tag,
                ))

    return ClassificationResult(
        dimensions=[r for r in results if r.annotation_type == "DIMENSION"],
        leaders=[r for r in results if r.annotation_type == "LEADER"],
        centerlines=[r for r in results if r.annotation_type == "CENTERLINE"],
        notes=[r for r in results if r.annotation_type == "NOTE"],
    )


# Public API
def classify_drawing_annotations(
    ocr_lines: List[str],
    ocr_dimensions: Optional[List[dict]] = None,
) -> ClassificationResult:
    """
    Main entry point: classify all annotations in a furniture drawing.
    """
    return classify_annotations(ocr_lines, ocr_dimensions)
