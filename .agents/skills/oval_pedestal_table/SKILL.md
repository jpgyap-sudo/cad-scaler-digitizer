---
name: oval_pedestal_table
description: Guide to identify and parametrically reconstruct oval/elliptical pedestal tables with central pedestal support.
---

# Oval Pedestal Table Skill

## Identification Clues

- **Top view is an ellipse** — not a true circle, not a rectangle with corners. Both axes are visible and clearly unequal.
- **Aspect ratio test**: if `length : depth > 1.2 : 1`, classify as oval pedestal (not round pedestal).
- Single central pedestal footprint visible as a small circle at the centroid of the ellipse in top view.
- Front view shows a rectangular tabletop spanning the full length, supported by **one** central vertical column.
- Pedestal column may flare outward at the base (trumpet or star base) but has a single neck connecting to the top.
- No corner legs visible in any view.
- Top surface is often stone (marble, sintered stone, granite) — smooth with a polished edge profile.
- Label or annotation may include the words "oval", "ellipse", or show both a length and a width dimension that differ significantly.
- Side view shows the **depth** (short axis) of the ellipse, which is notably shorter than the front-view width.

## Critical Parameters

These map directly to `build_oval_pedestal_model()` — use these exact names:

| Parameter | Builder Arg | Min | Typical | Max | Unit | Notes |
|---|---|---|---|---|---|---|
| Major axis (length) | `length_cm` | 120 | 180 | 260 | cm | Longest horizontal dimension |
| Minor axis (depth) | `depth_cm` | 80 | 100 | 130 | cm | Shortest horizontal dimension |
| Overall height | `height_cm` | 72 | 75 | 78 | cm | Floor to top surface |
| Tabletop thickness | `top_thick_cm` | 2 | 3 | 5 | cm | Stone tops tend toward 3-4 cm |
| Pedestal diameter | `pedestal_dia_cm` | 25 | 40 | 55 | cm | Single central support column |

### Parameter Derivation from Images
- **length_cm**: measure the widest span of the table in the front view (left edge to right edge).
- **depth_cm**: measure the narrowest span in the side view (front edge to back edge).
- **height_cm**: floor to top surface in front view.
- **top_thick_cm**: height of the tabletop band in front view.
- **pedestal_dia_cm**: width of the central column in the front view.

### VISION Dimension Tag Routing
```
width     -> length_cm      (major axis)
depth     -> depth_cm       (minor axis)
height    -> height_cm
thickness -> top_thick_cm
```

NOTE: Do NOT output `top_dia`. Oval tables require a `length`+`depth` pair, never a single diameter.

## SVG Rendering Rules

Builder: `build_oval_pedestal_model(length_cm, depth_cm, height_cm, top_thick_cm, pedestal_dia_cm)`

### Top View
- **Shape**: Ellipse entity with `rx = length_cm / 2`, `ry = depth_cm / 2`, centred at origin.
- **Wood/stone grain**: Horizontal hatch lines spaced ~5 cm apart across the ellipse body, clipped to ellipse boundary.
- **Pedestal footprint**: Small circle at centre, `r = pedestal_dia_cm / 2`, drawn on the CENTER layer (blue, #2563eb).
- **Centrelines**: One horizontal and one vertical centreline crossing at origin, on CENTER layer.
- **Dimensions**:
  - `L = length_cm` linear dimension along the long axis (DIMENSION layer, #e6c700).
  - `D = depth_cm` linear dimension along the short axis.

### Front View
- **Tabletop**: Rectangle `width = length_cm`, `height = top_thick_cm`, positioned at top of elevation.
- **Pedestal column**: Rectangle `width = pedestal_dia_cm`, `height = (height_cm - top_thick_cm)`, centred horizontally, directly below tabletop.
- **Base flare** (if applicable): Wider trapezoid or rectangle at floor level, typically `1.5 x pedestal_dia_cm` wide, ~3-5 cm tall.
- **Hatch**: ANSI37 metal hatch on pedestal column; ANSI31 diagonal hatch on tabletop.
- **Dimensions**:
  - Height `H` on left side, floor to top surface.
  - Top thickness `T` with leader on top band.
  - Pedestal diameter `O` with leader or linear on column.

### Side View
- Tabletop rectangle `width = depth_cm`, `height = top_thick_cm`.
- Single pedestal column `width = pedestal_dia_cm` (same diameter, centred).
- Dimension `D = depth_cm` at top.

## Common Mistakes

| Mistake | Why It Happens | Prevention |
|---|---|---|
| Classified as `round_pedestal_table` | Ellipse viewed at angle looks circular | Check both L and D dimensions; if ratio > 1.2 it's oval |
| Output `top_dia` instead of `length_cm` + `depth_cm` | Confusion with round pedestal builder | Oval builder has NO `top_dia` param -- always use length/depth pair |
| `length_cm < depth_cm` | Axes swapped | Enforce: `length_cm` is always the **major** (longer) axis |
| `pedestal_dia_cm > depth_cm` | Pedestal wider than the short axis | Impossible geometry -- pedestal must fit within depth |
| Classified as `rectangular_table` | Rectangular top view of asymmetric oval | Look for curved edges; any curvature = pedestal candidate |
| `depth_cm` set equal to `length_cm` | Oval treated as circle | If equal, round pedestal is correct; if different, use oval |

## Materials Intelligence

| Component | Typical Material | Visual Clue |
|---|---|---|
| Tabletop | Marble, sintered stone, granite | Polished edge, veining pattern, cold grey/white tone |
| Pedestal column | Brushed stainless steel, lacquered steel | Reflective or matte metal surface, cylindrical |
| Base | Cast iron, powder-coated steel | Heavier/darker finish at floor level |

### Hatch Convention
- Tabletop stone: ANSI31 at 45 degrees (diagonal lines), layer HATCH (#94a3b8).
- Pedestal metal: ANSI37 crosshatch, layer HATCH (#94a3b8).
- Object outlines: layer OBJECT (#1a1a1a).
- Dimensions: layer DIMENSION (#e6c700).
- Leaders: layer LEADER (#000000).
- Centrelines and pedestal footprint: layer CENTER (#2563eb).

## Quick Reference Card

```
Oval Pedestal Table
-----------------------------------------
Builder : build_oval_pedestal_model()
Shape   : Ellipse (L > D)
Support : 1 central column
-----------------------------------------
Params (cm):
  length_cm        120-260  (typ 180)  <- major axis
  depth_cm          80-130  (typ 100)  <- minor axis
  height_cm          72-78  (typ  75)
  top_thick_cm         2-5  (typ   3)
  pedestal_dia_cm    25-55  (typ  40)
-----------------------------------------
Sanity:
  length_cm > depth_cm          (else -> round)
  pedestal_dia_cm < depth_cm    (else -> won't fit)
  height_cm > top_thick_cm
```
