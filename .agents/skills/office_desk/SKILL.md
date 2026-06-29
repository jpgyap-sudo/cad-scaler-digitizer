---
name: office_desk
description: Guide to identify and parametrically reconstruct office desks with modesty panels and leg supports.
---

# Office Desk with Modesty Panel Skill

## Identification Clues

- **Rectangular top** in both top and front view — moderate aspect ratio (roughly 1.5:1 to 2.5:1 length:depth).
- **Modesty panel**: a solid vertical panel that runs horizontally below the desktop at the front face, sitting between the two front legs. This is the single strongest distinguishing feature.
- **Four corner legs** (square or rectangular section) — not a pedestal, not a trestle.
- **Depth is substantial** (50–80 cm) to accommodate a seated user plus a monitor.
- No hutch, no overhead riser, no drawers in the basic model.
- Cable management grommet holes are often visible in the top as small circles.
- Leg inset from the outer edge is typically 1–5 cm (not flush with the corner like a basic table).
- Front view silhouette looks like a wide "П" shape: desktop + modesty panel fill the gap + short visible leg stubs below the panel.

## Critical Parameters

All parameter names must match the builder exactly:

| Builder Param        | Alias / Note                   | Min | Typical | Max | Unit |
|----------------------|--------------------------------|-----|---------|-----|------|
| `length_cm`          | overall width of desk           | 100 | 140     | 200 | cm   |
| `depth_cm`           | front-to-back dimension         | 50  | 60      | 80  | cm   |
| `height_cm`          | floor to top of desktop         | 72  | 75      | 78  | cm   |
| `top_thick_cm`       | desktop panel thickness         | 2   | 2.5     | 4   | cm   |
| `leg_thick_cm`       | leg square section size         | 3   | 4       | 8   | cm   |
| `modesty_panel_h_cm` | height of front privacy panel   | 10  | 15      | 25  | cm   |
| `leg_inset_cm`       | how far legs sit in from edges  | 1   | 2       | 5   | cm   |

**Parameter normalisation** (grammar/engine.py maps these automatically):
- `overall_height_cm` → `height_cm`
- `leg_thickness_cm` → `leg_thick_cm`

**VISION dimension tags to extract**: `length`, `depth`, `height`, `thickness` (top), `modesty_panel_h`

## SVG Rendering Rules

### Front View

```
[ ══════════════ DESKTOP ══════════════ ]   <- top_thick_cm tall, length_cm wide
[  LEG  ][  MODESTY PANEL (solid band)  ][  LEG  ]
         |  modesty_panel_h_cm tall     |
[  leg  ]                               [  leg  ]   <- stub below panel to floor
```

- **Desktop rect**: width=`length_cm`, height=`top_thick_cm`.
- **Modesty panel rect**: sits flush against the underside of the desktop, between the inner edges of both front legs; width = `length_cm − 2 × (leg_inset_cm + leg_thick_cm)`, height = `modesty_panel_h_cm`.
- **Leg rects**: width=`leg_thick_cm`, total height=`height_cm − top_thick_cm`. The portion above the panel bottom is hidden behind the panel; only the kick-space stub below is drawn as a separate visible element.
- Layer: `OBJECT` (#1a1a1a).

### Side View

- Desktop profile: `depth_cm` wide, `top_thick_cm` tall.
- Front leg: `leg_thick_cm` wide, `height_cm − top_thick_cm` tall.
- Modesty panel shows as a thin band at the front edge only — reads as an L-profile in silhouette.
- Back leg (if visible): dashed/hidden on HIDDEN layer.
- Hatch (ANSI31, 45°) on desktop cross-section for wood grain.

### Top View

- Outer rectangle: `length_cm × depth_cm`.
- Four leg footprints (squares `leg_thick_cm × leg_thick_cm`) near corners, each offset inward `leg_inset_cm` from all edges — drawn on HIDDEN layer (dashed lines).
- Centerlines on CENTER layer (#2563eb): one horizontal axis, one vertical axis.
- Dimension annotations: `W = length_mm`, `D = depth_mm`.

### Dimension / Leader Lines

- Layer: `DIMENSION` (#e6c700).
- Annotate: H (total height), W (length), D (depth), MH (modesty panel height).
- All leader ticks orthographic (90°).

### Hatch Fills

- Desktop wood grain: ANSI31, 45°, layer `HATCH` (#94a3b8).
- Modesty panel: ANSI31, 45° (wood) or ANSI37 (metal frame).

## Common Mistakes

| Mistake | Prevention |
|---------|-----------|
| Omitting the modesty panel | Any filled band under the front of the desktop → set `modesty_panel_h_cm`. Default 15 cm if uncertain. |
| Classifying as rectangular_table | Does the front view have a solid band beneath the desktop? Yes → office_desk. |
| Setting `depth_cm` < 50 | Office desks ≥ 50 cm. Values < 50 → likely a console_table. |
| Using mm values in cm params | All builder params are in **cm**. Always divide mm measurements by 10. |
| Placing modesty panel at floor level | Panel top = underside of desktop. Panel bottom is always above the floor (kick-space gap ≥ 10 cm). |
| Ignoring `leg_inset_cm` | Legs sit inside the outer edge. Never use inset = 0. |
| `modesty_panel_h_cm` too tall | Cap at ~40% of clear leg height: `modesty_panel_h_cm ≤ (height_cm − top_thick_cm) × 0.4`. |

## Materials Intelligence

| Component      | Typical Materials                                     |
|----------------|-------------------------------------------------------|
| Desktop        | MDF with veneer, solid timber, laminate, tempered glass |
| Legs           | Solid timber, powder-coated steel square tube         |
| Modesty Panel  | Matching desktop material (18–25 mm MDF/ply panel)    |
| Fasteners      | Cam locks, wood screws, biscuits (concealed)          |

## Distinction from Similar Furniture

| Feature            | Office Desk       | Rectangular Table | Console Table | Reception Counter |
|--------------------|-------------------|-------------------|---------------|-------------------|
| Modesty panel      | ✅ Yes            | ❌ No             | ❌ No         | ✅ Yes (raised)   |
| Depth (cm)         | 50–80             | 75–100            | 25–45         | 50–90             |
| Wall placement     | Sometimes         | Centre of room    | Always        | Always            |
| Under-desk privacy | ✅ Yes            | ❌ No             | ❌ No         | ✅ Yes            |

## Builder Function Reference

```python
build_office_desk_model(
    length_cm=140,          # overall width of the desk
    depth_cm=60,            # front-to-back dimension
    height_cm=75,           # floor to desktop surface
    top_thick_cm=2.5,       # desktop panel thickness
    leg_thick_cm=4,         # leg square cross-section size
    modesty_panel_h_cm=15,  # height of front privacy/structure panel
    leg_inset_cm=2          # inset of leg centres from desk edges
)
```