# HomeU Furniture Template Upgrade

Copy `resources/furniture_templates/*.json` into your repo at:

```text
resources/furniture_templates/
```

Then either:

1. Keep your current loader and read the new fields gradually, or
2. Add `tools/template_selector.py` and call `select_template(evidence)` before DXF generation.

Minimum evidence object:

```json
{
  "title": "Kean Tables | Center Table | Coffee Table",
  "category": "center table",
  "tags": ["rectangular", "stone", "low-table"],
  "detected_shapes": ["rectangle"],
  "detected_components": ["tabletop", "legs", "base"],
  "aspect_ratio": 2.0
}
```

Important: do not generate DXF directly after generic category classification. First select a specific template, then ask user confirmation when confidence is low.
