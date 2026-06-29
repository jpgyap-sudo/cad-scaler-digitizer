---
name: console_table
description: Guide to identify and parametrically reconstruct console/sofa tables — narrow long tables with simple legs.
---

# Console / Sofa Table Skill

## Identification Clues

- **Very narrow depth** (25–45 cm) is the primary identifier — far shallower than any dining or office table.
- **Long and narrow** top view: aspect ratio (length ÷ depth) is typically **≥ 2.5:1**, often 3:1 or 4:1.
- **Four straight corner legs** (square or tapered round section); no pedestal, no modesty panel.
- Placed flat against a wall — back legs may be simplified or omitted in product renders.
- No drawers in the basic model; occasional single shelf between legs in some variants.
- Height is slightly **taller than a dining table** (70–95 cm) because it is used standing/passing, not seated.
- Front view shows an extremely wide, shallow-looking tabletop sitting on four slim legs.
- Side view is very thin: the depth silhouette is narrow (25–45 cm wide).

## Critical Parameters

All parameter names must match the builder exactly:

| Builder Param  | Alias / Note                   | Min | Typical | Max | Unit |
|----------------|--------------------------------|-----|---------|-----|------|
| `length_cm`    | overall length (left to right)  | 80  | 120     | 200 | cm   |
| `depth_cm`     | front-to-back depth             | 25  | 40      | 55  | cm   |
| `height_cm`    | floor to top surface            | 70  | 80      | 95  | cm   |
| `top_thick_cm` | desktop panel thickness         | 2   | 2.5     | 4   | cm   |
| `leg_thick_cm` | leg cross-section (square/circ) | 2   | 4       | 6   | cm   |
| `leg_inset_cm` | inset of legs from outer edges  | 1   | 2       | 4   | cm   |

**Parameter normalisation** (grammar/engine.py maps automatically):
- `overall_height_cm` → `height_cm`
- `leg_thickness_cm` → `leg_thick_cm`

**VISION dimension tags to extract**: `length`, `depth`, `height`, `thickness` (top)

## SVG Rendering Rules

### Front View

```
[ ════════════════════ DESKTOP ════════════════════ ]  <- top_thick_cm tall, length_cm wide
[LEG]                                             [LEG]  <- leg_thick_cm wide, full leg height
```

- Desktop rectangle: width=`length_cm`, height=`top_thick_cm`.
- Two front leg rectangles: width=`leg_thick_cm`, height=`height_cm − top_thick_cm`, placed at `leg_inset_cm` from each end.
- Back legs drawn as dashed lines on HIDDEN layer (same position, directly behind front legs).
- No modesty panel — the space under the desktop is fully open.
- Layer: `OBJECT` (#1a1a1a).

### Side View

```
[ DESKTOP ]   <- depth_cm wide, top_thick_cm tall
[  LEG   ]   <- leg_thick_cm wide, height_cm - top_thick_cm tall (front leg)
```

- Extremely shallow profile — `depth_cm` will be noticeably smaller than `length_cm`.
- Single front leg (solid), single back leg (dashed/hidden on HIDDEN layer).
- The side silhouette is a simple flat I-shape (no stretchers in the basic model).
- Hatch (ANSI31, 45°) on desktop cross-section.

### Top View

```
┌─────────────────────────────────────────────────────┐
│  [□]                                             [□]  │  <- front leg footprints (HIDDEN)
│                                                       │
│  [□]                                             [□]  │  <- back leg footprints (HIDDEN)
└─────────────────────────────────────────────────────┘
```

- **Highly elongated outer rectangle**: `length_cm × depth_cm`. The strong length:depth ratio is visually obvious.
- Four leg footprints (squares `leg_thick_cm × leg_thick_cm`) at corners, inset `leg_inset_cm` on all sides, on HIDDEN layer.
- Centerlines on CENTER layer (#2563eb): horizontal and vertical axes.
- Dimensions: `W = length_mm`, `D = depth_mm`.

### Dimension / Leader Lines

- Layer: `DIMENSION` (#e6c700).
- Annotate: H (height), W (length), D (depth).
- All leaders orthographic.

### Hatch Fills

- Desktop wood grain: ANSI31, 45°, layer `HATCH` (#94a3b8).
- Metal legs (if applicable): ANSI37, 45°, layer `HATCH`.

## Common Mistakes

| Mistake | Prevention |
|---------|-----------|
| Classifying as rectangular_table | Console depth ≤ 45 cm; dining table depth ≥ 75 cm. If `depth_cm < 50` → likely console. |
| Classifying as office_desk | No modesty panel, no cable holes, depth < 50 → not an office desk. |
| Setting depth_cm ≥ 75 | Console tables are never that deep — re-examine proportions in the photo. |
| Using height 72–78 cm (office range) | Console tables are taller: 70–95 cm. Values around 80–85 cm are typical. |
| Missing leg_inset_cm | Legs sit inward from the outer boundary. Always use ≥ 1 cm. |
| Using mm in cm params | All builder params are **cm**. Divide mm measurements by 10. |
| Aspect ratio < 2.5:1 | If length/depth < 2.5, this may not be a console — verify with the photo. |

## Materials Intelligence

| Component    | Typical Materials                                     |
|--------------|-------------------------------------------------------|
| Top surface  | Solid timber, marble slab, glass, lacquered MDF       |
| Legs         | Solid timber (turned/tapered), powder-coated metal    |
| Optional shelf | Solid timber, rattan, glass panel                   |
| Finish       | Natural wood, black/gold metal, painted               |

## Distinction from Similar Furniture

| Feature           | Console Table | Rectangular Table | Office Desk | Sideboard/Cabinet |
|-------------------|---------------|-------------------|-------------|-------------------|
| Depth (cm)        | 25–45         | 75–100            | 50–80       | 35–55             |
| Against wall?     | Always        | No                | Sometimes   | Always            |
| Legs visible?     | ✅ Open       | ✅ Open           | ✅ Open     | ❌ Closed carcass |
| Aspect ratio      | ≥ 2.5:1       | ~1:1 to 2:1       | 1.5:1–2.5:1 | 1.5:1–3:1         |
| Modesty panel?    | ❌ No         | ❌ No             | ✅ Yes      | N/A               |

## Builder Function Reference

```python
build_console_table_model(
    length_cm=120,    # overall length (left-to-right)
    depth_cm=40,      # front-to-back dimension (narrow!)
    height_cm=80,     # floor to top surface
    top_thick_cm=2.5, # desktop panel thickness
    leg_thick_cm=4,   # leg square cross-section
    leg_inset_cm=2    # inset of legs from outer edges
)
```