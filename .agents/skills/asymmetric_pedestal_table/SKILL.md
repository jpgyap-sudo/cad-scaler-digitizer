---
name: asymmetric_pedestal_table
description: Guide to identify and parametrically reconstruct asymmetric cylindrical pedestal dining tables with marble/stone tops and dual offset metal pedestals.
---

# Asymmetric Pedestal Table Skill

## Identification Clues

- **Two distinct pedestal columns** visible in the front view — of DIFFERENT diameters, at DIFFERENT horizontal offsets from centre. This is the defining feature.
- Top view (rectangular) shows **two circular footprints** at non-symmetric positions — one closer to one end, one closer to the other.
- `support_count = 2` in vision facts. If only one pedestal is visible, use `oval_pedestal_table` or `round_pedestal_table` instead.
- Pedestals are **NOT** evenly spaced as mirror images; the larger column is offset further from centre than a symmetric layout would suggest.
- No corner legs in any view.
- Thin stone/marble/sintered tabletop (2.5–4 cm thick) with a clean horizontal top edge.
- Brushed metal pedestals (stainless steel or dark powder-coat), cylindrical (not tapered, not square).
- Side view: one pedestal appears as a solid outline (closer to viewer), the other as a hidden/dashed outline (further from viewer).
- Overhangs differ at each end of the table — the end nearest the smaller pedestal typically has a larger overhang.

## Critical Parameters

These map directly to `build_asymmetric_pedestal_model()` — use these exact names:

| Parameter | Builder Arg | Min | Typical | Max | Unit | Notes |
|---|---|---|---|---|---|---|
| Table length | `length_cm` | 120 | 180 | 240 | cm | Full tabletop major dimension |
| Table depth | `depth_cm` | 70 | 90 | 110 | cm | Full tabletop minor dimension |
| Overall height | `height_cm` | 72 | 75 | 78 | cm | Floor to top surface |
| Tabletop thickness | `top_thick_cm` | 1.5 | 3 | 5 | cm | Stone/sintered slab |
| Large pedestal diameter | `large_ped_dia_cm` | 25 | 40 | 50 | cm | Wider column (left side by convention) |
| Small pedestal diameter | `small_ped_dia_cm` | 15 | 22 | 30 | cm | Narrower column (right side by convention) |
| Left pedestal X offset | `left_ped_x_cm` | 20 | 30 | 45 | cm | Distance from table centre toward left end (positive value) |
| Right pedestal X offset | `right_ped_x_cm` | -35 | -25 | -15 | cm | Distance from table centre toward right end (negative value) |

### Offset Sign Convention
- `left_ped_x_cm` is a **positive** number — the large pedestal is offset to the LEFT of centre.
- `right_ped_x_cm` is a **negative** number — the small pedestal is offset to the RIGHT of centre.
- Both pedestals are typically inset from the table ends by `large_ped_dia_cm / 2` minimum to avoid overhang.

### Parameter Derivation from Images
- **length_cm**: total tabletop width in front view.
- **depth_cm**: total tabletop depth in side view.
- **large_ped_dia_cm**: measure the wider column's width in the front view.
- **small_ped_dia_cm**: measure the narrower column's width in the front view.
- **left_ped_x_cm**: horizontal distance from table centreline to the centre of the large pedestal in the front view (read as positive cm).
- **right_ped_x_cm**: horizontal distance from table centreline to the centre of the small pedestal in the front view (read as negative cm).

### VISION Dimension Tag Routing
```
length    -> length_cm
width     -> length_cm    (if "width" refers to major axis)
depth     -> depth_cm
height    -> height_cm
thickness -> top_thick_cm
```

For pedestal offsets, extract from visual measurement relative to the table's centre:
```
left_ped_x_cm   = (table_left_edge_to_large_ped_centre) - (length_cm / 2)  [expressed positive]
right_ped_x_cm  = (table_right_edge_to_small_ped_centre) - (length_cm / 2) [expressed negative]
```

## SVG Rendering Rules

Builder: `build_asymmetric_pedestal_model(length_cm, depth_cm, height_cm, top_thick_cm, large_ped_dia_cm, small_ped_dia_cm, left_ped_x_cm, right_ped_x_cm)`

### Front View
- **Tabletop**: Full-width rectangle, `width = length_cm`, `height = top_thick_cm`, at top of elevation. Stone hatch ANSI31.
- **Large pedestal (left)**: Rectangle `width = large_ped_dia_cm`, `height = (height_cm - top_thick_cm)`. Horizontally centred at `x = left_ped_x_cm` from table centre (offset to the LEFT). Touches the floor line. Metal hatch ANSI37.
- **Small pedestal (right)**: Rectangle `width = small_ped_dia_cm`, `height = (height_cm - top_thick_cm)`. Horizontally centred at `x = right_ped_x_cm` from table centre (offset to the RIGHT). Touches the floor line. Metal hatch ANSI37.
- **Dimensions**:
  - `H`: overall height, left side leader.
  - `L`: overall length, top or bottom.
  - `OL`: left overhang (from left table edge to left edge of large pedestal).
  - `OR`: right overhang (from right edge of small pedestal to right table edge).
  - `O_LARGE`: large pedestal diameter, with leader.
  - `O_SMALL`: small pedestal diameter, with leader.

