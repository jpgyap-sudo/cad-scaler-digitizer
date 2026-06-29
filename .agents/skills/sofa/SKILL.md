---
name: sofa
description: >
  Guide to identify and parametrically reconstruct sofas and seating units — including
  2-seater, 3-seater, sectional (L-shape/U-shape), chaise, and modular configurations.
  Covers cushion count detection, armrest identification, sectional detection fallback
  behaviour, and correct parameter mapping to build_sofa_model().
---

# Sofa Skill

## 1. Identification Clues

A sofa is a **wide, low seating unit** with a padded backrest, seat cushions, and optional
armrests. Look for:

| Visual Feature | What to Look For |
|---|---|
| **Backrest** | Tall padded panel behind the seat, typically 35-55 cm above seat height |
| **Seat cushions** | Horizontal padded panels at seat level; count of cushions = seating capacity indicator |
| **Armrests** | Padded or upholstered side panels at the left/right ends; may be low/flat or high/rolled |
| **Legs** | Short legs at front corners; may be hidden by skirt fabric or visible as metal/wood feet |
| **Seat height** | Typically 38-48 cm from floor to top of seat cushion |
| **Overall height** | 75-100 cm floor to top of backrest |
| **Depth** | 70-110 cm front to back; deep sofas (> 100 cm) suggest a relaxed/lounge profile |

### Seating Capacity Quick Reference

| Capacity | Typical Width | Seat Count |
|---|---|---|
| 2-seater (loveseat) | 140-175 cm | 2 cushions |
| 3-seater | 180-230 cm | 3 cushions |
| 4-seater | 230-280 cm | 4 cushions or 2 large |
| Sectional / L-shape | 240-320 cm on long arm | Corner + arms |

### Sectional Detection

Look for these sectional indicators:
- **L-shape**: A perpendicular chaise arm extending to one side; longer arm usually 250-320 cm, shorter 150-200 cm
- **U-shape**: Both ends extend forward with a connecting back section; rare, very wide (> 300 cm)
- **Corner unit**: A square corner seat visible where the two sections meet
- **Ottoman attachment**: A detached or attached footrest extending from one end

> **LIMITATION**: `build_sofa_model()` currently renders a straight (linear) sofa regardless
> of sectional flag. If `is_sectional=true`, set `width_cm` to the LONGER arm length and note
> the limitation in metadata. The renderer will produce a straight sofa as a best approximation.

### Do NOT Confuse With

- **Bench / Day bed**: No backrest, or very low backrest (< 20 cm); use different furniture type
- **Armchair**: Single seat only (width 70-100 cm); not a sofa
- **Lounge chair with ottoman**: Two separate pieces; classify the main seat separately
- **Banquette seating**: Fixed to wall, no freestanding legs visible

---

## 2. Critical Parameters

Builder function:
```python
build_sofa_model(width_cm=200, depth_cm=80, height_cm=85)
```

> **Parameter normalization**: `overall_height_cm -> height_cm` in grammar/engine.py.

| Parameter | Builder Arg | Min | Typical | Max | Unit | Notes |
|---|---|---|---|---|---|---|
| Width | `width_cm` | 150 | 200-260 | 350 | cm | Full external width including armrests |
| Depth | `depth_cm` | 70 | 80-95 | 110 | cm | Front leg to back of backrest |
| Height | `height_cm` | 75 | 85 | 100 | cm | Floor to top of backrest |

### Key Sub-Dimensions (Metadata Only — Not Builder Args)

These are extracted for proportional accuracy but are not direct builder parameters:

| Sub-dimension | Typical Range | Notes |
|---|---|---|
| `seat_height_cm` | 38-48 cm (typical 42) | Floor to top of seat cushion |
| `backrest_height_cm` | 35-55 cm above seat | Backrest portion above seat level |
| `armrest_width_cm` | 8-25 cm | Lateral width of one armrest |
| `armrest_height_cm` | 55-75 cm floor height | Top of armrest from floor |
| `seat_depth_cm` | 50-70 cm | Usable seat depth (less than total depth) |
| `leg_height_cm` | 5-20 cm | Clearance from floor to frame base |

### Derived Checks
- `height_cm = seat_height_cm + backrest_height_cm` (approximately)
- `depth_cm = seat_depth_cm + backrest_thickness_cm (10-20 cm)`
- `width_cm = seat_width + (2 x armrest_width_cm)` when armrests are present

---

## 3. SVG Rendering Rules

The builder generates three orthographic views:

### FRONT VIEW
- **Outer silhouette rectangle**: `width_cm x height_cm` -- OBJECT layer (`#1a1a1a`)
- **Seat cushion band**: horizontal rect from floor+leg_height to seat_height; divided into N vertical panels (N = cushion count)
- **Backrest rect**: rectangle from seat level up to height_cm, same width as seat minus armrests
- **Armrest rects**: two vertical rectangles at left and right ends, `armrest_width_cm` wide, full height
- **Cushion divider lines**: vertical lines separating seat cushions and back cushions
- **Leg stubs**: short rectangles at the bottom corners below the seat frame

### TOP VIEW
- **Footprint rectangle**: `width_cm x depth_cm` -- full external envelope
- **Armrest zones**: shaded/outlined rects at each side end showing armrest width
- **Seat depth zone**: dashed line across the footprint at seat_depth_cm from front, indicating where the backrest begins
- **Backrest zone**: rect between dashed line and rear, showing backrest thickness

