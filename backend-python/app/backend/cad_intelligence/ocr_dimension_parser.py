from __future__ import annotations
import re
from typing import Iterable
from .models import OCRItem, OCRDimension

NUMBER_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)")
DIAMETER_TOKENS = ["dia", "diam", "diameter", "ø", "⌀", "phi"]
MM_TOKENS = ["mm", "millimeter", "millimetre"]
CM_TOKENS = ["cm", "centimeter", "centimetre"]

def normalize_text(text: str) -> str:
    return text.lower().replace("Ø", "ø").replace("⌀", "ø").replace("×", "x").strip()

def infer_kind(text: str) -> str:
    t = normalize_text(text)
    if any(token in t for token in DIAMETER_TOKENS):
        return "diameter"
    if re.search(r"(^|\s)r\s*\d", t) or "radius" in t:
        return "radius"
    if re.search(r"(^|\s)w($|\s|:)", t) or "width" in t:
        return "width"
    if re.search(r"(^|\s)h($|\s|:)", t) or "height" in t:
        return "height"
    return "length"

def infer_unit(text: str, default_unit: str = "mm") -> str:
    t = " " + normalize_text(text) + " "
    if any(token in t for token in MM_TOKENS):
        return "mm"
    if any(token in t for token in CM_TOKENS):
        return "cm"
    if " m " in t or "meter" in t or "metre" in t:
        return "m"
    return default_unit

def to_mm(value: float, unit: str) -> float:
    if unit == "mm":
        return value
    if unit == "cm":
        return value * 10
    if unit == "m":
        return value * 1000
    return value

def parse_ocr_dimensions(
    ocr_items: Iterable[OCRItem | dict],
    default_unit: str = "mm",
    min_confidence: float = 0.3,
) -> list[OCRDimension]:
    dimensions: list[OCRDimension] = []
    for item in ocr_items:
        if isinstance(item, dict):
            text = str(item.get("text", ""))
            bbox = tuple(item.get("bbox", [0, 0, 0, 0]))
            confidence = float(item.get("confidence", 1.0))
        else:
            text = item.text
            bbox = item.bbox
            confidence = item.confidence
        if confidence < min_confidence:
            continue
        match = NUMBER_RE.search(normalize_text(text))
        if not match:
            continue
        value = float(match.group("value"))
        unit = infer_unit(text, default_unit=default_unit)
        value_mm = to_mm(value, unit)
        if value_mm <= 0:
            continue
        dimensions.append(OCRDimension(
            raw_text=text,
            value=value,
            unit=unit,
            value_mm=value_mm,
            kind=infer_kind(text),
            bbox=bbox, # type: ignore
            confidence=confidence,
        ))
    return dimensions
