"""Furniture classifier with type normalization and alias resolution."""


def normalize_furniture_type(ftype: str) -> str:
    """Normalize AI/OCR output to canonical furniture type names.
    Fixes: "round pedestal table", "Round Table", "round_table_or_circular_part"
    """
    s = (ftype or "").lower().strip().replace("-", "_").replace(" ", "_")

    aliases = {
        "round_pedestal_table": "round_pedestal_table",
        "round_table": "round_pedestal_table",
        "round_table_or_circular_part": "round_pedestal_table",
        "circular_table": "round_pedestal_table",
        "pedestal_table": "round_pedestal_table",
        "table_round": "round_pedestal_table",
        "pedestal": "round_pedestal_table",
        "round": "round_pedestal_table",
        "circular": "round_pedestal_table",
        "round_table_with_pedestal_base": "round_pedestal_table",
        "round_dining_table": "round_pedestal_table",
        "rectangular_table": "rectangular_table",
        "rectangle_table": "rectangular_table",
        "rect_table": "rectangular_table",
        "dining_table": "rectangular_table",
        "square_table": "rectangular_table",
        "sofa": "sofa",
        "couch": "sofa",
        "loveseat": "sofa",
        "settee": "sofa",
        "cabinet": "cabinet",
        "storage_cabinet": "cabinet",
        "wardrobe": "wardrobe",
        "closet": "wardrobe",
        "bed_headboard": "bed_headboard",
        "headboard": "bed_headboard",
        "bed": "bed_headboard",
        "chair": "chair",
        "dining_chair": "dining_chair",
        "armchair": "chair",
        "coffee_table": "coffee_table",
        "coffee_table_round": "coffee_table",
        "reception_counter": "reception_counter",
        "counter": "reception_counter",
        "desk": "reception_counter",
    }
    return aliases.get(s, s)


def classify_furniture(ocr_lines: list, circles: list, lines: list, rects: list = None) -> dict:
    """Classify furniture type from features with alias normalization.
    IMPORTANT: Do NOT require circles[] for round table detection — OCR text like
    'Round Table', 'Pedestal', 'DIA', 'Diameter', 'Ø' is sufficient evidence.
    """
    text = " ".join(ocr_lines).lower()
    rects = rects or []

    has_dia = any("dia" in t.lower() or "diameter" in t.lower() or "%%c" in t or "Ø" in t for t in ocr_lines)
    has_round = any(s in text for s in ["round", "circular", "pedestal", "Ø"])
    has_table = "table" in text
    has_rect = any(s in text for s in ["rect", "square"])
    has_sofa = any(s in text for s in ["sofa", "couch", "loveseat", "settee"])
    has_cabinet = any(s in text for s in ["cabinet", "wardrobe", "closet", "drawer", "shelf"])
    has_bed = any(s in text for s in ["bed", "headboard", "mattress"])
    has_chair = any(s in text for s in ["chair", "stool", "seat", "armchair"])

    ftype = "generic_2d_furniture"
    confidence = 0.30

    # Priority 1: Round table (OCR text is stronger evidence than circle detection)
    if (has_dia or has_round or has_table) and ("round" in text or "circular" in text or "pedestal" in text or has_dia):
        ftype, confidence = "round_pedestal_table", 0.85 if has_table else 0.75
    elif circles and (has_round or has_dia):
        ftype, confidence = "round_pedestal_table", 0.75
    # Priority 2: Rectangular table
    elif len(rects) >= 1 and (has_table or has_rect):
        ftype, confidence = "rectangular_table", 0.80 if has_table else 0.60
    # Priority 3: Sofa
    elif has_sofa or (len(rects) >= 2 and "seat" in text):
        ftype, confidence = "sofa", 0.85 if has_sofa else 0.50
    # Priority 4: Cabinet
    elif has_cabinet or (len(rects) >= 1 and "door" in text):
        ftype, confidence = "cabinet", 0.80 if has_cabinet else 0.50
    # Priority 5: Bed
    elif has_bed:
        ftype, confidence = "bed_headboard", 0.85
    # Priority 6: Chair
    elif has_chair or (len(rects) >= 2 and len(lines) >= 6):
        ftype, confidence = "chair", 0.80 if has_chair else 0.40
    # Priority 7: Circles without text — might be round table
    elif circles:
        ftype, confidence = "round_pedestal_table", 0.50
    # Priority 8: Table mentioned without any other clue
    elif has_table:
        ftype, confidence = "rectangular_table", 0.40

    return {"type": normalize_furniture_type(ftype), "confidence": confidence,
            "required_dimensions": [], "recommended_template": ftype}
