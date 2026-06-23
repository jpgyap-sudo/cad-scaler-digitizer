# CAD Intelligence Layer — Architecture Plan

## Problem Statement

The current app is a **line scanner**: image → detect fragmented lines → export as LINE entities in DXF. A round tabletop becomes 12 straight line segments. A rectangle becomes 4 disconnected lines. Dimensions like "80cm DIA" are read but not interpreted.

**Target**: A **shop drawing generator**: image → understand semantically → rebuild as real CAD primitives with correct dimensions, views, and parametric templates.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    GEMINI CAD INTELLIGENCE                    │
│  (One multimodal call — structured output with primitives)   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. OCR & Dimension Reading                                   │
│     "80cm DIA" → { value: 80, unit: "cm", type: "diameter" }│
│     "70cm H"   → { value: 70, unit: "cm", type: "height" }   │
│     "TOP VIEW" → view: "top"                                  │
│                                                              │
│  2. Primitive Detection                                       │
│     circle:   { type: "circle",   center, radius }           │
│     rect:     { type: "rectangle", corners, width, height }  │
│     arc:      { type: "arc",      center, radius, start, end }│
│     polyline: { type: "polyline", points, closed }            │
│     line:     { type: "line",     p1, p2 }                    │
│     centerline: { type: "centerline", p1, p2 }                │
│     dimline:  { type: "dimension", p1, p2, value, unit }     │
│                                                              │
│  3. View Separation                                          │
│     views: [{ view: "top", primitives: [...] },              │
│             { view: "front", primitives: [...] }]             │
│                                                              │
│  4. Parametric Template Matching                              │
│     detected: "round pedestal table"                          │
│     match: table_template { diameter, height }                │
│     override: use measured dimensions                         │
│                                                              │
│  5. Shape Reconstruction                                      │
│     raw lines → clean primitives                              │
│     merge overlapping, snap endpoints                         │
│     remove duplicates, straighten near-h/v lines              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   FRONTEND CAD ENGINE                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Canvas Renderer: draws REAL circles, arcs, rectangles       │
│  Multi-view layout: top, front, side panels                  │
│  Parametric editor: override dimensions inline               │
│  DXF Generator: exports CIRCLE, ARC, LWPOLYLINE entities     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: CAD Primitive Type System

New types in `types.ts`:

```typescript
// === CAD Primitives ===

export type CadPrimitiveType =
  | 'circle'
  | 'arc'
  | 'rectangle'
  | 'polyline'
  | 'line'
  | 'centerline'
  | 'dimension'
  | 'text'
  | 'ellipse';

export interface CadCircle {
  type: 'circle';
  center: Point;
  radius: number;           // in real-world units after calibration
  layer?: string;
  style?: 'solid' | 'hidden' | 'center';
}

export interface CadArc {
  type: 'arc';
  center: Point;
  radius: number;
  startAngle: number;       // radians
  endAngle: number;         // radians
}

export interface CadRectangle {
  type: 'rectangle';
  p1: Point;
  p2: Point;
  width: number;            // real units
  height: number;           // real units
}

export interface CadPolyline {
  type: 'polyline';
  points: Point[];
  closed: boolean;
}

export interface CadLine {
  type: 'line';
  p1: Point;
  p2: Point;
  style?: 'solid' | 'hidden' | 'center' | 'dimension';
}

export interface CadDimension {
  type: 'dimension';
  p1: Point;
  p2: Point;
  value: number;            // real-world measurement
  unit: string;             // "cm", "m", "mm"
  orientation: 'horizontal' | 'vertical' | 'aligned';
}

export interface CadText {
  type: 'text';
  position: Point;
  content: string;
  height?: number;
}

export type CadPrimitive =
  | CadCircle | CadArc | CadRectangle | CadPolyline
  | CadLine | CadDimension | CadText;

// === Drawing Views ===

export interface CadView {
  name: string;             // "TOP VIEW", "FRONT VIEW", "SIDE VIEW"
  scale: number;
  origin: Point;            // where this view starts on the image
  primitives: CadPrimitive[];
}

// === Full CAD Document ===

export interface CadDocument {
  title: string;
  views: CadView[];
  calibration: {
    found: boolean;
    pixelsPerUnit: number;
    originalScale?: string;
  };
  templates: ParametricMatch[];
}

// === Parametric Templates ===

export interface ParametricTemplate {
  name: string;
  type: string;             // "round-table", "rect-table", "sofa", "cabinet", "bed", "chair"
  views: {
    view: 'top' | 'front' | 'side';
    primitives: CadPrimitive[];
    parameters: Record<string, number>;  // template variables
  }[];
  parameters: {
    name: string;
    default: number;
    unit: string;
    description: string;
  }[];
}

export interface ParametricMatch {
  templateName: string;
  parameters: Record<string, number>;   // filled from OCR
  confidence: number;
}
```

