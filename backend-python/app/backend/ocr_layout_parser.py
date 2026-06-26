"""
OCR Layout Parser — enhanced OCR with text box positions, orientation, units, symbols.

Strategy:
1. Use pytesseract.image_to_data() to get per-word bounding boxes + confidence
2. Classify each text region by content pattern
3. Detect special CAD symbols (├ÿ, %%c, DIA, etc.)
4. Return structured data linking text ÔåÆ position ÔåÆ type

This is the foundation for dimension association — knowing WHERE text is
on the drawing enables matching it to the geometry it describes.
"""

import re
import os
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Literal
from PIL import Image
import pytesseract

# Tesseract path setup (same as ocr.py)
for tp in [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
           r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
    if os.path.exists(tp):
        pytesseract.pytesseract.tesseract_cmd = tp
        break

# ===== Data Types =====

TextType = Literal[
    "DIMENSION_LABEL",   # Numeric value with units (e.g. "80 cm", "├ÿ40")
    "MATERIAL_NOTE",     # Material or finish description
    "TITLE_BLOCK",       # Title, scale, revision info
    "CENTERLINE_MARK",   # "CL", "C", center marks
    "LEADER_TEXT",       # Callout text with arrow leader
    "LABEL",             # Component label (e.g. "TABLE TOP")
    "NOTE",              # General note
    "UNKNOWN"
]


@dataclass
class TextBox:
    """A single text region detected by OCR with its position."""
    text: str
    x: int              # Left edge of bounding box
    y: int              # Top edge of bounding box
    w: int              # Width of bounding box
    h: int              # Height of bounding box
    confidence: float   # OCR confidence (0-100)
    text_type: TextType = "UNKNOWN"
    value_cm: Optional[float] = None
    unit: str = ""
    is_diameter: bool = False
    symbol: str = ""    # "├ÿ", "%%c", "DIA", etc.
    orientation: float = 0.0  # degrees, 0 = horizontal

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    @property
    def area(self) -> int:
        return self.w * self.h

    def contains_point(self, px: float, py: float, margin: int = 5) -> bool:
        """Check if a point falls within this text box (with margin)."""
        return (self.x - margin <= px <= self.x + self.w + margin and
                self.y - margin <= py <= self.y + self.h + margin)

    def distance_to_point(self, px: float, py: float) -> float:
        """Distance from point to nearest edge of this text box."""
        dx = max(self.x - px, 0, px - (self.x + self.w))
        dy = max(self.y - py, 0, py - (self.y + self.h))
        return math.sqrt(dx * dx + dy * dy)

    def overlaps_horizontally(self, other: "TextBox", margin: int = 10) -> bool:
        """Check if this box horizontally overlaps with another."""
        return (self.x - margin < other.x + other.w + margin and
                self.x + self.w + margin > other.x - margin)

    def overlaps_vertically(self, other: "TextBox", margin: int = 10) -> bool:
        """Check if this box vertically overlaps with another."""
        return (self.y - margin < other.y + other.h + margin and
                self.y + self.h + margin > other.y - margin)


@dataclass
class LayoutParseResult:
    """Complete OCR layout parsing result."""
    text_boxes: List[TextBox]
    dimension_labels: List[TextBox]   # Shortcut: numeric dimensions
    material_notes: List[TextBox]     # Shortcut: material callouts
    title_blocks: List[TextBox]       # Shortcut: title block text
    center_marks: List[TextBox]       # Shortcut: centerline labels
    raw_text: str
    image_width: int
    image_height: int

    def to_dict(self) -> dict:
        return {
            "text_boxes": [
                {"text": t.text, "x": t.x, "y": t.y, "w": t.w, "h": t.h,
                 "confidence": round(t.confidence, 2), "type": t.text_type,
                 "value_cm": t.value_cm, "unit": t.unit,
                 "is_diameter": t.is_diameter, "symbol": t.symbol}
                for t in self.text_boxes
            ],
            "dimension_labels": [
                {"text": t.text, "x": t.x, "y": t.y, "value_cm": t.value_cm,
                 "is_diameter": t.is_diameter}
                for t in self.dimension_labels
            ],
            "material_notes": [{"text": t.text, "x": t.x, "y": t.y} for t in self.material_notes],
            "raw_text_length": len(self.raw_text),
            "image_size": {"width": self.image_width, "height": self.image_height},
        }


# ===== Unit Conversion =====

UNIT_PATTERNS = {
    "cm": re.compile(r'(\d+(?:\.\d+)?)\s*cm\b', re.I),
    "mm": re.compile(r'(\d+(?:\.\d+)?)\s*mm\b', re.I),
    "m":  re.compile(r'(\d+(?:\.\d+)?)\s*m\b(?!m)', re.I),
    "in": re.compile(r'(\d+(?:\.\d+)?)\s*(?:in|inch|")', re.I),
    "ft": re.compile(r'(\d+(?:\.\d+)?)\s*(?:ft|foot|\')', re.I),
}

SYMBOL_PATTERNS = {
    "diameter": re.compile(r'[├ÿ├©%%c]|\bDIA\b|DIAMETER', re.I),
    "radius":   re.compile(r'\b[Rr]\s*=?\s*\d+'),
    "height":   re.compile(r'\b[Hh]\s*=?\s*\d+'),
    "width":    re.compile(r'\b[Ww]\s*=?\s*\d+'),
    "depth":    re.compile(r'\b[Dd]\s*=?\s*\d+(?!\w*(?:IA|IAMETER))'),  # not DIA/DIAMETER
}

# ===== Text Classification Patterns =====

DIMENSION_PATTERN = re.compile(
    r'^[├ÿ├©%%c]?\s*\d+(?:\.\d+)?\s*(?:cm|mm|m|in|ft|")?\s*$|'
    r'^\d+(?:\.\d+)?\s*(?:cm|mm|m)\s*(?:DIA|diameter|W|H|D|L)?\s*$|'
    r'^(?:W|H|D|L|DIA|├ÿ)\s*=\s*\d+(?:\.\d+)?', re.I
)

CENTERLINE_PATTERN = re.compile(
    r'^(?:CL|C\.L|CL\s|CENTER|CENTRE|AXIS|C/L)\s*$', re.I
)

TITLE_BLOCK_KEYWORDS = [
    "scale", "revision", "project", "client", "designer",
    "date", "drawn", "approved", "material", "finish",
    "tolerance", "all dimensions", "do not scale",
]

MATERIAL_KEYWORDS = [
    "wood", "metal", "steel", "brass", "copper", "aluminum",
    "glass", "marble", "stone", "concrete",
    "leather", "fabric", "upholstery", "foam",
    "veneer", "laminate", "mdf", "plywood", "particle board",
    "solid", "oak", "maple", "walnut", "cherry", "mahogany",
    "paint", "coating", "finish", "stain", "varnish",
    "powder coat", "anodized", "brushed", "polished", "matte",
    "black", "white", "chrome", "nickel", "brass", "bronze",
    "textured", "hammered", "smooth", "grain",
    "stainless", "carbon steel", "cast iron",
]


def _convert_to_cm(value: float, unit: str) -> float:
    """Convert value to cm."""
    conversions = {"mm": 0.1, "cm": 1.0, "m": 100.0, "in": 2.54, "ft": 30.48}
    return value * conversions.get(unit, 1.0)


def _determine_text_type(text: str, is_numeric: bool, has_unit: bool) -> TextType:
    """Classify text based on content patterns."""
    text_clean = text.strip()

    # Centerline marks
    if CENTERLINE_PATTERN.match(text_clean):
        return "CENTERLINE_MARK"

    # Pure dimension labels (numbers with or without units)
    if is_numeric and (has_unit or DIMENSION_PATTERN.match(text_clean)):
        return "DIMENSION_LABEL"

    # Title block content
    text_lower = text.lower()
    if any(kw in text_lower for kw in TITLE_BLOCK_KEYWORDS):
        return "TITLE_BLOCK"

    # Material descriptions
    if any(kw in text_lower for kw in MATERIAL_KEYWORDS):
        return "MATERIAL_NOTE"

    # Short labels (likely component names)
    if len(text_clean.split()) <= 3 and len(text_clean) < 30:
        return "LABEL"

    if is_numeric:
        return "DIMENSION_LABEL"

    return "NOTE"


def _merge_adjacent_text_boxes(boxes: List[TextBox],
                                x_gap: int = 15,
                                y_gap: int = 8) -> List[TextBox]:
    """
    Merge text boxes that are close together (same line of text split by OCR).
    This happens when Tesseract breaks "80 cm DIA" into ["80", "cm", "DIA"].
    """
    if not boxes:
        return []

    # Sort by y then x
    sorted_boxes = sorted(boxes, key=lambda b: (b.y, b.x))
    merged: List[TextBox] = []

    current = sorted_boxes[0]
    for next_box in sorted_boxes[1:]:
        # Check if same line (y overlap) and close horizontally
        if (current.overlaps_vertically(next_box, y_gap) and
                abs((current.x + current.w) - next_box.x) < x_gap):

            # Merge: combine text, expand bounding box
            combined_text = current.text + " " + next_box.text
            new_x = min(current.x, next_box.x)
            new_y = min(current.y, next_box.y)
            new_w = max(current.x + current.w, next_box.x + next_box.w) - new_x
            new_h = max(current.y + current.h, next_box.y + next_box.h) - new_y
            new_conf = max(current.confidence, next_box.confidence)

            # Re-derive type from merged text
            is_numeric = bool(re.search(r'\d+', combined_text))
            has_unit = bool(re.search(r'(?:cm|mm|m|in|ft)', combined_text, re.I))
            text_type = _determine_text_type(combined_text, is_numeric, has_unit)

            current = TextBox(
                text=combined_text, x=new_x, y=new_y, w=new_w, h=new_h,
                confidence=new_conf, text_type=text_type,
                is_diameter=bool(SYMBOL_PATTERNS["diameter"].search(combined_text)),
            )
        else:
            merged.append(current)
            current = next_box
    merged.append(current)
    return merged


def parse_ocr_layout(image_path: str) -> LayoutParseResult:
    """
    Parse OCR layout from an image: extract text boxes with positions, classification.

    Uses pytesseract.image_to_data() for per-word bounding boxes.
    Falls back to simple text-only if Tesseract data output fails.

    Args:
        image_path: Path to the image file

    Returns:
        LayoutParseResult with structured text box data
    """
    img = Image.open(image_path)
    width, height = img.size

    # Get detailed OCR data with positions
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as e:
        # Fallback: basic text only
        text = pytesseract.image_to_string(img)
        return LayoutParseResult(
            text_boxes=[TextBox(text=text, x=0, y=0, w=width, h=height,
                                confidence=50.0, text_type="NOTE")],
            dimension_labels=[], material_notes=[], title_blocks=[],
            center_marks=[], raw_text=text,
            image_width=width, image_height=height,
        )

    raw_boxes: List[TextBox] = []
    n = len(data.get("text", []))

    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue

        try:
            conf = int(data["conf"][i]) / 100.0 if data["conf"][i] != "-1" else 0.1
        except (ValueError, IndexError):
            conf = 0.1

        x = int(data["left"][i])
        y = int(data["top"][i])
        w = int(data["width"][i])
        h = int(data["height"][i])

        if w <= 0 or h <= 0:
            continue

        # Parse value and symbol
        value_cm = None
        unit = ""
        is_diameter = bool(SYMBOL_PATTERNS["diameter"].search(text))
        symbol = ""
        if is_diameter:
            symbol = "├ÿ"

        # Try to extract numeric value
        for unit_name, pattern in UNIT_PATTERNS.items():
            m = pattern.search(text)
            if m:
                value_cm = _convert_to_cm(float(m.group(1)), unit_name)
                unit = unit_name
                break

        if value_cm is None:
            # Try plain number
            m = re.search(r'(\d+(?:\.\d+)?)', text)
            if m:
                value_cm = float(m.group(1))
                # Assume cm if no unit specified (common in CAD)
                unit = "cm"

        # Determine text type
        is_numeric = value_cm is not None
        has_unit = bool(unit)
        text_type = _determine_text_type(text, is_numeric, has_unit)

        tb = TextBox(
            text=text, x=x, y=y, w=w, h=h,
            confidence=conf,
            text_type=text_type,
            value_cm=value_cm,
            unit=unit,
            is_diameter=is_diameter,
            symbol=symbol,
        )
        raw_boxes.append(tb)

    # Merge adjacent text boxes on same line
    text_boxes = _merge_adjacent_text_boxes(raw_boxes)

    # Categorize
    dimension_labels = [t for t in text_boxes if t.text_type == "DIMENSION_LABEL"]
    material_notes = [t for t in text_boxes if t.text_type == "MATERIAL_NOTE"]
    title_blocks = [t for t in text_boxes if t.text_type == "TITLE_BLOCK"]
    center_marks = [t for t in text_boxes if t.text_type == "CENTERLINE_MARK"]

    raw_text = "\n".join(t.text for t in text_boxes)

    return LayoutParseResult(
        text_boxes=text_boxes,
        dimension_labels=dimension_labels,
        material_notes=material_notes,
        title_blocks=title_blocks,
        center_marks=center_marks,
        raw_text=raw_text,
        image_width=width,
        image_height=height,
    )


def get_dimension_labels(image_path: str) -> List[TextBox]:
    """Quick access: get only dimension labels from an image."""
    result = parse_ocr_layout(image_path)
    return result.dimension_labels


# Public API
def extract_layout(image_path: str) -> LayoutParseResult:
    """Main entry point: extract structured OCR layout from a drawing image."""
    return parse_ocr_layout(image_path)
