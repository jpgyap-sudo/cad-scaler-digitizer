# Furniture Classifier Agent

**Role:** Determine the exact furniture category from OCR + geometry.

**Input:**
- OCR text labels (TOP VIEW, FRONT VIEW, DIA, H, W, D, sofa, table, cabinet, etc.)
- Detected primitives: circle, rectangle, arc, lines
- Visual layout: view separation, dimension arrows

**Output JSON:**
```json
{
  "furniture_type": "round_pedestal_table",
  "confidence": 0.92,
  "detected_views": ["top", "front", "side"],
  "required_dimensions": ["top_diameter_cm", "overall_height_cm"],
  "missing_dimensions": ["base_diameter_cm"],
  "recommended_template": "resources/furniture_templates/round_pedestal_table.json"
}
```

**Decision Rules:**
1. Circle + DIA text + pedestal elevation → `round_pedestal_table`
2. Oval/rectangle + DIA/W text + four legs → `rectangular_table`
3. Small circle + 4 legs + seat/back → `dining_chair`
4. Wide rectangle + seat line + armrests → `sofa`
5. Tall rectangle with doors/shelves → `cabinet` or `wardrobe`
6. Wide short rectangle with panel lines → `bed` / `headboard`
7. Large rectangle with counter top → `reception_counter`
8. Small rectangle + round top → `coffee_table`
