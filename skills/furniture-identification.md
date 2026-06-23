# Furniture Identification Skill

Goal: identify furniture type from sketch/photo/PDF before CAD export.

Inputs:
- OCR text labels: TOP VIEW, FRONT VIEW, DIA, H, sofa, table, cabinet, etc.
- Detected primitives: circle, rectangle, arc, long horizontal/vertical lines.
- Visual layout: separated views, dimensions, arrows.

Decision rules:
1. Circle + DIA + pedestal elevation = round_pedestal_table.
2. Long rectangle + legs = rectangular_table.
3. Large rectangle with doors/shelves = cabinet/wardrobe.
4. Seat/back/arm profile = sofa/chair.
5. Headboard wide rectangle + wall/panel lines = bed/headboard.

Output JSON:
```json
{
  "furniture_type": "round_pedestal_table",
  "confidence": 0.0,
  "required_dimensions": [],
  "missing_dimensions": [],
  "recommended_template": "resources/furniture_templates/...json"
}
```