### Top View
- **Tabletop**: Rectangle `width = length_cm`, `height = depth_cm`. Stone hatch ANSI31.
- **Large pedestal footprint**: Circle `r = large_ped_dia_cm / 2`, centred at `(left_ped_x_cm, 0)` from table centre, on CENTER layer (#2563eb).
- **Small pedestal footprint**: Circle `r = small_ped_dia_cm / 2`, centred at `(right_ped_x_cm, 0)` from table centre, on CENTER layer (#2563eb).
- **Centrelines**: Horizontal and vertical through table centre.
- **Dimensions**: `L = length_cm`, `D = depth_cm`.

### Side View
- Tabletop rectangle `width = depth_cm`, `height = top_thick_cm`.
- **Closer pedestal** (whichever is front in the physical setup): solid outline rectangle.
- **Further pedestal**: hidden/dashed lines on HIDDEN layer.
- Dimensions: `H = height_cm`, `D = depth_cm`.

## Common Mistakes

| Mistake | Why It Happens | Prevention |
|---|---|---|
| Treated as single-pedestal table | Only one pedestal visible from a photo angle | Check side view for a second dashed outline; check top view for two footprint circles |
| Both pedestals given the same diameter | Overlooking size difference | Asymmetric by definition means two DIFFERENT diameters; measure each independently |
| `right_ped_x_cm` entered as positive | Sign convention unclear | Right pedestal is always negative offset; enforce `right_ped_x_cm < 0` |
| Pedestals overlap each other | Offsets too close to zero | Check: `left_ped_x_cm - large_ped_dia_cm/2 > right_ped_x_cm + small_ped_dia_cm/2` |
| Pedestals protrude beyond table end | Offsets too large | Each pedestal edge must remain inside table boundary by at least `pedestal_dia_cm / 2` |
| Classified as `oval_pedestal_table` | Top edge appears curved in perspective photo | Oval = 1 pedestal, elliptical top. Asymmetric = 2 pedestals, rectangular top. |
| Classified as `rectangular_table` | No obvious corner legs | Look for cylinders, not rectangular leg profiles in front view |

## Non-Overlap Constraint

Both pedestals must remain non-overlapping and within the table boundary:

```
left_ped_x_cm  - (large_ped_dia_cm / 2)  >  right_ped_x_cm + (small_ped_dia_cm / 2)
                                              [gap between inner edges must be positive]

left_ped_x_cm  + (large_ped_dia_cm / 2)  <  length_cm / 2
                                              [large pedestal right edge inside table]

|right_ped_x_cm| + (small_ped_dia_cm / 2) <  length_cm / 2
                                              [small pedestal left edge inside table]
```

## Materials Intelligence

| Component | Typical Material | Visual Clue |
|---|---|---|
| Tabletop | Marble, sintered stone, Calacatta, Statuario | Veining, cool white/grey, polished edge |
| Large pedestal | Brushed stainless steel | Vertical grain marks, reflective cylinder |
| Small pedestal | Brushed stainless steel (matching) | Same surface finish as large pedestal |
| Floor contact base | Circular steel plate or dome foot | Slight flare or disc at column base |

### Hatch Convention
- Tabletop stone: ANSI31 at 45 degrees, layer HATCH (#94a3b8).
- Pedestal columns metal: ANSI37 crosshatch, layer HATCH (#94a3b8).
- Object outlines: layer OBJECT (#1a1a1a).
- Dimensions: layer DIMENSION (#e6c700).
- Leaders: layer LEADER (#000000).
- Centrelines and pedestal footprints: layer CENTER (#2563eb).
- Hidden pedestal (side view): dashed lines on HIDDEN layer.

## Quick Reference Card

```
Asymmetric Pedestal Table
-----------------------------------------
Builder : build_asymmetric_pedestal_model()
Shape   : Rectangle top, 2 offset cylinders
Support : 2 pedestals (large LEFT, small RIGHT)
-----------------------------------------
Params (cm):
  length_cm          120-240  (typ 180)
  depth_cm            70-110  (typ  90)
  height_cm            72-78  (typ  75)
  top_thick_cm           1.5-5 (typ   3)
  large_ped_dia_cm    25-50  (typ  40)   <- LEFT pedestal
  small_ped_dia_cm    15-30  (typ  22)   <- RIGHT pedestal
  left_ped_x_cm       20-45  (typ  30)   <- positive, leftward from centre
  right_ped_x_cm    -35--15  (typ -25)   <- negative, rightward from centre
-----------------------------------------
Sanity:
  large_ped_dia_cm > small_ped_dia_cm
  left_ped_x_cm > 0
  right_ped_x_cm < 0
  pedestals do not overlap (inner edges must be separated)
  each pedestal fits inside table boundary
```
