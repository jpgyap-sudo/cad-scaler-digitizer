---
name: round_pedestal_table
description: >
  Guide to identify and parametrically reconstruct round pedestal tables with
  circular tops and a single central column support. Covers marble, stone, and
  wood tops with metal or wood pedestals. Uses build_round_pedestal_model() builder.
---

# Round Pedestal Table Skill

## Overview

Round pedestal tables are characterized by a circular top supported by a single
central column (the pedestal or neck), which expands at the base into a wider foot
plate. They are common as dining tables, side tables, café bistro tables, and
occasional accent pieces. The absence of corner legs makes round pedestal tables
visually light and highly versatile for small spaces.

This skill governs both the AI vision extraction of dimensions and the SVG rendering
via `build_round_pedestal_model()`.

---

## Identification Clues

Look for these visual signals to classify an item as a **round pedestal table**:

| Signal | Detail |
|--------|--------|
| **Top shape (plan view)** | True circle — NOT an oval, ellipse, or rounded rectangle |
| **Leg count** | Zero visible corner legs; ONE central column only |
| **Column / neck** | Visible vertical shaft rising from the base plate to the top underside |
| **Base spread** | The base plate/foot is wider than the neck, creating a stable triangular or disc profile |
| **Front elevation** | Reads as: [tabletop rectangle] → [collar trapezoid] → [neck rectangle] → [base trapezoid] → [base plate] |
| **Circular plan symbol** | In technical drawings, a filled circle entity represents the top |
| **Centre mark** | Technical drawings show a crosshair at the circle centre |
| **Context** | Typically paired with dining chairs or found in café/restaurant settings |

### Pedestal Profile Sub-types

| Profile | Visual Character | When to Use |
|---------|-----------------|-------------|
| `cylinder` | Neck and base are similar in diameter; column looks uniform | Modern, minimal, industrial styles |
| `tapered` | Neck clearly narrower than base; smooth taper or stepped shoulder | Traditional, transitional styles |
| `flared` | Neck very narrow, base widens dramatically like a trumpet bell | Art Deco, sculptural, statement pieces |

---

## Critical Parameters

These map directly to `build_round_pedestal_model()`:

```python
build_round_pedestal_model(
    top_dia_cm=80,       # diameter of the circular tabletop
    height_cm=73,        # floor to top surface (overall height)
    base_dia_cm=44,      # diameter of the base foot plate
    neck_dia_cm=22,      # diameter of the narrowest column section
    collar_dia_cm=48,    # diameter of the transition collar below the top
    top_thick_cm=3,      # thickness of the tabletop slab
    base_thick_cm=1,     # thickness of the base foot plate
    profile="tapered"    # cylinder | tapered | flared
)
```

### Parameter Reference Table

| Parameter | Builder Name | Min | Max | Typical | Notes |
|-----------|-------------|-----|-----|---------|-------|
| Top diameter | `top_dia_cm` | 60 | 130 | 80–100 | The overall width of the table in all directions |
| Overall height | `height_cm` | 68 | 80 | 73 | Floor to top surface |
| Base diameter | `base_dia_cm` | 30 | 60 | 44 | Foot spread at floor level |
| Neck diameter | `neck_dia_cm` | 15 | 35 | 22–28 | Column shaft at narrowest point |
| Collar diameter | `collar_dia_cm` | 35 | 65 | 45–50 | Transition piece just below the tabletop |
| Top thickness | `top_thick_cm` | 2 | 6 | 3–4 | Slab thickness visible in front elevation |
| Base plate thickness | `base_thick_cm` | 0.5 | 3 | 1 | Foot plate thickness at floor |
| Profile | `profile` | — | — | `"tapered"` | Enum: cylinder, tapered, flared |

### VISION Dimension Tag -> Parameter Mapping

| Vision Tag | Maps To | Notes |
|------------|---------|-------|
| `top_dia` | `top_dia_cm` | Direct; also from `top_diameter_cm` (normalized) |
| `base_dia` | `base_dia_cm` | Also from `base_diameter_cm` (normalized) |
| `neck_dia` | `neck_dia_cm` | Column shaft diameter |
| `collar_dia` | `collar_dia_cm` | Transition collar under the top |
| `height` | `height_cm` | Also from `overall_height_cm` (normalized) |
| `thickness` | `top_thick_cm` | Top slab thickness |
| `top_diameter_cm` | `top_dia_cm` | Normalized by grammar engine |
| `base_diameter_cm` | `base_dia_cm` | Normalized by grammar engine |
| `overall_height_cm` | `height_cm` | Normalized by grammar engine |

