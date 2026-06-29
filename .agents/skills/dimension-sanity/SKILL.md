---
name: dimension-sanity
description: Cross-checks AI-extracted furniture dimensions against a furniture standards database. Catches unit errors (mm vs cm confusion), impossible values, and swapped length/depth. Returns corrected dimensions with a sanity_flag log.
---

# Dimension Sanity Checker

## Purpose

Prevents bad dimensions from reaching the SVG builder by validating every extracted value against known furniture standards BEFORE calling `_dispatch_furniture()`.

## Common errors it catches

| Error | Example | Fix |
|-------|---------|-----|
| mm not converted | `height=750` (should be 75) | Divide by 10 if value in obvious mm range |
| length/depth swap | `width=90, length=200` on a table listed as 90×200 | Ensure width=90 (narrow), length=200 (long) |
| impossible ratio | `leg_thickness=20` for a 80cm wide table | Flag, suggest typical 4-8cm |
| pedestal wider than top | `base_dia=120` on a 90cm table | Flag impossible, cap at top_dia*0.85 |
| dining height | `height=40` for a dining table | Flag, typical dining is 72-78cm |

## Integration point

Call `check_and_correct_dimensions(furniture_type, dims_dict)` after AI extraction, before building the model.

```python
from app.backend.dimension_sanity import check_and_correct_dimensions

corrected, flags = check_and_correct_dimensions(
    furniture_type="rectangular_table",
    dims={"width_cm": 90, "length_cm": 1800, "height_cm": 75}
)
# corrected = {"width_cm": 90, "length_cm": 180, "height_cm": 75}
# flags = ["length_cm: 1800 looks like mm — divided by 10 → 180"]
```

## Sanity rules per furniture type

See `resources/dimension_standards.json` for the complete machine-readable rules.

## Auto-correction policy

- **Divide by 10:** If a cm value > 5× the maximum known range → likely mm input
- **Swap width/length:** If width > length for a rectangular table → swap
- **Cap impossible values:** If pedestal wider than tabletop → cap at 85% of top_dia
- **Flag, don't auto-fix:** If value is in plausible but unusual range → add to flags list only
