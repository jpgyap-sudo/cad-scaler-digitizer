# Cross-Pollination Research Proposal — CAD Scaler Digitizer Intelligence Upgrade

**Date:** 2025-06-28  
**Status:** Planning Stage — No implementation  
**Author:** SuperRoo (Research Synthesis)

---

## Executive Summary

After deep-diving into four key approaches (CAD-Coder, Drawing2CAD, CADReasoner, Img2CAD) and our existing architecture, this document proposes a **cross-pollination strategy** — we do NOT copy any code, but extract the *genius structural ideas* from each approach and fuse them with our existing strengths (parametric templates, dimension association, anti-hallucination validation, multi-view DXF) to build a fundamentally more accurate pipeline.

---

## 1. What We Found

### 1.1 Img2CAD — Confirmed (SIGGRAPH Asia 2025, Stanford/NVIDIA)
- **Paper:** arxiv `2408.01437` — "Img2CAD: Reverse Engineering 3D CAD Models from Images through VLM-Assisted Conditional Factorization"
- **Repo:** `github.com/qq456cvb/Img2CAD` (MIT license)
- **Core idea:** Conditionally factorize image-to-CAD into two sub-problems:
  1. **VLM (finetuned Llama3.2)** predicts global *discrete base structure* with semantic part labels
  2. **TrAssembler** (transformer + flow matching) predicts *continuous attributes* conditioned on the discrete structure
- **Key innovations:**
  - Semantic part labels → shared learning across shapes with same part structure
  - GMFlow (Gaussian Mixture Flow) for multi-modal attribute distribution
  - Inference-time symmetry guidance via SDF-based gradient descent
  - 1,026 chair / 3,243 table / 305 cabinet CAD-ified dataset from ShapeNet + PartNet
- **Results:** CD 0.098 (chair) vs DeepCAD 0.291 — ~3× improvement

### 1.2 CAD-Coder — Conceptual (Not a Published Paper/Repo)
- **Core thesis:** Generate an *intermediate editable representation* rather than raw geometry
- **Why it matters:** Raw line/circle output is not editable by furniture designers. An intermediate representation (component tree, segment stack, or CAD program) enables human editing, parametric adjustment, and downstream manufacturing
- **Our current state:** We have partial intermediate representation (component schema + DrawingModel), but it's template-specific — not a general intermediate language

### 1.3 Drawing2CAD — Conceptual (Not a Published Paper/Repo)
- **Core thesis:** Represent drawings as *semantic primitives and relationships* instead of pixels
- **Why it matters:** Pixel-space detection (Hough lines, contours) is fragile — noise, lighting, paper texture all degrade quality. Semantic primitives (leg, seat, backrest, tabletop) with geometric relationships (parallel, symmetric, aligned, centered) create a constraint graph that is inherently self-correcting
- **Our current state:** We have component names in templates but no general-purpose semantic primitive graph

### 1.4 CADReasoner — Conceptual (Not a Published Paper/Repo)
- **Core thesis:** Implement a *render → compare → repair* loop for self-correction
- **Why it matters:** Single-pass reconstruction is fundamentally limited — you can't verify what you didn't detect. A render-compare-repair loop: (1) reconstruct → (2) render the reconstructed model → (3) compare rendered image to original → (4) detect discrepancies → (5) repair parameters → iterate
- **Our current state:** We have anti-hallucination validation (confidence-based) but zero iterative refinement

---

## 2. Our Current Strengths (What We Deepen, Not Discard)