---

## Visual Base Estimation (VISUAL_BASE_ESTIMATE)

When no explicit base/neck/collar dimensions are given, estimate using ratios:

### Ratio Reference

| Component | Ratio to top_dia | Practical Range | Example (top=90 cm) |
|-----------|-----------------|----------------|---------------------|
| Collar | `collar_dia / top_dia` | 0.55 – 0.70 | 50–63 cm |
| Neck | `neck_dia / top_dia` | 0.25 – 0.38 | 23–34 cm |
| Base | `base_dia / top_dia` | 0.45 – 0.65 | 41–59 cm |

### Visual Fraction Method

In a product photo, estimate:
1. **Collar fraction:** How wide is the collar plate compared to the full top diameter?
   - Reads as a trapezoid just below the tabletop in front elevation
   - Typical: collar is 55–70% of top_dia
2. **Neck fraction:** How wide is the column shaft at its narrowest?
   - Typical: neck is 25–38% of top_dia
3. **Base fraction:** How wide does the base spread at the floor?
   - Typical: base is 45–65% of top_dia
   - Base is almost always WIDER than the neck

### Default Ratios (when nothing is visible)

```python
# If no base/collar/neck dimensions extracted:
collar_dia_cm = round(top_dia_cm * 0.60)
neck_dia_cm   = round(top_dia_cm * 0.30)
base_dia_cm   = round(top_dia_cm * 0.52)
```

---

## SVG Rendering Rules

The builder generates **three orthographic views** on a single canvas.

### TOP VIEW (Plan)

- **Shape:** True circle at radius `top_dia_cm / 2`, centred at the view centre
- **Circle outline:** Solid line in `OBJECT=#1a1a1a`
- **Wood grain / radial pattern:** 24 radial ray lines emanating from the centre
  to the circle edge, rendered in `HATCH=#94a3b8` — simulates radial wood grain
  or stone veining
- **Centre mark:** Small crosshair (+ symbol) at the circle centre in `CENTER=#2563eb`
- **Diameter dimension:** Single horizontal dimension line across the full diameter,
  labeled `Ø {top_dia_cm} cm` in `DIMENSION=#e6c700`

### FRONT VIEW (Elevation)

From top to bottom, the following components are stacked:

1. **Tabletop rectangle:** `top_dia_cm wide × top_thick_cm tall`
   - Rendered in `OBJECT=#1a1a1a`
2. **Collar trapezoid:** Trapezoid that transitions from `collar_dia_cm` (top edge)
   to `neck_dia_cm` (bottom edge), height approximately 3–5 cm
   - Represents the mounting bracket / transition piece
3. **Neck / column rectangle:** `neck_dia_cm wide × neck_height_cm tall`
   - `neck_height_cm = height_cm - top_thick_cm - collar_h - base_taper_h - base_thick_cm`
4. **Base trapezoid:** Trapezoid that transitions from `neck_dia_cm` (top edge)
   to `base_dia_cm` (bottom edge), height approximately 4–6 cm
5. **Base plate rectangle:** `base_dia_cm wide × base_thick_cm tall` at floor level

**Dimension annotations in FRONT VIEW:**
- **Height dimension:** Vertical leader line on the RIGHT side, from floor to top
  surface, labeled `H = {height_cm} cm`
- **Top diameter:** Horizontal dimension line above the top, labeled `Ø {top_dia_cm} cm`
- **Base diameter:** Horizontal dimension line below the base plate, labeled
  `base_dia = {base_dia_cm} cm`

### SIDE VIEW (Elevation)

- Identical profile to FRONT VIEW — round pedestal tables are radially symmetric
- May show a secondary diameter annotation for the neck

### Layer Color Reference

| Layer | Hex | Usage |
|-------|-----|-------|
| OBJECT | `#1a1a1a` | All solid geometry outlines |
| DIMENSION | `#e6c700` | Dimension arrows, extension lines, text |
| LEADER | `#000000` | Leader lines to note callouts |
| CENTER | `#2563eb` | Centreline crosshair in plan view |
| HATCH | `#94a3b8` | Radial grain lines in plan, column hatch in elevation |

---

## Profile Type Guide

### `cylinder` Profile

