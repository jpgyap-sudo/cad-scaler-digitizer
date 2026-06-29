---
name: rectangular_table
description: >
  Guide to identify and parametrically reconstruct rectangular tables with legs
  and optional stretchers. Covers dining tables, side tables, and rectangular
  coffee tables. Uses build_rectangular_table_model() builder.
---

# Rectangular Table Skill

## Overview

Rectangular tables are the most common furniture type in dining rooms, kitchens,
meeting rooms, and living spaces. They feature a flat rectangular top supported by
four legs (or alternative structural systems), with optional stretchers or aprons
connecting the legs for rigidity. This skill governs how the AI vision system extracts
dimensions and how the SVG rendering pipeline draws the result.

---

## Identification Clues

Look for these visual signals to classify an item as a **rectangular table**:

| Signal | Detail |
|--------|--------|
| **Top shape** | Strictly rectangular — four 90° corners, no rounded ends, no oval curves |
| **Leg count** | Typically 4 legs, one at each corner; trestle uses 2 end frames |
| **Leg style** | Tapered, box/square, hairpin (thin rod), cross-frame, or trestle |
| **Apron / skirt** | Horizontal frame connecting top to legs — often visible in front elevation |
| **Stretcher** | Low horizontal bar(s) connecting leg pairs for rigidity; not always present |
| **Profile view** | Side view shows a thin top slab sitting on slender vertical legs |
| **Plan view** | Clear rectangle with no circular or oval geometry |
| **Proportions** | Width always greater than depth for standard rectangular tables |

### Sub-type Recognition

| Sub-type | Height Range | Width Range | Typical Context |
|----------|-------------|-------------|-----------------|
| Dining table | 72–78 cm | 120–300 cm | Dining room, kitchen |
| Meeting / conference | 72–76 cm | 180–400 cm | Office, boardroom |
| Side / accent table | 55–75 cm | 40–80 cm | Beside sofa, bedroom |
| Console table | 70–85 cm | 80–180 cm | Hallway, behind sofa |
| Rectangular coffee table | 35–50 cm | 80–160 cm | Living room, lounge |

> **Important:** Do NOT use the rectangular_table builder for coffee tables — use
> `build_coffee_table_model()` instead. Use this builder for dining, side, and
> meeting tables.

---

## Critical Parameters

These map directly to `build_rectangular_table_model()`:

```python
build_rectangular_table_model(
    width_cm=120,        # long horizontal dimension (X-axis)
    depth_cm=80,         # short horizontal dimension (Y-axis)
    height_cm=70,        # floor to top surface
    leg_thickness_cm=6   # square leg cross-section dimension
)
```

### Parameter Reference Table

| Parameter | Builder Name | Min | Max | Typical | Notes |
|-----------|-------------|-----|-----|---------|-------|
| Width (long side) | `width_cm` | 60 | 300 | 120–200 | Always the longer horizontal dimension |
| Depth (short side) | `depth_cm` | 60 | 100 | 80–90 | Always the shorter horizontal dimension |
| Overall height | `height_cm` | 35 | 80 | 72–78 (dining) | Floor to top surface |
| Leg thickness | `leg_thickness_cm` | 4 | 10 | 6–8 | Square section; hairpin legs may be 1–2 cm |

### VISION Dimension Tag -> Parameter Mapping

The AI vision system extracts dimension tags which the grammar engine maps:

| Vision Tag | Maps To | Notes |
|------------|---------|-------|
| `width` | `width_cm` | Direct pass-through |
| `length` | `width_cm` | Alias — length always means the long side |
| `depth` | `depth_cm` | Short horizontal dimension |
| `height` | `height_cm` | Also aliased from `overall_height_cm` |
| `leg_thickness` | `leg_thickness_cm` | Also aliased from `leg_thick_cm` |
| `overall_height_cm` | `height_cm` | Normalized by grammar engine |
| `leg_thick_cm` | `leg_thickness_cm` | Normalized by grammar engine |

---

## SVG Rendering Rules

The builder generates **three orthographic views** arranged on a single SVG canvas.

### TOP VIEW (Plan)