### SIDE VIEW
- **L-shaped profile**: The sofa side silhouette forms a rough L or J:
  - Vertical backrest rect: `backrest_thickness_cm x backrest_height_cm` at rear
  - Horizontal seat rect: `seat_depth_cm x seat_height_cm`
  - Leg rectangle at bottom front corner
- **Armrest profile**: if visible from side, shows rolled or flat armrest top

### Layer Colours
| Layer | Hex |
|---|---|
| OBJECT | `#1a1a1a` |
| DIMENSION | `#e6c700` |
| LEADER | `#000000` |
| CENTER | `#2563eb` |
| HATCH | `#94a3b8` |

---

## 4. Common Mistakes

### Mistake 1: Width Includes Only Seat, Not Armrests
**Cause**: Measuring the seat cushion width and ignoring the armrests on each side.
**Fix**: `width_cm` is the TOTAL external width from outer edge of left armrest to outer edge of right armrest.

### Mistake 2: Height Measured to Seat, Not Backrest Top
**Cause**: Confusing seat_height with overall height.
**Fix**: `height_cm` is always floor to top of backrest. Seat height is a sub-dimension only.

### Mistake 3: Depth Too Shallow
**Cause**: Reading the seat_depth (usable sitting area) as total depth.
**Fix**: `depth_cm` = seat_depth + backrest_thickness. Add 10-20 cm to seat_depth to get total depth.

### Mistake 4: Sectional Classified as Extra-Wide Straight Sofa
**Cause**: Viewing an L-shape from above makes it look like a very wide sofa.
**Fix**: Check for a perpendicular arm. If detected, set `is_sectional=true` and use the LONGER arm length as `width_cm`. Note: renderer will approximate as straight sofa.

### Mistake 5: Missing Armrests in Width
**Cause**: Arms are low/flat (track arms or tight arms) and blend with the seat visually.
**Fix**: Even low-profile armrests add 8-15 cm per side. Always include in total `width_cm`.

### Mistake 6: Confusing Sofa Depth with Chair Depth
**Cause**: Deep sectional sofas (95-110 cm) are assumed to be armchairs.
**Fix**: Width >= 150 cm is a sofa. Width < 100 cm is a chair.

---

## 5. Sectional Sofa Handling

```
if is_sectional:
    # L-shape: measure the two arms separately
    long_arm_length_cm   = <longer straight section>
    short_arm_length_cm  = <perpendicular section>
    width_cm = long_arm_length_cm   # use long arm for primary dimension
    depth_cm = short_arm_length_cm  # use short arm as depth approximation
    # Note: builder renders straight sofa; L-shape geometry is NOT produced
    metadata.sectional_note = "Sectional approximated as straight sofa"
```

---

## 6. Materials Intelligence

| Component | Typical Materials | Visual Cue |
|---|---|---|
| Upholstery | Linen, velvet, boucle, leather, faux leather | Texture, sheen, colour uniformity |
| Frame (hidden) | Solid hardwood kiln-dried, engineered wood | Not visible; inferred from quality |
| Cushion filling | High-resilience foam, feather wrap, spring-down | Softness / plumpness of cushion edges |
| Legs | Solid beech/oak (natural/stained), powder-coated steel, brass | Wood grain or metallic finish at base |
| Piping / trim | Contrasting fabric, leather welt | Thin outline at cushion seams |

### Upholstery -> SVG Texture
| Material | SVG Treatment |
|---|---|
| Fabric (linen/velvet/boucle) | No hatch; solid OBJECT colour outline with fill |
| Leather | No hatch; slightly thicker outline strokes |
| Two-tone / channel tufting | Vertical or diagonal lines within cushion panels (HATCH `#94a3b8`) |

---

## 7. Dimension Extraction Flow

```
Vision extracts:
  width, depth, height         -> build_sofa_model(width_cm, depth_cm, height_cm)
  seat_height                  -> metadata only
  backrest_height              -> metadata only
  armrest_width                -> metadata only (used for width sanity check)
  cushion_count                -> metadata, used for SVG cushion divider lines
  is_sectional                 -> boolean flag (see sectional handling above)
  leg_style                    -> "wood" | "metal" | "hidden" | "skirt"
  material                     -> stored in metadata
```

---

## 8. Example Extractions

**Product A**: "3-seater sofa in grey linen, W220 x D90 x H85 cm, natural oak legs"

```yaml
furniture_type: sofa
width_cm: 220
depth_cm: 90
height_cm: 85
cushion_count: 3
is_sectional: false
leg_style: wood
material: linen_grey
seat_height_cm: 42
```

Builder call:
```python
build_sofa_model(width_cm=220, depth_cm=90, height_cm=85)
```

---

**Product B**: "L-shape sectional sofa, long arm 280 cm, short arm 165 cm, D95 cm, H85 cm"

```yaml
furniture_type: sofa
width_cm: 280
depth_cm: 165
height_cm: 85
is_sectional: true
sectional_note: "L-shape; renderer approximates as straight sofa using long arm width"
```

Builder call:
```python
build_sofa_model(width_cm=280, depth_cm=95, height_cm=85)
# depth_cm uses the per-arm depth (95 cm), not the short-arm length
```