- Neck and base diameters are similar (base ≈ neck × 1.1–1.3)
- Column reads as nearly uniform vertical tube
- Common in: modern Scandinavian, industrial, minimal metal frames
- Example: steel tube pedestal, concrete column base

### `tapered` Profile

- Base diameter significantly wider than neck (base ≈ neck × 1.5–2.2)
- Visible outward taper from neck to base gives stability illusion
- Common in: traditional tulip-style, mid-century modern (Eero Saarinen), transitional
- This is the DEFAULT profile

### `flared` Profile

- Neck is very narrow (neck ≈ top_dia × 0.15–0.20)
- Base spreads dramatically (base ≈ top_dia × 0.55–0.70)
- Creates a trumpet-bell or goblet shape
- Common in: Art Deco, luxury/statement pieces, cast iron antique bistro tables

---

## Dimension Extraction Protocol

When reading a product photo:

1. **Confirm circle top:** Verify the top is a true circle in plan view (or described
   as "round" / "circular"). If elliptical, use oval_pedestal_table skill instead.
2. **Read top diameter:** Usually the most prominent dimension given. Look for `Ø`
   symbol or "diameter" / "round" in product description.
3. **Read overall height:** Floor-to-surface measurement.
4. **Estimate collar, neck, base** using the ratio method above if not explicit.
5. **Read or estimate top thickness:** Visible as the slab edge in perspective photos.
6. **Identify profile type** from the visual shape of the pedestal.

### Proportion-Based Estimation Guide

| If you see... | Estimate |
|--------------|----------|
| Thin column, wide spread at floor | `profile="flared"`, neck_ratio ≈ 0.18, base_ratio ≈ 0.62 |
| Smooth outward taper | `profile="tapered"`, neck_ratio ≈ 0.30, base_ratio ≈ 0.52 |
| Nearly parallel column sides | `profile="cylinder"`, neck_ratio ≈ 0.35, base_ratio ≈ 0.42 |
| Heavy cast base, ornate column | Traditional bistro: base_dia ≈ 55 cm, neck_dia ≈ 12 cm |
| Slim modern metal column | Contemporary: base_dia ≈ 40 cm, neck_dia ≈ 8 cm disc base |

---

## Materials Intelligence

### Tabletop Materials

| Material | Visual Cues | Typical top_thick_cm |
|----------|-------------|---------------------|
| Marble (Calacatta, Carrara) | White/grey base with dramatic grey/gold veining | 2–4 |
| Sintered stone (Dekton, Lapitec) | Flat matte/satin, very uniform, no veins | 1.2–2 |
| Porcelain / ceramic | Matte, often large-format tile pattern | 1–2 |
| Tempered glass | Transparent, slight green tint on edge | 1–1.5 |
| Solid timber (oak, walnut) | Clear grain, warm brown tones, visible jointing | 3–5 |
| MDF / lacquered | Perfectly smooth, monochromatic | 2–3 |
| Terrazzo | Speckled aggregate visible, matte finish | 3–5 |

### Base / Pedestal Materials

| Material | Visual Cues | Profile |
|----------|-------------|---------|
| Powder-coated steel (black/white) | Flat uniform colour, sharp crisp edges, matte | cylinder or tapered |
| Brushed gold / antique brass | Warm yellow-gold, directional brush marks | tapered or flared |
| Polished chrome / stainless | High mirror reflectivity, cool silver | cylinder |
| Cast iron (antique) | Very heavy appearance, ornate detailing, dark | flared |
| Turned solid wood | Visible lathe profiles, rounded shoulders | tapered |
| Concrete / stone | Heavy textured grey, monolithic | cylinder |
| Rose gold metal | Warm pinkish metallic, brushed or polished | cylinder or tapered |

---

## Common Mistakes

### 1. Reporting base_dia as a Ratio Instead of cm

**Problem:** AI estimates "the base is about 50% of the top" and reports `base_dia_cm=0.50`
instead of `base_dia_cm=45` (for a 90 cm top).

**Prevention:** Always convert ratios to cm before outputting. If top_dia_cm=90 and
base_ratio=0.50, then `base_dia_cm = 90 × 0.50 = 45`. Never output decimal fractions
for diameter fields.

---

### 2. collar_dia > top_dia (Geometrically Impossible)

**Problem:** The collar plate cannot physically extend beyond the tabletop edge.

**Rule:** `collar_dia_cm < top_dia_cm` ALWAYS.

