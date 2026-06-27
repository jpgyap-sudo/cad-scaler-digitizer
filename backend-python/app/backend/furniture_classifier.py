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
        "oval_pedestal_table": "oval_pedestal_table",
        "oval_table": "oval_pedestal_table",
        "elliptical_table": "oval_pedestal_table",
        "oval_dining_table": "oval_pedestal_table",
        "console_table": "console_table",
        "sofa_table": "console_table",
        "console": "console_table",
        "hall_table": "console_table",
        "office_desk": "office_desk",
        "desk": "office_desk",
        "computer_desk": "office_desk",
        "writing_desk": "office_desk",
        "workstation": "office_desk",
        "asymmetric_pedestal_table": "asymmetric_pedestal_table",
        "asymmetric_table": "asymmetric_pedestal_table",
        "dual_pedestal_table": "asymmetric_pedestal_table",
        "offset_pedestal_table": "asymmetric_pedestal_table",
        "pedestal_dining_table": "asymmetric_pedestal_table",
        "two_pedestal_table": "asymmetric_pedestal_table",
        "rectangular_pedestal_table": "asymmetric_pedestal_table",
        "table": "generic_2d_furniture",  # Fallback: "table" alone is too generic
    }
    return aliases.get(s, s)


def classify_furniture(ocr_lines: list, circles: list, lines: list, rects: list = None) -> dict:
    """Classify furniture type from features with alias normalization.
    
    Geometry rules:
    - Large circles (radius >= 20px) → round table evidence
    - Small circles (radius < 20px) → annotation artifacts, ignored for classification
    - Many rectangles + text keywords → cabinet / sofa / chair
    - Aspect ratio of bounding box → rectangular vs square vs round
    """
    text = " ".join(ocr_lines).lower()
    rects = rects or []

    # Filter out annotation circles (dimension arrows create tiny circles).
    # A real tabletop circle is typically 5-10x larger than annotation circles.
    # Strategy: if the largest circle is >80px AND at least 5x bigger than
    #            the second-largest, it's a real round tabletop.
    sorted_circles = sorted([c for c in circles if len(c) >= 3 and c[2] > 0],
                            key=lambda c: c[2], reverse=True)
    has_large_circle = False
    if len(sorted_circles) >= 1 and sorted_circles[0][2] >= 80:
        if len(sorted_circles) >= 2:
            has_large_circle = sorted_circles[0][2] >= sorted_circles[1][2] * 5
        else:
            has_large_circle = True

    has_dia = any("dia" in t.lower() or "diameter" in t.lower() or "%%c" in t or "\u00d8" in t for t in ocr_lines)
    has_round = any(s in text for s in ["round", "circular", "pedestal", "\u00d8"])
    has_pedestal = "pedestal" in text  # very strong round-pedestal-table signal
    has_asymmetric = any(s in text for s in ["asymmetric", "dual", "offset", "two pedestal"])
    has_oval = any(s in text for s in ["oval", "elliptical", "ellipse"])
    has_console = any(s in text for s in ["console", "sofa table", "hall table"])
    has_desk = any(s in text for s in ["desk", "workstation", "computer"])
    has_table = "table" in text
    has_rect = any(s in text for s in ["rect", "square"])
    has_sofa = any(s in text for s in ["sofa", "couch", "loveseat", "settee"])
    has_cabinet = any(s in text for s in ["cabinet", "wardrobe", "closet", "drawer", "shelf"])
    has_bed = any(s in text for s in ["bed", "headboard", "mattress"])
    has_chair = any(s in text for s in ["chair", "stool", "seat", "armchair"])

    ftype = "generic_2d_furniture"
    confidence = 0.30

    # Compute bounding box aspect ratio from lines
    aspect_ratio = 1.0
    if lines:
        xs = [p[0] for ln in lines for p in (ln if len(ln) == 2 else [(ln[0], ln[1]), (ln[2], ln[3])])]
        ys = [p[1] for ln in lines for p in (ln if len(ln) == 2 else [(ln[0], ln[1]), (ln[2], ln[3])])]
        if xs and ys:
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if h > 0:
                aspect_ratio = w / h

    # Priority 0a: Oval pedestal table
    if (has_oval and has_table) or (has_oval and has_pedestal) or (has_table and "oval" in text):
        ftype, confidence = "oval_pedestal_table", 0.80
    # Priority 0b: Console table
    elif has_console and has_table:
        ftype, confidence = "console_table", 0.80
    # Priority 0c: Office desk
    elif has_desk:
        ftype, confidence = "office_desk", 0.80
    # Priority 0d: Asymmetric pedestal table — two offset pedestals of different sizes
    elif (has_asymmetric and has_table) or (has_pedestal and has_table and "rect" in text and "pedestal" in text):
        ftype, confidence = "asymmetric_pedestal_table", 0.80

    # Priority 0: an explicit "pedestal" label is decisive for a round
    # pedestal table — a drawing that says "TEXTURED PEDESTAL BASE" with a
    # diameter callout is one even if the word "table" never appears.
    # Guard: skip when an explicit competing furniture type is named, because
    # the app stamps a boilerplate "PEDESTAL BASE" line into every drawing's
    # material notes — without this guard a titled "Sofa"/"Cabinet" drawing
    # would match on that boilerplate and be misread as a round table.
    competing_type = has_sofa or has_cabinet or has_bed or has_chair or has_rect
    if has_pedestal and (has_dia or has_round or has_large_circle) and not competing_type:
        ftype, confidence = "round_pedestal_table", 0.85
    # Priority 1: Round table — requires LARGE circle OR strong text evidence
    elif has_large_circle and (has_round or has_dia or has_table):
        ftype, confidence = "round_pedestal_table", 0.85
    elif has_large_circle and has_table:
        ftype, confidence = "round_pedestal_table", 0.70
    elif (has_round or has_dia) and has_table:
        # Strong text evidence without large circle — still round table
        ftype, confidence = "round_pedestal_table", 0.75
    elif has_large_circle:
        # Large circle but no text — moderate confidence
        ftype, confidence = "round_pedestal_table", 0.55
    
    # Priority 2: Rectangular table — many rectangles or wide aspect ratio
    elif (len(rects) >= 1 and (has_table or has_rect)) or (has_table and aspect_ratio > 1.4):
        ftype, confidence = "rectangular_table", 0.80 if has_table else 0.60
    
    # Priority 3: Sofa — wide + low aspect ratio, or text keywords
    elif has_sofa or (len(rects) >= 2 and "seat" in text):
        ftype, confidence = "sofa", 0.85 if has_sofa else 0.50
    
    # Priority 4: Cabinet — tall aspect ratio, or text keywords
    elif has_cabinet or (len(rects) >= 1 and "door" in text) or (aspect_ratio < 0.7 and len(rects) >= 1):
        ftype, confidence = "cabinet", 0.80 if has_cabinet else 0.45
    
    # Priority 5: Bed — extremely wide, or text keywords
    elif has_bed or (aspect_ratio > 3.0 and len(rects) >= 1):
        ftype, confidence = "bed_headboard", 0.85 if has_bed else 0.35
    
    # Priority 6: Chair — small, or text keywords
    elif has_chair or (len(rects) >= 2 and len(lines) >= 6):
        ftype, confidence = "chair", 0.80 if has_chair else 0.40
    
    # Priority 7: Table mentioned without other clues
    elif has_table:
        ftype, confidence = "rectangular_table", 0.40

    return {"type": normalize_furniture_type(ftype), "confidence": confidence,
            "required_dimensions": [], "recommended_template": ftype}
