---
name: cabinet
description: >
  Guide to identify and parametrically reconstruct storage cabinets and shelving units —
  including sideboards, display cabinets, bookcases, wardrobes, and general-purpose
  carcass-based storage furniture. Covers door count detection, plinth vs leg base
  identification, and correct parameter mapping to build_cabinet_model().
---

# Cabinet Skill

## 1. Identification Clues

A cabinet is a **tall or wide rectangular carcass** with enclosed storage. Look for:

| Visual Feature | What to Look For |
|---|---|
| **Carcass** | Solid rectangular box body — no open frame |
| **Doors** | Flat or panelled rectangles with visible hinges and/or handle hardware |
| **Drawers** | Horizontal banded lines lower in the body, often with small pull handles centred |
| **Plinth base** | A thin recessed toe-kick panel below the carcass (approx 8-15 cm high) |
| **Leg base** | Four short tapered or turned legs at the corners (visible gap below carcass) |
| **Top surface** | Flush or slightly overhanging, sometimes in contrasting material (stone, glass) |
| **Proportions** | Tall >= 120 cm height -> likely storage cabinet / display cabinet / wardrobe |
|  | Wide >= 120 cm, low height 60-90 cm -> likely sideboard / media unit |

### Sub-type Quick Identification

- **Sideboard / Media Unit**: Very wide (120-240 cm), low (60-90 cm), multiple doors + drawers, typically plinth base
- **Display Cabinet / Vitrine**: Tall (160-220 cm), glass-panelled upper doors, solid lower doors, slender proportions
- **Storage Cabinet / Cupboard**: Moderate height (100-200 cm), 1-2 solid doors, deep carcass
- **Bookcase / Open Shelving**: No doors, open-fronted with visible shelves -- still uses build_cabinet_model()
- **Wardrobe**: Very tall (190-220 cm), very wide (120-300 cm) -> delegates internally to build_cabinet_model()

### Do NOT Confuse With

- **Wardrobe**: Use `build_wardrobe_model()` when the piece is full-height bedroom clothing storage (w, d, h short params).
- **Desk with drawers**: Desk top at working height (70-80 cm), open knee space below.
- **Reception counter**: Has a raised transaction top > 90 cm.

---

## 2. Critical Parameters

Builder function:
```python
build_cabinet_model(width_cm=100, depth_cm=50, height_cm=180)
```

> **Parameter normalization**: `overall_height_cm -> height_cm` in grammar/engine.py.

| Parameter | Builder Arg | Min | Typical | Max | Unit | Notes |
|---|---|---|---|---|---|---|
| Width | `width_cm` | 40 | 80-120 | 250 | cm | Measure full external width |
| Depth | `depth_cm` | 30 | 45-55 | 80 | cm | Front-to-back external |
| Height | `height_cm` | 60 | 180-200 | 250 | cm | Floor to top surface |

### Sub-type Typical Dimension Ranges

| Sub-type | Width | Depth | Height |
|---|---|---|---|
| Sideboard | 120-240 cm | 40-55 cm | 60-90 cm |
| Display Cabinet | 60-120 cm | 35-50 cm | 160-220 cm |
| Storage Cabinet | 40-100 cm | 35-55 cm | 100-200 cm |
| Bookcase | 60-120 cm | 25-45 cm | 120-220 cm |

### Door Count Extraction (Vision Tag: `door_count`)

Count door leaves carefully from the front view:
- Single door -> 1 vertical rectangle occupying full or half width
- Double door -> 2 rectangles meeting at the centre line
- 3-door -> 3 equal-width rectangles (common in wide sideboards)
- 4+ doors -> wide unit, count centre gaps between door pairs

> **Common trap**: A centre gap/stile between two doors is NOT a third door. Gaps are structural, doors are the rectangles.

---

## 3. SVG Rendering Rules

The builder generates three orthographic views:

### FRONT VIEW
- **Outer carcass rectangle**: `width_cm x height_cm` -- drawn in OBJECT colour (`#1a1a1a`)
- **Plinth rectangle**: runs the full width at the bottom; height typically 8-12 cm, slightly inset from the carcass sides
- **Door rectangles**: vertically-oriented rects inside the carcass area; number = door_count; divided equally across width
- **Handle dots / pulls**: small filled circle or short horizontal line centred on each door, typically at mid-height or upper third
- **Drawer lines**: horizontal dividing lines in the lower portion if the piece has drawer bank; each drawer has a centred pull line
- **Shelf lines**: faint horizontal lines inside open-shelved units (no fill, OBJECT layer)