**Prevention:** Hard cap: `collar_dia_cm = min(collar_dia_cm, top_dia_cm - 5)`

---

### 3. neck_dia > base_dia for Tapered or Flared Profiles

**Problem:** For tapered and flared profiles, the neck (column) is always narrower
than the base (foot). If neck > base, the geometry is inverted (upside-down cone).

**Rule:**
- `profile="tapered"` or `profile="flared"`: `neck_dia_cm < base_dia_cm`
- `profile="cylinder"`: neck ≈ base is acceptable

**Prevention:** If extracted neck > base, swap the values or reconsider which
dimension was labelled which.

---

### 4. Confusing Table Diameter with Table Radius

**Problem:** A photo caption says "radius 50 cm" meaning the table is 100 cm wide,
but AI inputs `top_dia_cm=50`.

**Rule:** The builder parameter `top_dia_cm` is the **full diameter**. If only
a radius is given, multiply by 2.

---

### 5. Wrong Profile Selection Leading to Ugly Geometry

**Problem:** A traditional Saarinen-style tulip table is rendered as `cylinder`,
producing a clunky uniform column instead of the elegant taper.

**Prevention:**
- Always look at the base spread vs column width ratio
- A ratio > 1.8 means the profile should be `tapered` or `flared`
- When unsure, `tapered` is the safest default

---

### 6. Height Outside Dining Range

**Problem:** A dining table is assigned `height_cm=95` (likely a measurement error
or mm-to-cm confusion).

**Rule:** Dining table height must be 68–80 cm. Bar/counter-height tables are
90–105 cm (different builder or variant).

---

### 7. Marble Top Thickness Underestimated

**Problem:** A thick Calacatta marble slab (4 cm) is rendered as `top_thick_cm=1`.

**Rule:** Natural marble and stone tops are typically 2–4 cm. Sintered stone can
be 1.2 cm but is rarely thinner. Glass tops are 1–1.5 cm.

---

## Sanity Checks

| Rule | Condition | Action |
|------|-----------|--------|
| Collar inside top | `collar_dia_cm < top_dia_cm` | Hard cap: collar = top_dia - 5 |
| Neck inside collar | `neck_dia_cm < collar_dia_cm` | Warn, swap if necessary |
| Base >= neck | `base_dia_cm >= neck_dia_cm` | Warn, swap if tapered/flared |
| Height dining range | `68 <= height_cm <= 80` | Flag if outside range |
| Top dia realistic | `60 <= top_dia_cm <= 150` | Flag extremes |
| Ratios coherent | `collar_dia/top_dia` in [0.45, 0.80] | Warn if outside |
| No ratios as values | All dia values > 5 cm | Warn if any diameter < 5 cm |
| Top thickness visible | `top_thick_cm >= 1.2` | Default to 3 cm |

---

## Example Extractions

**Product:** "Round dining table 90 cm diameter, height 74 cm, Calacatta marble top
3 cm thick, matte black powder-coated steel base"

```json
{
  "furniture_type": "round_pedestal_table",
  "top_dia_cm": 90,
  "height_cm": 74,
  "base_dia_cm": 47,
  "neck_dia_cm": 27,
  "collar_dia_cm": 52,
  "top_thick_cm": 3,
  "base_thick_cm": 1,
  "profile": "tapered",
  "top_material": "marble",
  "base_material": "powder-coated steel"
}
```

**Product:** Photo estimation — round table, appears about 80 cm across, café height
(≈74 cm), very thin metal column, wide spread disc base:

```json
{
  "furniture_type": "round_pedestal_table",
  "top_dia_cm": 80,
  "height_cm": 74,
  "base_dia_cm": 42,
  "neck_dia_cm": 16,
  "collar_dia_cm": 46,
  "top_thick_cm": 2,
  "base_thick_cm": 2,
  "profile": "flared",
  "top_material": "sintered stone",
  "base_material": "powder-coated steel"
}
```

**Product:** Classic Saarinen-style tulip table, white, 120 cm diameter, 74 cm tall:

```json
{
  "furniture_type": "round_pedestal_table",
  "top_dia_cm": 120,
  "height_cm": 74,
  "base_dia_cm": 58,
  "neck_dia_cm": 30,
  "collar_dia_cm": 70,
  "top_thick_cm": 2,
  "base_thick_cm": 1,
  "profile": "tapered"
}
```
