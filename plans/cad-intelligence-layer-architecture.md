# CAD Intelligence Layer — Architecture Document

## Overview

The CAD Intelligence Layer transforms raw image pixels into accurate, dimensionally-correct DXF shop drawings. It replaces template-based guessing with measurement-based reconstruction.

## Architecture

```
Image Upload
    │
    ├── OpenCV Pipeline ────┬── detect_lines() → normalize_lines()
    │                       ├── detect_circles() → HoughCircles
    │                       └── detect_rectangles() → contour approx
    │
    ├── OCR Pipeline ───────┬── OpenAI GPT-4o Vision (primary)
    │                       └── Tesseract (fallback)
    │
    └── Accuracy Core (NEW) ─ (5 modules, run in sequence)
         │
         ├── 1. OCR Layout Parser
         │    └── extract_layout() → TextBox[] with positions
         │
         ├── 2. Line Role Classifier
         │    └── classify_line_roles() → OBJECT/DIMENSION/LEADER/CENTER/...
         │
         ├── 3. Dimension Associator
         │    └── associate_dimensions() → text↔geometry pairs
         │
         ├── 4. Scale Solver
         │    └── compute_scale() → px_per_cm with outlier rejection
         │
         └── 5. Geometry Reconstructor
              └── reconstruct() → closed contours, circles, axes
    │
    ├── Furniture Classifier → normalize type + confidence
    ├── Visual Ratio Scaler → priority-ordered component estimates
    └── DXF Exporter → template-based or generic fallback
```

## Module Details

### Phase 1: Accuracy Core (5 modules)

#### 1a. `ocr_layout_parser.py`

**Purpose**: Enhanced OCR that preserves text box positions, orientation, units, and classification.

**Key outputs**:
- `TextBox` — text + bounding box (x, y, w, h) + confidence
- `LayoutParseResult` — categorized boxes by type (DIMENSION_LABEL, MATERIAL_NOTE, TITLE_BLOCK, CENTERLINE_MARK)

**Classification rules**:
- Centerline marks → regex `^(?:CL|C\.L|CENTER|AXIS)`
- Dimension labels → numbers + units (cm/mm/m) or diameter symbols
- Material notes → wood, metal, glass, fabric, etc.
- Title block → scale, revision, project, client, etc.

#### 1b. `dimension_associator.py`

**Purpose**: The "dimension graph" — connect each OCR text box to the geometry it measures.

**Algorithm**:
1. Find dimension lines (arrowheads at both ends OR thin line with extension lines)
2. For each dimension label → find nearest dimension line
3. Find extension lines (perpendicular to dim line at both ends)
4. Find object lines near extension lines (the measured edge)
5. For diameter labels → find nearest circle
6. Score each association by proximity + geometric alignment

**Confidence scoring**:
- 0.85+ : Both extension lines visible + object lines nearby
- 0.70 : One extension line + nearby object lines
- 0.50 : Dimension line matched but no extension lines
- 0.20 : No dimension line found (pure proximity guess)

#### 1c. `line_role_classifier.py`

**Purpose**: Classify EVERY line segment by its CAD role.

**Roles**: OBJECT_EDGE | DIMENSION_LINE | EXTENSION_LINE | LEADER | CENTERLINE | HATCH | TITLE_BLOCK | HIDDEN

**Signals used**:
1. Arrowheads: both ends → DIMENSION, one end → LEADER
2. Line length: short < 15px → HATCH, long > 100px → OBJECT_EDGE
3. Text proximity: near numeric value → DIMENSION, near material note → LEADER
4. Angle: ~45° → HATCH, near-perpendicular to dim line → EXTENSION
5. Texture pattern: groups of parallel short lines → HATCH

#### 1d. `scale_solver.py`

**Purpose**: Compute pixel→cm scale from confirmed dimension pairs.

**Algorithm**:
1. Collect (pixel_length, cm_value) pairs from confident associations
2. Separate into horizontal vs. vertical pairs (anisotropic scaling)
3. Reject outliers using Median Absolute Deviation (MAD)
4. Compute combined, X, and Y scale factors
5. Apply scale to resolve all dimension values

**Outlier rejection**: MAD threshold = 3.0, requires ≥ 3 samples for robust estimate

**Priority chain for every dimension**:
1. MEASURED: pixel_length / confirmed_px_per_cm
2. OCR_CONFIRMED: dimension label text from image
3. INFERRED: pixel_length / estimated_px_per_cm
4. RATIO: standard furniture proportion ratios
5. TEMPLATE_DEFAULT: last resort

#### 1e. `geometry_reconstructor.py`

**Purpose**: Snap, merge, and close contours from raw vision lines.

**Pipeline**:
1. Snap near-parallel collinear lines → continuous segments
2. Snap endpoints to near-right-angle corners → closed shapes
3. Extract closed contours from adjacency graph → polygons
4. Verify circles by checking supporting points on circumference
5. Detect symmetry axes from bounding boxes + centerlines

## Data Flow

```
Uploaded Image
    │
    ▼
OpenCV Detection (lines, circles, rects)
    │
    ▼
OCR Layout Parser (dimension_labels with positions)
    │
    ▼
Line Role Classifier (object_edges, dimension_lines, etc.)
    │
    ▼
Dimension Associator (text ↔ geometry pairs)
    │
    ▼
Scale Solver (px_per_cm from confident pairs)
    │
    ▼
Geometry Reconstructor (clean contours)
    │
    ▼
Visual Ratio Scaler (component estimates, ratio fallback)
    │
    ▼
Anti-Hallucination Validator (per-entity confidence)
    │
    ▼
DXF/SVG/PDF Export (template-matched or generic)
```

## Confidence Metadata

Every DXF entity carries:

```json
{
  "source": "measured_from_pixels | ocr_confirmed | user_confirmed | ratio_estimated | default_template",
  "confidence": 0.85,
  "evidence": ["ocr_box_id:12", "line_id:45", "scale_factor:0.5_px_per_cm"]
}
```

## Anti-Hallucination Rules

| Confidence | Visibility | Drawing |
|-----------|-----------|---------|
| >= 0.70   | VISIBLE   | Solid line on OBJECT layer |
| 0.30-0.70 | ESTIMATED | Dashed line on HIDDEN layer, labeled "EST." |
| < 0.30    | UNKNOWN   | NOT DRAWN, listed in rejected_entities |

## Dimension Source Display (Frontend)

| Source | Color | Label |
|--------|-------|-------|
| measured | Green (#22c55e) | 📏 Measured from pixels |
| ocr_confirmed | Blue (#3b82f6) | 👁️ Read from drawing |
| user_confirmed | Purple (#8b5cf6) | ✏️ User confirmed |
| ratio_estimated | Amber (#f59e0b) | 📐 Estimated from proportions |
| default_template | Red (#ef4444) | ⚠️ Template default — verify! |

## Production Readiness Score

Current: **7/10** (was 5.5/10)

- ✅ Dimension association + scale solver working
- ✅ Line role classification separating geometry from annotations
- ✅ Confidence metadata on every entity
- ❌ Human correction UI (click-to-assign dimensions)
- ❌ Automated accuracy benchmark suite
- ❌ Real test dataset with ground truth DXF files

Next phase target: **8-9/10** with correction UI + benchmarks.