- **Shape:** Solid rectangle `width_cm x depth_cm`
- **Hatching:** Diagonal cross-hatch pattern (45° lines at ~8 cm spacing) fills the
  tabletop area, rendered in `HATCH=#94a3b8` color
- **Leg footprints:** Four small squares (`leg_thickness_cm x leg_thickness_cm`) drawn
  at each inner corner, offset ~2 cm from the edges
- **Centerlines:** One horizontal + one vertical centerline crossing at the centre,
  rendered in `CENTER=#2563eb` color with long-dash pattern
- **Dimension lines:**
  - **W** arrow: spans full width at the bottom edge, labeled with value in cm
  - **D** arrow: spans full depth at the right edge, labeled with value in cm
  - All dimension geometry uses `DIMENSION=#e6c700` color

### FRONT VIEW (Elevation)

- **Tabletop slab:** Rectangle of `width_cm x top_thick_cm` (top thickness approx 3 cm
  default) at the top of the view, filled/outlined in `OBJECT=#1a1a1a`
- **Apron (if present):** Thin horizontal band ~5–8 cm tall immediately below the slab
- **Legs:** Four rectangles of `leg_thickness_cm x leg_height_cm` hanging from the
  underside of the apron/slab to the floor line
  - Outer two legs are fully visible; inner two may be hidden-line dashed
  - `leg_height_cm = height_cm - top_thick_cm - apron_height_cm`
- **Floor line:** Thin horizontal line at y=0, spans the full width
- **Height dimension:** Leader line on the right side spanning floor to top surface,
  labeled `H = {height_cm} cm`

### SIDE VIEW (Elevation)

- **Shape:** Rectangle `depth_cm x height_cm` — the depth profile
- **Tabletop slab:** Same top_thick_cm band at the top
- **Legs:** Two rectangles (near + far legs), `leg_thickness_cm x leg_height_cm`
- **Depth dimension:** Dimension line at bottom labeled `D = {depth_cm} cm`

### Layer Color Reference

| Layer | Hex | Usage |
|-------|-----|-------|
| OBJECT | `#1a1a1a` | All solid geometry lines |
| DIMENSION | `#e6c700` | Dimension arrows, text, extension lines |
| LEADER | `#000000` | Leader lines to notes |
| CENTER | `#2563eb` | Centerlines |
| HATCH | `#94a3b8` | Fill hatching on plan view |

---

## Dimension Extraction Protocol

When reading a product photo or technical drawing:

1. **Identify the long side** -> this is always `width_cm` (or `length`, which maps to `width_cm`)
2. **Identify the short side** -> this is always `depth_cm`
3. **Read the floor-to-surface height** -> `height_cm`
4. **Estimate leg thickness** from proportional comparison to height:
   - Slender modern legs: 4–5 cm
   - Standard dining legs: 6–8 cm
   - Heavy farmhouse/industrial legs: 8–10 cm
5. **Classify sub-type** using height:
   - 72–78 cm -> dining/standard table
   - 35–50 cm -> coffee/cocktail table (route to coffee_table builder instead)
   - 55–70 cm -> side/accent table or console table

### Visual Proportion Estimates

When no explicit dimensions are given, estimate from proportions:

- Standard dining chair seat height approx 45 cm -> table height approx 75 cm
- Standard door height approx 210 cm -> useful as background reference
- Tabletop slab thickness is typically 2–5% of total height
- Leg thickness is typically 4–8% of table width for dining tables

---

## Materials Intelligence

### Tabletop Materials

| Material | Visual Cues | Typical Thickness |
|----------|-------------|------------------|
| Marble / natural stone | Visible veining, polished sheen, heavy appearance | 2–4 cm |
| Sintered stone (e.g. Dekton) | Very flat, matte or satin, no visible veins | 1.2–2 cm |
| Tempered glass | Transparent, edge visible as thin green/grey line | 1–1.5 cm |
| Solid hardwood | Wood grain visible, warm tones, visible joints | 2.5–4 cm |
| MDF / lacquer | Smooth, monochromatic, no grain visible | 1.8–3 cm |
| Ceramic / porcelain | Matte surface, may have subtle texture, grout if tiled | 1–2 cm |

### Leg / Base Materials

