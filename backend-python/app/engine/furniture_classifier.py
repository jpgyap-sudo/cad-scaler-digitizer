"""
Furniture Classifier: Identify furniture type from OCR text + detected primitives.
Uses keyword matching and geometric heuristics.
"""
from typing import List, Dict, Tuple, Any

def classify_furniture(
    ocr_lines: List[str],
    circles: List[Tuple[float, float, float]],
    lines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    rects: List[Tuple[float, float, float, float]] = None
) -> Dict[str, Any]:
    """
    Classify furniture type from detected features.
    
    Returns:
    {
        "type": str,
        "confidence": float,
        "required_dimensions": List[str],
        "missing_dimensions": List[str],
        "recommended_template": str
    }
    """
    text = " ".join(ocr_lines).lower()
    has_dia = any("dia" in t.lower() or "diameter" in t.lower() for t in ocr_lines)
    has_round = any("round" in t.lower() or "circular" in t.lower() for t in ocr_lines)
    has_rectangular = any("rect" in t.lower() or "square" in t.lower() for t in ocr_lines)
    has_table = "table" in text
    has_sofa = any(s in text for s in ["sofa", "couch", "loveseat", "settee"])
    has_cabinet = any(s in text for s in ["cabinet", "wardrobe", "closet", "drawer", "shelf"])
    has_bed = any(s in text for s in ["bed", "headboard", "mattress", "frame"])
    has_chair = any(s in text for s in ["chair", "stool", "seat", "armchair"])

    rects = rects or []
    
    # Round pedestal table: circles + DIA/text hints
    if circles and (has_dia or has_round or has_table):
        return {
            "type": "round_pedestal_table",
            "confidence": 0.85 if has_table else 0.75,
            "required_dimensions": ["top_diameter_cm", "overall_height_cm"],
            "missing_dimensions": [],
            "recommended_template": "resources/furniture_templates/round_pedestal_table.json"
        }
    
    # Rectangular table: rectangles + table hint
    if len(rects) >= 1 and (has_table or has_rectangular):
        return {
            "type": "rectangular_table",
            "confidence": 0.80 if has_table else 0.60,
            "required_dimensions": ["width_cm", "depth_cm", "height_cm"],
            "missing_dimensions": [],
            "recommended_template": "resources/furniture_templates/rectangular_table.json"
        }
    
    # Sofa: specific text hints or wide rectangle + legs pattern
    if has_sofa or (len(rects) >= 2 and "seat" in text):
        return {
            "type": "sofa",
            "confidence": 0.85 if has_sofa else 0.50,
            "required_dimensions": ["width_cm", "depth_cm", "height_cm", "seat_height_cm"],
            "missing_dimensions": [],
            "recommended_template": "resources/furniture_templates/sofa.json"
        }
    
    # Cabinet: tall rectangle with door/shelf hints
    if has_cabinet or (len(rects) >= 1 and "door" in text):
        return {
            "type": "cabinet",
            "confidence": 0.80 if has_cabinet else 0.50,
            "required_dimensions": ["width_cm", "depth_cm", "height_cm"],
            "missing_dimensions": [],
            "recommended_template": "resources/furniture_templates/cabinet.json"
        }
    
    # Bed / Headboard: wide rectangle
    if has_bed:
        return {
            "type": "bed_headboard",
            "confidence": 0.85,
            "required_dimensions": ["width_cm", "height_cm", "thickness_cm"],
            "missing_dimensions": [],
            "recommended_template": "resources/furniture_templates/bed_headboard.json"
        }
    
    # Chair: chair text or small rectangle + seat/back
    if has_chair or (len(rects) >= 2 and len(lines) >= 6):
        return {
            "type": "chair",
            "confidence": 0.80 if has_chair else 0.40,
            "required_dimensions": ["seat_width_cm", "seat_depth_cm", "seat_height_cm", "back_height_cm"],
            "missing_dimensions": [],
            "recommended_template": "resources/furniture_templates/chair.json"
        }
    
    # If circles detected but no match
    if circles:
        return {
            "type": "round_table_or_circular_part",
            "confidence": 0.50,
            "required_dimensions": ["diameter_cm"],
            "missing_dimensions": [],
            "recommended_template": "resources/furniture_templates/round_pedestal_table.json"
        }
    
    # Generic fallback
    return {
        "type": "generic_2d_furniture",
        "confidence": 0.30,
        "required_dimensions": ["width_cm", "height_cm"],
        "missing_dimensions": [],
        "recommended_template": ""
    }
