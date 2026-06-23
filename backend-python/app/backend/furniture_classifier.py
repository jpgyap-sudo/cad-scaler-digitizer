"""
Module: furniture_classifier.py
Identify furniture type from OCR text + detected primitives.
"""
from typing import List, Tuple, Any


def classify_furniture(ocr_lines: list, circles: list, lines: list, rects: list = None) -> dict:
    """Classify furniture type from features with confidence scoring."""
    text = " ".join(ocr_lines).lower()
    rects = rects or []

    has_dia = any("dia" in t.lower() or "diameter" in t.lower() for t in ocr_lines)
    has_round = any(s in text for s in ["round", "circular", "pedestal"])
    has_table = "table" in text
    has_rect = any(s in text for s in ["rect", "square"])
    has_sofa = any(s in text for s in ["sofa", "couch", "loveseat", "settee"])
    has_cabinet = any(s in text for s in ["cabinet", "wardrobe", "closet", "drawer", "shelf"])
    has_bed = any(s in text for s in ["bed", "headboard", "mattress", "frame"])
    has_chair = any(s in text for s in ["chair", "stool", "seat", "armchair"])

    # Round pedestal table
    if circles and (has_dia or has_round or has_table):
        return {"type": "round_pedestal_table", "confidence": 0.85 if has_table else 0.75,
                "required_dimensions": ["top_diameter_cm", "overall_height_cm"],
                "recommended_template": "round_pedestal_table"}

    # Rectangular table
    if len(rects) >= 1 and (has_table or has_rect):
        return {"type": "rectangular_table", "confidence": 0.80 if has_table else 0.60,
                "required_dimensions": ["width_cm", "depth_cm", "height_cm"],
                "recommended_template": "rectangular_table"}

    # Sofa
    if has_sofa or (len(rects) >= 2 and "seat" in text):
        return {"type": "sofa", "confidence": 0.85 if has_sofa else 0.50,
                "required_dimensions": ["width_cm", "depth_cm", "height_cm", "seat_height_cm"],
                "recommended_template": "sofa"}

    # Cabinet
    if has_cabinet or (len(rects) >= 1 and "door" in text):
        return {"type": "cabinet", "confidence": 0.80 if has_cabinet else 0.50,
                "required_dimensions": ["width_cm", "depth_cm", "height_cm"],
                "recommended_template": "cabinet"}

    # Bed/headboard
    if has_bed:
        return {"type": "bed_headboard", "confidence": 0.85,
                "required_dimensions": ["width_cm", "height_cm", "thickness_cm"],
                "recommended_template": "bed_headboard"}

    # Chair
    if has_chair or (len(rects) >= 2 and len(lines) >= 6):
        return {"type": "chair", "confidence": 0.80 if has_chair else 0.40,
                "required_dimensions": ["seat_width_cm", "seat_depth_cm", "seat_height_cm", "back_height_cm"],
                "recommended_template": "chair"}

    # Generic fallback
    if circles:
        return {"type": "round_table_or_circular_part", "confidence": 0.50,
                "required_dimensions": ["diameter_cm"],
                "recommended_template": "round_pedestal_table"}

    return {"type": "generic_2d_furniture", "confidence": 0.30,
            "required_dimensions": ["width_cm", "height_cm"],
            "recommended_template": ""}