---

## Phase 2: Gemini Prompt — Semantic CAD Extraction

Replace the current generic digitization prompt with a structured CAD extraction prompt.

The key insight: **One Gemini call, structured JSON output** containing:
- Detected views with their regions
- Primitives per view (circles, arcs, rectangles, polylines, centerlines)
- Dimension readings with numeric values and units
- Template matches (what is this piece of furniture?)
- Confidence scores per primitive

Prompt architecture:
```
You are a Professional CAD Engineer. Analyze this architectural/furniture drawing.

TASK 1 — VIEW DETECTION
Identify separate drawing views (TOP VIEW, FRONT VIEW, SIDE VIEW, DETAIL).
For each view, determine its bounding box and scale.

TASK 2 — PRIMITIVE DETECTION
For each detected view, extract:
- CIRCLE: center, radius
- ARC: center, radius, startAngle, endAngle
- RECTANGLE: corners, width, height (in real units)
- POLYLINE: point sequence, closed/open
- LINE: p1, p2 (including CENTERLINES and DIMENSION LINES)
- TEXT: position, content, font size

TASK 3 — DIMENSION READING
Read all dimension annotations. Return numeric values with units.
Examples: "80cm DIA" → { value: 80, unit: "cm", meaning: "diameter" }
         "70cm H"   → { value: 70, unit: "cm", meaning: "height" }
         "1:100"    → { scale: 100 }

TASK 4 — TEMPLATE MATCHING
Classify the drawn object into a known template:
- round_pedestal_table
- rectangular_table
- sofa
- cabinet
- bed_headboard
- chair
- custom (if no template matches)

Return as structured JSON matching the CadDocument schema.
```

---

## Phase 3: Frontend CAD Engine

### 3a — CadRenderer Component

Replace the current `Canvas.tsx` SVG polyline renderer with a proper CAD primitive renderer:

```
For each primitive type:
  circle:    ctx.arc(center, radius) — one clean circle
  arc:       ctx.arc(center, radius, startAngle, endAngle)
  rectangle: ctx.rect(p1, width, height)
  polyline:  ctx.moveTo/lineTo sequence
  dimline:   ctx.moveTo + text label + extension lines
  text:      ctx.fillText at position
  centerline: stroke with dash pattern [10, 5]
```

### 3b — Multi-View Panel Layout

```
┌─────────────────────────────────────┐
│  TOP VIEW                           │
│  ┌─────────────────────────────────┐│
│  │   ⭕ circle (80cm DIA)          ││
│  │   ── centerline ──              ││
│  │   ══ dimension 80cm ══          ││
│  └─────────────────────────────────┘│
├─────────────────────────────────────┤
│  FRONT VIEW                          │
│  ┌─────────────────────────────────┐│
│  │  ┌──────────────┐              ││
│  │  │  ████████████ │  70cm H     ││
│  │  └──────────────┘              ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### 3c — DXF Generator Upgrade

Current: only LINE entities.
New: support CIRCLE, ARC, LWPOLYLINE, TEXT, DIMENSION entities with proper DXF group codes.

```dxf
// CIRCLE
  0
CIRCLE
  8
0        // layer
 10
100.0    // center X
 20
200.0    // center Y
 40
40.0     // radius

// ARC
  0
ARC
  8
0
 10
100.0    // center X
 20
200.0    // center Y
 40
40.0     // radius
 50
0.0      // start angle
 51
180.0    // end angle

// LWPOLYLINE
  0
LWPOLYLINE
  8
0
 90
4        // number of vertices
 70
1        // closed flag
 10
0.0      // vertex 1 X
 20
0.0      // vertex 1 Y
 10
100.0    // vertex 2 X
 20
0.0
 10
100.0
 20
100.0
 10
0.0
 20