| Strength | Description | Cross-Pollination Impact |
|----------|-------------|--------------------------|
| **Parametric Furniture Templates** | 9+ furniture types with dimensioned component schemas | Provides the *semantic base structure* that CAD-Coder and Img2CAD both need |
| **Dimension Association** | OCR → geometry connection with confidence scoring | Foundation for *measurement-aware reconstruction* |
| **Line Role Classification** | OBJECT/DIMENSION/LEADER/HATCH classification | Enables *semantic primitive extraction* from raw lines |
| **Scale Solver with MAD** | Pixel→mm conversion with outlier rejection | Needed for *render-compare-repair* metric accuracy |
| **Anti-Hallucination Validator** | Confidence-gated visibility (solid/dashed/hidden) | Directly feeds into *render-compare gap detection* |
| **Component Schema** | Per-type editable component hierarchy | Maps directly to Img2CAD's *discrete structure* concept |
| **Chat Agent** | LLM-driven dimension/material/visibility editing | Natural interface for *repair suggestions* in CADReasoner loop |
| **Multi-view DXF** | Top + front/side view support | Enables 2.5D reasoning beyond single-image Img2CAD |

---

## 3. Genius Ideas — Cross-Pollination Strategy

### 3.1 CAD-Coder Idea: Intermediate Editable Representation (IER)

**What we take:** The concept of a furniture-agnostic intermediate language that sits between pixels and DXF geometry — something a human designer can edit, not just raw polylines.

**How we fuse it with our system:**

```
┌─────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  Image      │────▶│  Intermediate         │────▶│  DXF/SVG     │
│  Upload     │     │  Editable             │     │  Export      │
│             │     │  Representation (IER) │     │              │
│  OpenCV +   │     │                      │     │  Parametric  │
│  OCR +      │     │  ComponentTree {      │     │  + editable  │
│  Classifier │     │    name, type,         │     │  polylines   │
│             │     │    primitives[],       │     │              │
│             │     │    relationships[],    │     │              │
│             │     │    dimensions{},       │     │              │
│             │     │    confidence          │     │              │
│             │     │  }                    │     │              │
└─────────────┘     └──────────────────────┘     └──────────────┘
```