| Material | Visual Cues | Typical Thickness |
|----------|-------------|------------------|
| Powder-coated steel | Uniform flat colour (black, white, grey), sharp edges | 4–6 cm square or 3–5 cm round |
| Brushed brass / gold | Warm metallic sheen, visible brush direction | 3–5 cm |
| Chrome / stainless | High reflectivity, mirror-like | 3–5 cm |
| Solid oak / walnut | Natural grain on legs, tapered profile | 6–9 cm |
| Painted wood | Smooth finish, no grain visible | 6–8 cm |

---

## Common Mistakes

### 1. Confusing Width and Depth (Length vs Depth)

**Problem:** AI may label the long side as "length" and short side as "width", or
vice versa.

**Rule:** The grammar engine maps `length -> width_cm`. Always ensure the **longer**
dimension is assigned to `width_cm`. If depth_cm > width_cm, swap the values.

**Prevention:** Add sanity check: assert width_cm >= depth_cm

---

### 2. Legs Drawn Too Thick

**Problem:** Leg thickness set to >10 cm makes the table look like a support column.

**Rule:** Leg thickness for dining tables should be 4–8 cm. For coffee tables <= 5 cm.
For hairpin/rod legs, use 1–2 cm.

**Prevention:** Cap `leg_thickness_cm` at 10 cm. If extracted value exceeds this,
it is likely the apron/frame width, not leg section.

---

### 3. Missing Tabletop Thickness

**Problem:** The front view shows the tabletop as a single line with zero thickness.

**Rule:** Always render a visible slab of 2–5 cm. Default to 3 cm if unspecified.

---

### 4. Confusing Dining Height with Coffee Table Height

**Problem:** A 75 cm coffee table is drawn using the rectangular table builder,
producing an absurdly tall coffee table.

**Rule:**
- Height 72–78 cm -> dining/standard table -> `build_rectangular_table_model()`
- Height 35–50 cm -> coffee table -> `build_coffee_table_model()`
- When in doubt, check context clues (chairs present? sofa nearby?)

---

### 5. Apron vs Leg Thickness Confusion

**Problem:** The apron (horizontal frame below top) is measured and reported as
`leg_thickness_cm`.

**Rule:** Leg thickness is the **cross-section** of the vertical leg member, not
the apron depth. Apron depth is a separate aesthetic feature.

---

### 6. Negative or Zero Leg Height

**Problem:** If `height_cm` is entered smaller than `top_thick_cm`, the leg height
becomes negative or zero.

**Rule:** Validate: `leg_height = height_cm - top_thick_cm - apron_h >= 20 cm`.
If not, the height value was likely incorrectly extracted.

---

## Sanity Checks

| Rule | Condition | Action |
|------|-----------|--------|
| Width >= depth | `width_cm >= depth_cm` | Swap if violated |
| Dining height range | `72 <= height_cm <= 78` for dining | Flag if outside range |
| Coffee height range | `35 <= height_cm <= 50` for coffee | Flag if outside range |
| Leg not too thick | `leg_thickness_cm <= 10` | Cap and warn |
| Leg not too thin | `leg_thickness_cm >= 2` | Warn |
| Reasonable width | `60 <= width_cm <= 400` | Flag extremes |
| Reasonable depth | `40 <= depth_cm <= 120` | Flag extremes |
| Top thicker than 0 | `top_thick_cm >= 1.5` | Default to 3 cm |

---

## Example Extraction

**Product:** "240 x 100 cm dining table in Calacatta marble with black powder-coated
steel legs, height 75 cm, leg section 5 x 5 cm"

```json
{
  "furniture_type": "rectangular_table",
  "width_cm": 240,
  "depth_cm": 100,
  "height_cm": 75,
  "leg_thickness_cm": 5,
  "top_material": "marble",
  "leg_material": "powder-coated steel"
}
```

**Product:** A product photo showing a table with chairs — estimated proportions:
- Table appears to be 160 cm wide, 90 cm deep, 75 cm tall
- Square tapered wooden legs appear ~7 cm wide

```json
{
  "furniture_type": "rectangular_table",
  "width_cm": 160,
  "depth_cm": 90,
  "height_cm": 75,
  "leg_thickness_cm": 7
}
```