100.0
```

---

## Phase 4: Parametric Templates

Template definitions stored as JSON. When Gemini detects a template match, the app:
1. Loads the template primitive structure
2. Fills in the dimensions from OCR readings
3. Renders the CAD-perfect version

```json
{
  "name": "round_pedestal_table",
  "parameters": {
    "diameter": { "default": 80, "unit": "cm" },
    "height":   { "default": 70, "unit": "cm" },
    "thickness": { "default": 3, "unit": "cm" },
    "base_diameter": { "default": 50, "unit": "cm" }
  },
  "views": [
    {
      "view": "top",
      "primitives": [
        { "type": "circle", "center": [0,0], "radius": "diameter/2" },
        { "type": "centerline", "p1": [-radius, 0], "p2": [radius, 0] },
        { "type": "centerline", "p1": [0, -radius], "p2": [0, radius] }
      ]
    },
    {
      "view": "front",
      "primitives": [
        { "type": "rectangle", "p1": [-diameter/2, 0], "p2": [diameter/2, thickness], "layer": "tabletop" },
        { "type": "rectangle", "p1": [-base_diameter/2, thickness], "p2": [base_diameter/2, height], "layer": "pedestal" },
        { "type": "rectangle", "p1": [-base_diameter/2, height-5], "p2": [base_diameter/2, height], "layer": "base" },
        { "type": "dimension", "p1": [0, 0], "p2": [0, height], "value": "height" },
        { "type": "dimension", "p1": [-radius, 0], "p2": [radius, 0], "value": "diameter" }
      ]
    }
  ]
}
```

---

## Phase 5: Shape Reconstruction Pipeline

After Gemini returns primitives, run a client-side cleanup pass:

```
1. deduplicatePrimitives()
   - remove circles within 5px of each other
   - remove lines that overlap >80%

2. snapEndpoints()
   - for all polylines/lines, snap endpoints within 10px

3. mergeCollinearLines()
   - merge line segments that share angle (< 2 deg diff)
   - merge into single longer line

4. straightenNearHV()
   - if angle is within 3 deg of horizontal → make horizontal
   - if angle is within 3 deg of vertical → make vertical

5. removeShortPrimitives(threshold: 5px)
   - delete any primitive shorter than threshold in real units
```

---

## Implementation Order

```
Phase 1: CAD Types (est. 1 session)
  - types.ts → add all CadPrimitive, CadView, CadDocument types
  - Remove old AgentResponse/VerificationResult types
  
Phase 2: Gemini Prompt Rewrite (est. 1 session)
  - agent.ts → rewrite digitization prompt for CAD extraction
  - agent.ts → structured output per CadDocument schema
  
Phase 3: CadRenderer (est. 1 session)
  - components/CadCanvas.tsx → new canvas for CAD primitives
  - components/ViewPanel.tsx → multi-view layout
  
Phase 4: DXF Upgrade (est. 1 session)
  - utils/dxf.ts → support CIRCLE, ARC, LWPOLYLINE, TEXT
  
Phase 5: Shape Reconstruction Pipeline (est. 1 session)
  - services/cadCleanup.ts → dedup, snap, merge, straighten
  
Phase 6: Parametric Templates (est. 1 session)
  - templates/*.json → template definitions
  - services/templateMatcher.ts → fill dimensions, generate primitives
  
Phase 7: Integration & Polish (est. 1 session)
  - Wire into App.tsx
  - Verification adapted for CAD quality
  - PostgreSQL schema updated for CadDocument
```

---

## Data Flow (New)

```
User uploads image
  ↓
Gemini CAD Intelligence (one call)
  → CadDocument { views, primitives, calibration, templates }
  ↓
Shape Reconstruction Pipeline
  → dedup, snap, merge, straighten
  ↓
Template Override (if matched)
  → generate CAD-perfect primitives from template
  ↓
Frontend CAD Engine
  → Canvas: render circles/arcs/rects properly
  → ViewPanel: multi-view layout
  → Parametric editor: override dimensions
  ↓
PostgreSQL Brain
  → save CadDocument
  ↓
Export
  → DXF with CIRCLE/ARC/LWPOLYLINE entities
  → Clean, real CAD file
```

---

## Comparison

| Feature | Current App | Target |
|---------|-------------|--------|
| Circle detection | 12 line segments | One CIRCLE primitive |
| View separation | None | TOP/FRONT/SIDE panels |
| Dimension reading | Just text display | Numeric values drive scale correction |
| Templates | None | 6+ furniture templates |
| DXF export | Only LINE entities | CIRCLE, ARC, LWPOLYLINE, TEXT |
| Cleanup | None | Dedup, snap, merge, straighten |
| Parametric editing | None | Override dimensions → auto-update |