### TOP VIEW
- **Footprint rectangle**: `width_cm x depth_cm`
- **Door swing arc** (optional): 90 degree arc from the hinge edge if door swing is shown -- radius = door width
- **Top surface material hatch**: if stone/glass top is specified, cross-hatch the top rect in HATCH colour (`#94a3b8`)

### SIDE VIEW
- **Profile rectangle**: `depth_cm x height_cm`
- **Plinth step**: thin rectangle at the base indicating recessed plinth
- **Back panel line**: thin vertical line 2-3 cm from the rear

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

### Mistake 1: Door Count Off by One
**Cause**: Counting the centre stile as a door, or missing the last door against a side panel.
**Fix**: Count the number of *handle hardware* items visible -- each handle = one door leaf.

### Mistake 2: Swapping Width and Height for Tall vs Wide Units
**Cause**: A sideboard is wider than it is tall, which can trick the model.
**Fix**: Confirm: if height_cm > width_cm it is a TALL cabinet. If width_cm > height_cm it is a WIDE/LOW cabinet (sideboard). Never let height_cm exceed 250 cm.

### Mistake 3: Using Cabinet for Wardrobe
**Cause**: Large bedroom wardrobe looks like a tall cabinet.
**Fix**: If the piece is a full-height bedroom wardrobe (190-220 cm) with sliding or hinged robe doors, use `build_wardrobe_model(w, d, h)` instead.

### Mistake 4: Reporting External Depth as Internal
**Cause**: Product specs sometimes list internal depth (excludes back panel and door thickness).
**Fix**: Add ~4-6 cm to internal depth figure to get external `depth_cm`.

### Mistake 5: Missing Plinth in Height
**Cause**: Some dimension drawings measure from the floor to the underside of the carcass, excluding plinth.
**Fix**: Always use floor-to-top `height_cm`. The builder handles the plinth geometry internally.

### Mistake 6: Glass Door Confusion
**Cause**: Glass-panelled doors may look like open shelves when backlit.
**Fix**: If there is a visible frame around a transparent opening, it is a glass door -- not an open shelf.

---

## 5. Materials Intelligence

| Component | Typical Materials | Visual Cue |
|---|---|---|
| Carcass body | MDF lacquer (matte/gloss), melamine board, plywood | Uniform colour, no grain |
| Door faces | Solid wood veneer, lacquered MDF, glass insert | Wood grain pattern, gloss sheen |
| Top surface | Matching carcass, stone slab, glass | Stone veining, transparency |
| Plinth / base | Painted MDF, solid wood | Slight shadow at floor line |
| Hardware | Brushed steel, brass, matte black | Metallic glint on handles/hinges |
| Shelf edges | PVC edging, solid wood lipping | Thin contrasting strip on exposed edges |

### Material -> SVG Hatch Mapping
| Material | HATCH pattern in SVG |
|---|---|
| Solid wood / veneer | Diagonal line hatch (`#94a3b8`) |
| Stone top | Cross-hatch |
| Glass door | No hatch (transparent, leave outline only) |
| Lacquered MDF | No hatch (solid fill or no fill) |

---

## 6. Dimension Extraction Flow

```
Vision extracts:
  width, depth, height   -> build_cabinet_model(width_cm, depth_cm, height_cm)
  door_count             -> stored in metadata, used for SVG door rect count
  has_drawers            -> boolean flag -> drawer line rendering
  base_type              -> "plinth" | "legs" -> plinth rect or corner leg geometry
  material               -> stored in metadata
```

### Sanity Checks Before Rendering
1. `height_cm <= 250` -- flag if exceeded
2. `width_cm >= depth_cm` -- typical; warn if depth > width (unusual)
3. `height_cm > width_cm` -> tall cabinet subtype
4. `width_cm > 1.5 x height_cm` -> low/wide sideboard subtype
5. `depth_cm >= 30` -- cabinets shallower than 30 cm are display ledges, not cabinets

---

## 7. Example Extraction

**Product**: "3-door sideboard in walnut veneer, W180 x D45 x H75 cm, plinth base"

```yaml
furniture_type: cabinet
sub_type: sideboard
width_cm: 180
depth_cm: 45
height_cm: 75
door_count: 3
has_drawers: false
base_type: plinth
material: walnut_veneer
```

Builder call:
```python
build_cabinet_model(width_cm=180, depth_cm=45, height_cm=75)
```