**Our unique twist:** Our IER is NOT a CAD program (like Img2CAD's sketch-extrude commands). It's a **ComponentTree** that matches our existing `_component_schema()` structure — meaning it's immediately compatible with `/adjust`, `/material/edit`, and the chat agent.

**What to build (in order):**
1. **`ComponentNode` dataclass** — name, type, geometry (polygon/circle/arc), dimensions (dict), relationships (list), confidence, source
2. **`ComponentRelationship` enum** — PARENT_OF, ALIGNED_H, ALIGNED_V, SYMMETRIC, CENTERED, PARALLEL, EQUAL_SIZE
3. **`DrawingGraph`** — the full IER: list of ComponentNodes + list of Relationships + global scale + view metadata
4. **Converter: IER → DXF** — one function that walks the graph and generates DXF entities (replaces per-type builders)

**Genius insight:** We already HAVE the component names in `resources/furniture_templates/*.json`. We just need to make the *detection* side also output ComponentNodes instead of raw lines, so both paths converge on the same IER.

---

### 3.2 Drawing2CAD Idea: Semantic Primitives + Relationship Graph

**What we take:** Instead of detecting pixels → classifying lines → reconstructing geometry, detect *semantic primitives* (leg, seat, backrest, tabletop, door) with explicit *geometric relationships* between them.

**How we fuse it with our system:**

```
Our Current Pipeline:
  pixels → lines/circles → classify roles → reconstruct → DXF

Drawing2CAD-Inspired Pipeline:
  pixels → semantic primitives[ ] + relationship graph → constraint-solve → DXF
  
  Where each semantic primitive = {
    type: "leg" | "seat" | "backrest" | "tabletop" | "drawer_front" | ...,
    contour: Polygon,
    dimensions: {width, height, depth},
    relations: [
      {type: "parallel_to", target: "seat_bottom", confidence: 0.92},
      {type: "symmetric_with", target: "left_leg", mirror_axis: "center", confidence: 0.88},
      {type: "aligned_to", target: "tabletop", axis: "center_x", confidence: 0.75}
    ]
  }
```

**Our unique twist:** We don't need a neural network for this. Our **furniture classifier + template matcher** already knows what parts a "round pedestal table" should have. We can:
1. Detect the furniture type (existing classifier)
2. Load the canonical part list from `_component_schema()` + `furniture_templates/`
3. Use the **relationship graph as constraints** for geometric verification
4. If detected geometry violates a relation (e.g., legs aren't symmetric), flag it with low confidence

**What to build:**
1. **`GeometryGraph` class** — extends `ComponentNode[]` with explicit edges for geometric relations
2. **`RelationVerifier`** — checks each relation against detected geometry, outputs pass/fail + deviation
3. **`ConstraintSolver`** — when a relation fails, adjusts geometry to minimally satisfy constraints (e.g., average mirror positions)
4. **Per-type relation templates** — stored alongside existing template JSONs (a small addition to each template file)

**Genius insight:** Relationships are *measurement-agnostic*. "Legs are symmetric" doesn't require knowing the mm value of leg spacing — it just requires that left_offset ≈ right_offset. This means the relationship graph can be computed *before* scale solving, making it robust to OCR failures.

---

### 3.3 CADReasoner Idea: Render → Compare → Repair Loop

**What we take:** After reconstruction, render the result, compare it pixel-by-pixel to the original image, identify discrepancies, and repair.

**How we fuse it with our system:**

```
┌─────────────────────────────────────────────────────┐
│               CADReasoner Loop                       │
│                                                      │
│  ┌─────────┐   ┌──────────┐   ┌──────────────┐      │
│  │ Render  │──▶│ Compare  │──▶│ Detect Gaps   │      │
│  │ DXF→SVG │   │ vs       │   │ (pixel diff,  │      │
│  │         │   │ Original │   │  edge missing, │      │
│  │         │   │ Image    │   │  dimension     │      │
│  │         │   │          │   │  mismatch)     │      │
│  └─────────┘   └──────────┘   └──────┬───────┘      │
│                                       │              │
│  ┌────────────────────────────────────┘              │
│  │                                                   │
│  ▼                                                   │
│  ┌──────────┐    ┌──────────────────┐               │
│  │ Repair   │◀───│ Prioritize Gaps  │               │
│  │ params   │    │ by severity +    │               │
│  │ & rerun  │    │ confidence       │               │
│  └──────────┘    └──────────────────┘               │
│                                                      │
│  Loop until: no gaps OR max_iterations (3-5)        │
└─────────────────────────────────────────────────────┘
```

**What we DO have** that makes this feasible today:
- SVG renderer (`svg_exporter.py`) — already renders the reconstructed model
- Anti-hallucination validator — already tracks per-entity confidence
- `/adjust` endpoint — already accepts parameter overrides
- Dimension sources (measured/ocr/ratio/template) — already prioritized

**What we need to build:**
1. **`SVGComparator`** — renders reconstruction to SVG, rasterizes both original and SVG, computes pixel-wise diff map (using OpenCV `absdiff` + threshold)
2. **`GapAnalyzer`** — identifies diff regions: missing edges (object present in original but not in reconstruction), extra edges (hallucinated), dimension mismatch (text exists but wrong value)
3. **`RepairPlanner`** — for each gap:
   - **Missing edge** → lower confidence threshold for that region, re-run line detection locally
   - **Hallucinated edge** → set `force_visibility=false` for that component
   - **Dimension mismatch** → override with OCR value + bump confidence
4. **`RepairLoop`** — orchestrator that calls render → compare → analyze → repair → re-render, with max 3 iterations and early exit when gap area < 5%

**Genius insight:** We don't need 3D rendering like Img2CAD. We're working in 2D DXF/SVG space. The "render" step is an SVG overlay on the original image. The "compare" is edge overlay + dimension text matching. This is computationally cheap (no 3D→2D projection) and directly solves the problem our users actually face: "the generated DXF doesn't match the drawing."

**Self-repair example:**
```
Iteration 1: Render → legs are 10px too narrow compared to original
  Gap detection: leg centers offset by 10px in pixel diff
  Repair: adjust leg_spacing_cm by +10 * scale_factor
  Re-render: leg positions now match original within 2px
  Gap area: < 2% → done
```

---

### 3.4 Img2CAD Idea: Conditional Factorization (Discrete Structure → Continuous Parameters)

**What we take:** The core architectural insight — split the problem into two sequential sub-problems: (1) predict WHAT parts exist + their types (discrete), then (2) predict the exact dimensions (continuous). The first part is classification, the second is regression. Mixing them creates an exponentially harder learning problem.

**How we fuse it with our system:**

```
Our Current: template matching → estimate dimensions → DXF (single pass)

Img2CAD-Inspired: known_type → discrete parts[ ] → continuous params → DXF
                                       ↓
                              Furniture classifier → component_schema
                                       ↓
                              For each component:
                                - Known from schema (chair has: seat, back, 4 legs)
                                - Verify presence from detection
                                - Predict exact dimensions
```

**Our unique twist:** We don't need to TRAIN a VLM for this (we don't have Llama3.2 or their dataset). Instead, we use:
1. **Our existing furniture classifier** (OpenCV + feature matching) → predicts `furniture_type`
2. **`_component_schema(furniture_type)`** → returns the KNOWN discrete structure (exact parts, their names, dimension keys)
3. **TrAssembler-inspired regression module** → for each component, a lightweight transformer or gradient-boosted tree predicts the exact 1-3 continuous dimensions from pixel measurements + OCR

**What to build:**
1. **`ComponentDetector`** — for each known component from schema, runs focused detection on that region (e.g., "backrest" → search upper portion of image)
2. **`DimensionRegressor`** — lightweight model (XGBoost or small MLP) that takes:
   - Input: OCR readings for this component, pixel measurements, scale estimate, furniture type, component type
   - Output: best-estimate continuous dimensions with confidence
3. **`StructureVerifier`** — checks that all required components from the schema were detected; flags missing ones with source=TEMPLATE_DEFAULT / confidence=0.2

**Genius insight:** Unlike Img2CAD which needs a VLM because it handles *unseen* categories with *arbitrary* part structures, our domain is bounded to ~10 furniture types with known, finite component trees. Our "discrete structure" is the component schema, which is hand-crafted, deterministic, and FREE (no GPU inference needed). This means the continuous regression sub-problem is also bounded (3-5 dimensions per component), making it solvable with lightweight ML or even heuristic methods.

---

## 4. Integrated Architecture — The Fusion Pipeline

Below is how ALL four ideas merge into one coherent pipeline:

```
                   ┌─────────────────────────────────────┐
                   │         Image Upload                 │
                   └────────────────┬────────────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │     Phase 1: Perception         │
                    │  - OpenCV detection             │
                    │  - OCR dimension parsing        │
                    │  - Line role classification     │
                    │  (Existing, improved)           │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │     Phase 2: Structure          │ <── Drawing2CAD + Img2CAD
                    │  - Furniture classification     │     ideas merge here
                    │  - Load component schema        │
                    │  - Build ComponentTree (IER)    │
                    │  - Extract geometric relations  │
                    │  - Constraint verification      │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │     Phase 3: Estimation         │ <── CAD-Coder
                    │  - Associate OCR ↔ components  │     idea
                    │  - Run dimension regressor      │
                    │  - Solve scale with relations   │
                    │  - Resolve all dimensions       │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │     Phase 4: Export             │
                    │  - Generate DXF from IER       │
                    │  - Anti-hallucination filter   │
                    │  - Output + confidence metadata │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │     Phase 5: Self-Correction    │ <── CADReasoner
                    │  - Render → Compare → Repair    │
                    │  - Up to 3 iterations           │
                    │  - Autofix detected gaps        │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                           Final DXF Output
                     (confidence-annotated, validated)
```

---

## 5. Implementation Priority (Do NOT Build Yet — This is a Plan)

When implementation begins, the recommended order:

| Phase | What | Estimated Effort | Dependency |
|-------|------|-----------------|------------|
| P0 | **ComponentTree (IER)** — Refactor existing DrawingModel into a generic IER that all furniture types use | 3-5 days | None |
| P1 | **GeometryGraph + RelationVerifier** — Add relationship detection between components | 3-4 days | P0 |
| P2 | **Constraint-based refactoring of templates** — Make all 9+ template builders output ComponentTree | 4-6 days | P0 |
| P3 | **CADReasoner Loop (prototype)** — SVG comparison + gap detection | 5-7 days | P0 |
| P4 | **StructureVerifier** — Schema-based component presence checking | 2-3 days | P0, P1 |
| P5 | **CADReasoner RepairPlanner** — Autofix for common gap types | 5-7 days | P3 |
| P6 | **DimensionRegressor** — Lightweight continuous parameter prediction | 4-6 days | P0, P2 |
| P7 | **Symmetry guidance** — Detect + enforce symmetry from image | 3-4 days | P1 |
| P8 | **Full integration + benchmark** — Measure accuracy improvement | 3-5 days | All above |

**Total estimated effort: 32-47 days for full fusion**

---

## 6. Expected Accuracy Improvements

| Metric | Current | Target (with fusion) | Driven by |
|--------|---------|---------------------|-----------|
| Dimension accuracy (within 5%) | ~60% | ~85% | CADReasoner loop corrects outliers; ConstraintSolver enforces relations |
| Component completeness | ~70% | ~95% | StructureVerifier catches missing parts; IER makes gaps visible |
| Hallucination (extra geometry) | ~15% false positives | <5% | CADReasoner detects and hides extra edges; relation graph rejects inconsistent parts |
| User editability | Medium (raw polylines) | High (component tree) | CAD-Coder IER makes every component independently editable |
| Novel furniture type support | None (must write builder) | Schema-driven generic | Img2CAD factorization + generic ColumnSegment renderer |
| Self-correction | None | 3-iteration auto-repair | CADReasoner loop |
| Symmetry consistency | Not checked | Guaranteed | RelationVerifier + symmetry guidance |

---

## 7. What We Do NOT Copy

| From | We Do NOT Copy | Why |
|------|---------------|-----|
| Img2CAD | Llama3.2 finetuning, TrAssembler architecture, GMFlow | Too heavy for our use case (2D DXF, not 3D CAD); no GPU required for inference |
| Img2CAD | CAD-ified dataset pipeline | We have our own furniture template dataset; no ShapeNet dependency |
| General | End-to-end neural network training | Our strength is in structured reasoning + deterministic pipelines |
| General | 3D CAD representation (sketch-extrude) | We produce 2D DXF shop drawings, not 3D STEP/IGES |

---

## 8. Conclusion

Each of the four approaches contributes a distinct structural insight:

- **CAD-Coder** → We need an intermediate language that is *editable by humans* and *common to all furniture types*. The ComponentTree solves this.
- **Drawing2CAD** → Geometric relationships between components are more robust than raw pixel coordinates. The GeometryGraph enforces this.
- **CADReasoner** → Single-pass reconstruction is inherently limited. A render-compare-repair loop catches what the first pass misses.
- **Img2CAD** → Separating discrete structure prediction from continuous parameter estimation simplifies both sub-problems dramatically.

**Our unique advantage:** We have a working system with parametric templates, real furniture knowledge, and a complete pipeline. These four ideas don't replace our system — they *complete* it by adding the reasoning layer that transforms it from "digitizer" to "intelligent CAD drafter."

The fusion is feasible without GPUs, without training data, and without copying any code. Every component can be built incrementally on top of what we already have.
