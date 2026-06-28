# Cross-Pollination Architecture Plan — CAD Scaler Digitizer Intelligence Upgrade

**Status:** Planning Stage — No implementation  
**Derived from:** Research on Img2CAD (SIGGRAPH Asia 2025) + conceptual patterns (CAD-Coder, Drawing2CAD, CADReasoner)  
**See also:** [`plans/research-cross-pollination-proposal.md`](plans/research-cross-pollination-proposal.md) (proposal), [`plans/cad-intelligence-layer-architecture.md`](plans/cad-intelligence-layer-architecture.md) (existing), [`docs/architecture-ai-cad-drafter.md`](docs/architecture-ai-cad-drafter.md) (AI drafter)

---

## 1. Current Architecture

### 1.1 Pipeline Overview

```
Uploaded Image (PNG/JPEG/PDF)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Perception Core                                    │
│                                                              │
│  ┌─────────────────┐   ┌──────────────────┐                  │
│  │ OpenCV Detection │   │ OCR Parsing      │                  │
│  │ - Hough lines    │   │ - Tesseract dims  │                  │
│  │ - Hough circles  │   │ - GPT-4o Vision   │                  │
│  │ - Contour rects  │   │ - Dimension labels│                  │
│  └────────┬────────┘   └────────┬─────────┘                  │
│           │                     │                            │
│           ▼                     ▼                            │
│  ┌─────────────────┐   ┌──────────────────┐                  │
│  │ Line Role Class.│   │ Dimension Assoc.  │                  │
│  │ OBJECT/DIM/     │   │ text ↔ geometry   │                  │
│  │ LEADER/HATCH    │   │ with confidence   │                  │
│  └────────┬────────┘   └────────┬─────────┘                  │
│           │                     │                            │
│           └──────────┬──────────┘                            │
│                      ▼                                       │
│           ┌──────────────────────┐                           │
│           │ Scale Solver (MAD)   │                           │
│           │ px_per_cm + outliers │                           │
│           └──────────┬───────────┘                           │
└──────────────────────┼───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 2: Classification + Template                           │
│                                                               │
│  ┌────────────────────────────┐  ┌────────────────────────┐  │
│  │ Furniture Classifier       │  │ Template Graph System   │  │
│  │ (ML + feature matching)    │  │ 18+ furniture types     │  │
│  │ → normalized type + conf   │  │ JSON schemas + dim maps │  │
│  └───────────┬───────────────┘  └───────────┬────────────┘  │
│              │                              │                │
│              └──────────────┬───────────────┘                │
│                             ▼                                │
│              ┌──────────────────────────────┐                │
│              │ Unified Router (3-track fusion)│               │
│              │ Track A: AI Vision           │                │
│              │ Track B: OpenCV+OCR Pipeline  │                │
│              │ Track C: Template Graph       │                │
│              │ → ProvenanceValue per field   │                │
│              └──────────┬───────────────────┘                │
└─────────────────────────┼────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 3: IER + Export                                        │
│                                                               │
│  ┌──────────────────────────┐  ┌──────────────────────────┐  │
│  │ DrawingModel (IER)       │  │ drawing_builders.py      │  │
│  │ View[] → CircleComponent │  │ 18+ per-type builder fns │  │
│  │ PolygonComponent...      │  │ Each → DrawingModel       │  │
│  │ EntityMetadata on EVERY  │  │                           │  │
│  │ entity (source,conf,evid)│  │                           │  │
│  └──────────┬───────────────┘  └──────────┬───────────────┘  │
│             │                             │                  │
│             └──────────┬──────────────────┘                  │
│                        ▼                                     │
│  ┌─────────────────────────┐   ┌─────────────────────────┐  │
│  │ SVG Exporter            │   │ DXF Exporter            │  │
│  │ (browser preview)       │   │ (downloadable file)     │  │
│  │ _svg_polygon, _svg_line │   │ _save_* per type        │  │
│  └─────────────────────────┘   └─────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌──────────────────────────┐
              │ Anti-Hallucination Valid │
              │ conf ≥ 0.70 → VISIBLE     │
              │ 0.30-0.70 → DASHED        │
              │ conf < 0.30 → HIDDEN      │
              └──────────────────────────┘
                          │
                          ▼
              ┌──────────────────────────┐
              │ Frontend UI              │
              │ - CadCanvas SVG          │
              │ - SliderPanel edit dims  │
              │ - ChatBox agent          │
              │ - ConfidencePanel        │
              │ - /adjust + /material    │
              └──────────────────────────┘
```

### 1.2 Existing Modules

| Module | File | Role |
|--------|------|------|
| **cad_intelligence Pipeline** | `cad_intelligence/pipeline.py` | Sequential: OCR → line detect → line classify → dimension associate → scale solve → geometry reconstruct |
| **PipelineResult** | `cad_intelligence/models.py` | OCRDimension[], DetectedLine[], DetectedCircle[], DimensionAssociation[], ScaleSolution, CadEntity[] |
| **ComponentGraph** | `cad_intelligence/component_graph.py` | Groups CadEntity[] into ComponentNode[] by spatial proximity + heuristics |
| **UnifiedRouter** | `cad_intelligence/unified_router.py` | 3-track fusion (AI Vision / OpenCV+OCR / Template) with ProvenanceValue per field |
| **DrawingModel** | `drawing_model.py` | IER: View[] with Circle/Polygon/Line/Text/Dimension/Leader/HatchComponent. EntityMetadata on every entity |
| **drawing_builders** | `drawing_builders.py` | 18+ `build_X_model()` functions each producing a DrawingModel |
| **dxf_exporter** | `dxf_exporter.py` | 18+ `save_X()` functions for DXF output |
| **svg_exporter** | `svg_exporter.py` | DrawingModel → SVG for browser preview |
| **anti_hallucination_validator** | `anti_hallucination_validator.py` | Confidence-gated visibility (solid/dashed/hidden) |
| **chat_agent** | `chat_agent.py` | LLM-driven dimension/material/visibility/merge editing |
| **scale_solver** | `scale_solver.py` | MAD outlier rejection, priority chain: measured > ocr > inferred > ratio > template |
| **dimension_associator** | `dimension_associator.py` | text↔geometry matching with confidence scoring |
| **line_role_classifier** | `line_role_classifier.py` | OBJECT/DIMENSION/LEADER/HATCH role assignment |
| **resource_engine** | `resource_engine/` | Template loading, closed-loop learning, validation pipeline |
| **cad_kernel** | `cad_kernel/` | Spatial index, hidden line, section generator, annotation engine, learning engine, sheet layout, view generator |
| **furniture_classifier** | `furniture_classifier.py` | ML-based furniture type classification |
| **reference_ratio_solver** | `cad_intelligence/reference_ratio_solver.py` | Missing dimension estimation from part ratios |

### 1.3 Current Accuracy (Estimated)

| Metric | Current | Source |
|--------|---------|--------|
| Dimension accuracy within 5% | ~60% | Estimated from benchmark runs |
| Component completeness | ~70% | Template matching covers known types |
| Hallucination (extra geometry) | ~15% | Anti-hallucination filter catches some |
| User editability | Medium | Raw polylines, component names on some |
| Self-correction | None | Single-pass only |
| Symmetry consistency | Not checked | No symmetry enforcement |

---

## 2. Five Fusion Phases

### Phase A: IER Refactor — Furniture-Agnostic ComponentTree (CAD-Coder)

**Motivation:** The current DrawingModel is templated per-type. We need a generic intermediate representation that all furniture types produce, enabling cross-type operations (merge, repair, relationship extraction).

#### Module: `component_tree.py` (NEW)

```python
@dataclass
class ComponentNode:
    """A named, typed furniture component with geometry + relationships."""
    id: str                          # UUID
    name: str                        # "tabletop", "leg_1", "backrest"
    component_type: str              # "top", "support", "panel", "door", "drawer", "arm", "seat", "leg", etc.
    view: str                        # "top", "front", "side"
    geometry: ComponentGeometry      # polygon/circle/arc primitives
    dimensions_mm: Dict[str, float]  # resolved dimensions
    confidence: float
    source: str                      # "measured" | "schema" | "inferred"
    relations: List[ComponentRelation]

@dataclass
class ComponentRelation:
    """Explicit geometric relationship between two components."""
    type: str                        # "PARENT_OF" | "ALIGNED_H" | "ALIGNED_V" | "SYMMETRIC" | "CENTERED" | "PARALLEL" | "EQUAL_SIZE"
    target_id: str                   # other component's ID
    axis: Optional[str]              # "x" | "y" | "center" | "center_x" | "center_y"
    confidence: float                # 0.0-1.0
    metadata: Dict

@dataclass
class ComponentGeometry:
    """The geometric representation of a component."""
    type: str                        # "polygon" | "circle" | "arc" | "extrusion"
    points: List[Point]              # polygon vertices or centers
    radius: Optional[float]
    start_angle: Optional[float]
    end_angle: Optional[float]
    bounding_box: BBox               # x1, y1, x2, y2

@dataclass 
class ComponentTree:
    """Complete furniture representation as a tree of components."""
    furniture_type: str
    root: Optional[ComponentNode]
    nodes: Dict[str, ComponentNode]
    views: List[str]                 # ["top", "front", "side"]
    scale: Optional[ScaleSolution]
    metadata: Dict
```

**Modified modules:**
- `drawing_builders.py` — All 18+ `build_X_model()` functions refactored to output `ComponentTree` (which then converts to `DrawingModel` for legacy SVG/DXF export)
- `drawing_model.py` — Extended with `from_component_tree()` classmethod
- `dxf_exporter.py` — All 18+ `save_X()` functions refactored to use `ComponentTree` intermediates
- `component_graph.py` — `ComponentGraph` updated to output `ComponentTree` instead of ad-hoc dict

**Relationship detection (built into ComponentTree builder):**
1. For each pair of components in the same view:
   - Check horizontal alignment → `ALIGNED_H`
   - Check vertical alignment → `ALIGNED_V`
   - Check symmetry (mirror about center axis) → `SYMMETRIC`
   - Check centered overlap → `CENTERED`
   - Check parallel edges → `PARALLEL`
   - Check bounding box equality → `EQUAL_SIZE`
2. Confidence scored by proximity tolerance overlap

**Dependencies:** None (self-contained refactor of existing DrawingModel)  
**Estimated effort:** 5-7 days  
**Risk:** Medium — touches all 18 builder functions; regression risk

---

### Phase B: Semantic Primitive Graph + Constraint Solver (Drawing2CAD)

**Motivation:** Raw pixel coordinates are fragile. Relationships (symmetry, alignment, parallel) are measurement-agnostic and can be verified before scale solving.

#### Module: `relation_verifier.py` (NEW)

```python
class RelationVerifier:
    """Verifies ComponentRelations against actual geometry; outputs pass/fail + deviation."""
    
    def verify(self, tree: ComponentTree) -> List[VerificationResult]:
        """For each relation, compute deviation and pass/fail."""
    
    @dataclass  
    class VerificationResult:
        relation: ComponentRelation
        passed: bool
        deviation: float          # e.g., 3.2 pixels
        confidence: float         # adjusted down if failed
    
    # Algorithms per relation type:
    # ALIGNED_H: Compare y-coordinates of component centers. Deviation = |y1 - y2|
    # ALIGNED_V: Compare x-coordinates. Deviation = |x1 - x2|
    # SYMMETRIC: Mirror component1 across axis, compute Hausdorff distance to component2
    # CENTERED: Check component1 center falls within component2's bounding box  
    # PARALLEL: Compare edge angles. Deviation = |angle1 - angle2|
    # EQUAL_SIZE: Compare bounding box dimensions
```

#### Module: `constraint_solver.py` (NEW)

```python
class ConstraintSolver:
    """Adjusts component geometry to minimally satisfy violated relations."""
    
    def solve(self, tree: ComponentTree, fail_threshold: float = 0.25) -> ComponentTree:
        """Iteratively adjusts geometry to satisfy constraints.
        Uses gradient-free optimization:
        1. Collect all violated relations
        2. For each violation, compute minimal adjustment
        3. Apply adjustments in priority order (SYMMETRIC > ALIGNED > EQUAL_SIZE)
        4. Re-verify, repeat up to 3 iterations
        """
    
    # Example: If two legs should be SYMMETRIC but one is offset:
    #   avg_x = (leg1_center.x + mirrored(leg2_center).x) / 2
    #   leg1_center.x = avg_x
    #   leg2_center.x = mirrored(avg_x)
```

#### Module: `relation_templates.py` (NEW alongside existing template JSONs)

```python
# Per-type relation template (extends existing template JSON)
{
  "furniture_type": "round_pedestal_table",
  "relations": [
    {"type": "CENTERED", "source": "tabletop", "target": "collar_plate", "axis": "x"},
    {"type": "CENTERED", "source": "collar_plate", "target": "pedestal_body", "axis": "x"},
    {"type": "CENTERED", "source": "pedestal_body", "target": "base_plate", "axis": "x"},
    {"type": "PARALLEL", "source": "tabletop_top_edge", "target": "tabletop_bottom_edge"},
    {"type": "EQUAL_SIZE", "source": "tabletop_top_edge", "target": "tabletop_bottom_edge"}
  ]
}
```

**Modified modules:**
- `component_tree.py` — `ComponentTree` constructor auto-extracts relations for known types
- `unified_router.py` — Phase B runs between Phase A (IER build) and Phase 3 (export)
- `furniture_templates/*.json` — Each template gets a `"relations"` array

**Key insight:** Relations are computed BEFORE scale solving. "Legs are symmetric" uses pixel coordinates, not mm — works even when OCR fails.  
**Dependencies:** Phase A  
**Estimated effort:** 4-5 days  
**Risk:** Low — additive, all changes are new modules; existing pipeline untouched

---

### Phase C: Render → Compare → Repair Self-Correction Loop (CADReasoner)

**Motivation:** Single-pass reconstruction misses edges, misreads dimensions, and hallucinates geometry. A second-pass comparison catches these.

#### Module: `svg_comparator.py` (NEW)

```python
class SVGComparator:
    """Renders reconstruction to SVG, rasterizes both original and SVG, computes pixel diff."""
    
    def compare(self, original_path: str, reconstruction_model: DrawingModel) -> ComparisonReport:
        """Steps:
        1. Render reconstruction to SVG via svg_exporter
        2. Rasterize SVG to bitmap (via cairosvg or wand)
        3. Align original image to same scale/position as SVG
        4. Compute pixel-wise absolute difference (OpenCV absdiff)
        5. Threshold diff map (pixel diff > 10 → "gap pixel")
        6. Return ComparisonReport with gap regions
        """
    
    @dataclass
    class ComparisonReport:
        gap_regions: List[GapRegion]      # contiguous pixel-diff regions
        gap_pixel_count: int
        total_pixel_count: int
        gap_ratio: float                  # gap_pixels / total_pixels
        original_path: str
        reconstruction_path: str
```

#### Module: `gap_analyzer.py` (NEW)

```python
class GapAnalyzer:
    """Classifies each gap region into a specific repair type."""
    
    def analyze(self, report: SVGComparator.ComparisonReport,  
                tree: ComponentTree) -> List[GapClassification]:
    
    @dataclass
    class GapClassification:
        region: GapRegion
        type: str           # "missing_edge" | "extra_edge" | "dimension_mismatch" | "position_offset"
        severity: float     # 0.0-1.0
        component_id: Optional[str]
        suggested_action: str
    
    # Classification logic:
    # 1. missing_edge: gap region overlaps DXF component location but not drawn
    #    → Action: lower confidence threshold for that component, re-run detection
    # 2. extra_edge: gap region is drawn component not present in original
    #    → Action: force_visibility=false for that component
    # 3. dimension_mismatch: OCR text exists but value ≠ reconstructed value
    #    → Action: override dimension with OCR value
    # 4. position_offset: component drawn but at wrong position
    #    → Action: apply constraint solver with offset correction
```

#### Module: `repair_planner.py` (NEW)

```python
class RepairPlanner:
    """Generates repair actions from gap classifications."""
    
    def plan(self, gaps: List[GapAnalyzer.GapClassification],
             tree: ComponentTree) -> RepairPlan:
        """Prioritize gaps by severity, deduplicate, generate actions."""
    
    @dataclass
    class RepairAction:
        type: str                       # "re_detect" | "hide_component" | "override_dim" | "adjust_position"
        component_id: Optional[str]
        parameters: Dict                # new values for the action
        expected_effect: str
    
    @dataclass
    class RepairPlan:
        actions: List[RepairAction]
        estimated_gap_reduction: float  # predicted gap_ratio after repair
```

#### Module: `repair_loop.py` (NEW)

```python
class RepairLoop:
    """Orchestrator: render → compare → analyze → repair → re-render."""
    
    def run(self, original_path: str, initial_tree: ComponentTree,
            max_iterations: int = 3, gap_threshold: float = 0.05) -> ComponentTree:
        """Loop:
        1. Convert tree → DrawingModel → SVG via svg_exporter
        2. Compare SVG to original (SVGComparator)
        3. If gap_ratio < gap_threshold: return tree (done)
        4. Analyze gaps (GapAnalyzer)
        5. Plan repairs (RepairPlanner)
        6. Apply repairs to tree
        7. If iteration < max_iterations: goto 1
        8. Return best tree (lowest gap_ratio)
        """
```

**Modified modules:**
- `svc_exporter.py` — Ensure pixel-exact rendering for comparison quality
- `unified_router.py` — Wire Phase C as optional post-processing step
- `anti_hallucination_validator.py` — Accept repair loop's `force_visibility` overrides

**Dependencies:** Phase A (ComponentTree)  
**Estimated effort:** 6-8 days  
**Risk:** High — SVG rasterization quality is OS-dependent; diff threshold tuning requires experimentation; false positives from texture/shading differences

---

### Phase D: Conditional Factorization — Structure + Continuous Params (Img2CAD)

**Motivation:** Predict "what parts exist" (discrete) separately from "what are their dimensions" (continuous). The schema IS the discrete structure — no VLM training needed.

#### Module: `structure_verifier.py` (NEW)

```python
class StructureVerifier:
    """Checks that all expected components from schema are present in detection."""
    
    def verify(self, tree: ComponentTree, 
               schema: List[Dict]) -> StructureReport:
        """For each component in schema:
        1. Check if it exists in detection
        2. If missing: flag with source=TEMPLATE_DEFAULT, confidence=0.2
        3. If present: check detection confidence
        4. Return component completeness score
        """
    
    @dataclass
    class StructureReport:
        total_expected: int           # from schema
        detected: int                 # found in detection
        missing: List[str]            # component names not detected
        low_confidence: List[str]     # detected but conf < 0.5
        completeness: float           # detected / total_expected
```

#### Module: `component_detector.py` (NEW)

```python
class ComponentDetector:
    """Focused detection per component region (vs global detection)."""
    
    def detect_component(self, image: np.ndarray, 
                          component_name: str,
                          schema_entry: Dict,
                          parent_bbox: BBox) -> Optional[ComponentGeometry]:
        """For each schema component:
        1. Compute expected region from furniture type + component proportions
        2. Run focused OpenCV detection within that region
        3. If "seat" → look for horizontal rectangle in lower-mid region
        4. If "leg" → look for thin vertical rectangles in bottom region
        5. If "backrest" → look for vertical rectangle in upper region
        6. Return detected geometry or None with reason
        """
    
    EXAMPLE_REGION_MAP = {
        "sofa": {
            "seat": {"region": "middle_60pct", "shape": "horizontal_rect"},
            "backrest": {"region": "top_40pct", "shape": "horizontal_rect"},
            "arm_left": {"region": "left_15pct", "shape": "vertical_rect"},
            "arm_right": {"region": "right_15pct", "shape": "vertical_rect"},
            "base": {"region": "bottom_10pct", "shape": "horizontal_rect"},
            "legs": {"region": "bottom_5pct", "shape": "small_vertical_rects"},
        }
    }
```

#### Module: `dimension_regressor.py` (NEW)

```python
class DimensionRegressor:
    """Lightweight regressor for continuous dimensions from multiple signals."""
    
    def predict(self, component_name: str, 
                furniture_type: str,
                pixel_measurements: Dict[str, float],
                ocr_readings: List[float],
                scale_estimate: Optional[float],
                schema_defaults: Dict[str, float]) -> Dict[str, float]:
        """Priority chain (matching existing scale_solver.py):
        1. OCR reading → highest confidence if matches component
        2. Pixel measurement * scale → medium confidence
        3. Ratio estimate from reference → low confidence
        4. Schema default → lowest confidence
        
        For now: heuristic priority chain (no ML training needed).
        Future: lightweight XGBoost model trained on verified outputs.
        """
    
    # No ML training required for V1 — simply the existing priority chain 
    # from scale_solver.py but scoped per-component instead of globally.
    # The "regression" aspect comes from:
    # - Weighted averaging of multiple OCR readings for same component
    # - Scale estimate refinement per component (different scales for different views)
    # - Constraint propagation: if height_cm known, derive other dims from ratios
```

**Modified modules:**
- `unified_router.py` — ComponentDetector runs alongside existing detection; results fused
- `scale_solver.py` — Extended to output per-component scale estimates (not just global)
- `component_graph.py` — Schema-based detection integrated into graph building

**Dependencies:** Phase A (ComponentTree), Phase B (Schema templates with region maps)  
**Estimated effort:** 5-7 days  
**Risk:** Medium — per-component region detection may fail for unusual furniture proportions

---

### Phase E: Symmetry Detection + Enforcement

**Motivation:** Human-made furniture is highly symmetric. Existing pipelines don't enforce this.

#### Module: `symmetry_detector.py` (NEW)

```python
class SymmetryDetector:
    """Detects symmetry type and axis from image + geometry."""
    
    def detect_from_image(self, image_path: str) -> SymmetryInfo:
        """Uses OpenCV to detect reflection or rotational symmetry:
        1. Convert to edges (Canny)
        2. Try reflectional: flip image across candidate axes, compute edge overlap
        3. Try rotational: rotate image by 90/180/270°, compute edge overlap
        4. Return best match with confidence
        """
    
    def detect_from_geometry(self, tree: ComponentTree) -> SymmetryInfo:
        """Detects symmetry from component relationships:
        1. Find pairs of components with same type (e.g., leg_left / leg_right)
        2. Check if they are mirror images across center axis
        3. For single components: check self-symmetry (e.g., circle top)
        4. Return detected symmetry with confidence
        """
    
    @dataclass
    class SymmetryInfo:
        symmetry_type: str        # "reflectional" | "rotational" | "none"
        axis: Optional[str]      # "vertical" | "horizontal" | "diagonal"
        center: Optional[Point]  # symmetry center point
        confidence: float
```

#### Module: `symmetry_enforcer.py` (NEW)

```python
class SymmetryEnforcer:
    """Enforces symmetry constraints on component geometry."""
    
    def enforce(self, tree: ComponentTree, 
                symmetry: SymmetryDetector.SymmetryInfo) -> ComponentTree:
        """Adjusts component geometry to satisfy symmetry:
        1. For each symmetric pair: average their positions
        2. Mirror one to match the other
        3. For rotational symmetry: enforce equal angles
        4. Update component dimensions to match
        Returns modified tree with confidence boosted for enforced components.
        """
```

**Modified modules:**
- `repair_loop.py` — Symmetry enforcement as a repair action type
- `relation_verifier.py` — Add symmetry-specific verification rules
- `unified_router.py` — Wire symmetry as a refinement step

**Dependencies:** Phase B (Relations), Phase C (Repair loop)  
**Estimated effort:** 3-5 days  
**Risk:** Low — additive, modular, no existing module changes

---

## 3. Integrated Pipeline

```
                    ┌──────────────────────────────┐
                    │       Image Upload            │
                    └─────────────┬────────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │  Phase 1: Perception          │
                    │  (Existing, unchanged)        │
                    │  OpenCV + OCR + Line Role     │
                    │  + Dimension Assoc + Scale    │
                    └─────────────┬────────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │  Phase A: ComponentTree (IER) │ ← CAD-Coder
                    │  - ComponentNode[]            │
                    │  - ComponentRelation[]        │
                    │  - Relationship detection     │
                    └─────────────┬────────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │  Phase E: Symmetry Detection  │
                    │  - Image-based symmetry       │
                    │  - Geometry-based symmetry    │
                    └─────────────┬────────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │  Phase B: Constraint Verify   │ ← Drawing2CAD
                    │  - RelationVerifier           │
                    │  - ConstraintSolver           │
                    │  - Adjust to satisfy          │
                    └─────────────┬────────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │  Phase D: Structure Verify    │ ← Img2CAD
                    │  - StructureVerifier          │
                    │  - Missing component detection│
                    │  - Per-component detection    │
                    │  - Dimension regression       │
                    └─────────────┬────────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │  Phase 3: Export (Existing)    │
                    │  - DrawingModel conversion    │
                    │  - SVG + DXF export           │
                    │  - Anti-hallucination filter  │
                    └─────────────┬────────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │  Phase C: Self-Correction     │ ← CADReasoner
                    │  ┌─────────────────────────┐ │
                    │  │ SVGComparator            │ │
                    │  │   ↓                     │ │
                    │  │ GapAnalyzer              │ │
                    │  │   ↓                     │ │
                    │  │ RepairPlanner            │ │
                    │  │   ↓                     │ │
                    │  │ Apply + Re-render        │ │
                    │  │   ↓                     │ │
                    │  │ (loop up to 3x)         │ │
                    │  └─────────────────────────┘ │
                    └─────────────┬────────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │  Final Output                 │
                    │  - DXF with confidence meta   │
                    │  - SVG preview                │
                    │  - Per-component provenance   │
                    │  - Correction report          │
                    └───────────────────────────────┘
```

---

## 4. Detailed Module Specifications

### 4.1 `component_tree.py` — IER Core

**Inputs:**
- Furniture type (string)
- List of detected CadEntity from existing pipeline
- Component schema (from `_component_schema()`)
- Optional: pre-detected components from ComponentDetector

**Outputs:**
- `ComponentTree` with all components, geometry, relationships

**Algorithm:**
```
1. Load expected components from schema for this furniture type
2. For each expected component:
   a. Find matching CadEntity by spatial proximity to expected region
   b. If found: create ComponentNode with geometry from entities
   c. If not found: create ComponentNode with source="schema_default", confidence=0.2
3. Extract relationships between all detected components:
   a. Symmetry pairs: find mirrored components about center axis
   b. Alignment: check horizontal/vertical center alignment
   c. Centered: check if smaller component center lies on larger's center
4. Return ComponentTree
```

**Key design decision:** ComponentTree is the central data structure that all subsequent phases operate on. It replaces DrawingModel as the intermediate format, with DrawingModel becoming a CONVERTER output (ComponentTree → DrawingModel → SVG/DXF).

### 4.2 `relation_verifier.py` — Constraint Checking

**Inputs:** ComponentTree  
**Outputs:** List of VerificationResult (pass/fail + deviation)

**Pass/Fail Thresholds:**
| Relation | Pass Threshold | Fail Threshold |
|----------|---------------|----------------|
| ALIGNED_H | deviation < 5px | deviation > 15px |
| ALIGNED_V | deviation < 5px | deviation > 15px |
| SYMMETRIC | Hausdorff < 5px | Hausdorff > 20px |
| CENTERED | offset < 10% of bbox | offset > 25% of bbox |
| PARALLEL | angle diff < 5° | angle diff > 15° |
| EQUAL_SIZE | size diff < 5% | size diff > 15% |

### 4.3 `constraint_solver.py` — Geometry Adjustment

**Inputs:** ComponentTree + VerificationResult[]  
**Outputs:** Modified ComponentTree with adjusted geometry

**Algorithm:**
```
1. Sort violations: SYMMETRIC (highest priority) > CENTERED > ALIGNED > EQUAL_SIZE > PARALLEL
2. For SYMMETRIC violation:
   - Compute mirror axis from highest-confidence component
   - Mirror lower-confidence component to match higher-confidence one
   - Average position of both components if both are in detection (not schema default)
3. For CENTERED violation:
   - Move smaller component center to match larger component center
4. For ALIGNED violation:
   - Average the relevant coordinate (x for V, y for H)
5. For EQUAL_SIZE violation:
   - Set both to the average of their dimensions
6. For PARALLEL violation:
   - Rotate deviating edge to match reference edge angle
7. Re-run RelationVerifier, repeat up to 3 iterations
```

### 4.4 `svc_comparator.py` — Pixel Comparison

**Inputs:** 
- Original image path
- ComponentTree → DrawingModel → SVG (via SVG exporter)

**Outputs:** ComparisonReport with gap regions

**Implementation notes:**
- Use wand/ImageMagick or cairosvg for SVG → PNG rasterization
- Use OpenCV `cv2.absdiff()` for pixel comparison
- Gap region detection: `cv2.findContours()` on thresholded diff
- Scale SVG to match original image pixel dimensions before comparison
- Handle view layout: compare each view (top/front/side) independently

### 4.5 `repair_loop.py` — Orchestrator

**Inputs:** Original image path, initial ComponentTree  
**Outputs:** Final ComponentTree after self-correction

**Configuration:**
```yaml
repair_loop:
  max_iterations: 3
  gap_threshold: 0.05          # 5% gap → acceptable
  repair_actions:
    - re_detect                # Rerun detection in gap regions
    - hide_component           # Remove hallucinated geometry
    - override_dimension       # Replace with OCR value
    - adjust_position          # Constraint solver adjustment
    - enforce_symmetry         # Symmetry enforcer
```

### 4.6 `dimension_regressor.py` — Continuous Parameter Prediction

**Inputs:**
- Component name and type
- Pixel measurements from detection
- OCR readings (value + confidence)
- Global scale estimate
- Schema defaults + min/max

**Outputs:** Resolved dimensions dict with per-value confidence

**Algorithm (V1 — heuristic, no ML):**
```
For each dimension key:
  1. OCR match: if OCR value exists for this component → conf * 0.9
  2. Pixel * scale: if pixel measurement exists → conf * 0.6
  3. Ratio chain: from known dimension, derive via furniture proportions → conf * 0.4
  4. Schema default: → conf * 0.2
  Pick highest-confidence source
```

### 4.7 Component Region Map (stored alongside templates)

Each furniture type gets a `"component_regions"` block in its template JSON:
```json
{
  "furniture_type": "sofa",
  "component_regions": {
    "seat": { "region": "middle_60pct", "shape": "horizontal_rect", "detection": ["contour"] },
    "backrest": { "region": "top_40pct", "shape": "horizontal_rect", "detection": ["contour"] },
    "arm_left": { "region": "left_15pct", "shape": "vertical_rect", "detection": ["contour"] },
    "arm_right": { "region": "right_15pct", "shape": "vertical_rect", "detection": ["contour"] },
    "base": { "region": "bottom_10pct", "shape": "horizontal_rect", "detection": ["contour"] },
    "legs": { "region": "bottom_5pct", "shape": "small_vertical", "detection": ["line_pair"] }
  },
  "relations": [
    {"type": "SYMMETRIC", "source": "arm_left", "target": "arm_right", "axis": "vertical"},
    {"type": "ALIGNED_V", "source": "arm_left", "target": "arm_right", "axis": "center_x"},
    {"type": "CENTERED", "source": "seat", "target": "base", "axis": "center_x"},
    {"type": "PARALLEL", "source": "seat_top_edge", "target": "seat_bottom_edge"}
  ]
}
```

---

## 5. Implementation Roadmap

| Priority | Phase | Modules | Est. Effort | Dependencies | Risk Level |
|----------|-------|---------|-------------|--------------|------------|
| **P0** | **A (IER Refactor)** | `component_tree.py`, `component_relationships.py`, builder refactors (18+ functions) | 5-7 days | None | Medium |
| **P1** | **B (Semantic Graph)** | `relation_verifier.py`, `constraint_solver.py`, relation templates (types 1-6) | 4-5 days | Phase A | Low |
| **P2** | **E (Symmetry)** | `symmetry_detector.py`, `symmetry_enforcer.py` | 3-5 days | Phase B | Low |
| **P3** | **D (Factorization)** | `structure_verifier.py`, `component_detector.py`, `dimension_regressor.py` | 5-7 days | Phase A, B | Medium |
| **P4** | **C (Self-Correction)** | `svg_comparator.py`, `gap_analyzer.py`, `repair_planner.py`, `repair_loop.py` | 6-8 days | Phase A | High |
| **P5** | **Full Integration** | `unified_router.py` update, `chat_agent.py` update, frontend components | 6-8 days | All above | High |
| **P6** | **Benchmarking** | `accuracy_benchmark.py` update, test fixture generation, regression tests | 3-4 days | All above | Low |

**Total estimated effort: 32-44 days**

---

## 6. Expected Accuracy Targets

| Metric | Current | Target (Post-Fusion) | Primary Driver |
|--------|---------|---------------------|----------------|
| Dimension accuracy within 5% | ~60% | **85%** | CADReasoner loop corrects outliers; ConstraintSolver enforces relations |
| Component completeness | ~70% | **95%** | StructureVerifier catches missing parts; per-component detection fills gaps |
| Hallucination rate | ~15% | **<5%** | CADReasoner detects + hides extra edges; relation graph rejects inconsistent parts |
| Self-correction success (1st iteration) | N/A | **>60%** | SVGComparator + GapAnalyzer targeting common gap types |
| User editability | Medium | **High** | ComponentTree IER makes every component independently editable |
| Symmetry consistency | Not checked | **Guaranteed** | SymmetryDetector + SymmetryEnforcer |
| Novel type support | None | **Schema-driven** | Img2CAD factorization + region maps + generic component stack |
| Average correction iterations | N/A | **<2.5** | Repair loop with early exit on low gap_ratio |

---

## 7. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Phase C SVG rasterization quality** | Medium | High | Use multiple backends (cairosvg, wand, Chromium headless); fallback chain |
| **Phase C diff threshold tuning** | High | Medium | Automated threshold calibration script on synthetic test fixtures |
| **Phase C false positives from texture** | Medium | Medium | Pre-filter diff map: ignore regions with high edge density on both sides |
| **Phase D regressor overfitting** | Low | Medium | V1 uses heuristic priority chain only; ML only after 1000+ verified outputs |
| **Phase D per-component region detection** | Medium | Medium | Fall back to global detection if region-specific detection fails; confidence penalty |
| **Phase A builder refactor regression** | Medium | High | Regression test suite BEFORE refactor; entity-count assertions per type |
| **Integration complexity (Phase 5)** | Medium | High | Feature-flag each phase independently; integration test per phase |
| **Performance (3x repair iterations)** | Low | Medium | SVG render + image load per iteration (~500ms each); cache intermediate results |

---

## 8. Existing Module Changes Summary

| Module | Change Type | Phase |
|--------|------------|-------|
| `drawing_model.py` | Extend | A |
| `drawing_builders.py` | Refactor (18+ funcs) | A |
| `dxf_exporter.py` | Refactor (18+ funcs) | A |
| `component_graph.py` | Refactor | A |
| `svg_exporter.py` | Minor (pixel-exact option) | C |
| `unified_router.py` | Extend (5 new phases) | A-E |
| `anti_hallucination_validator.py` | Minor (accept overrides) | C |
| `scale_solver.py` | Extend (per-component scale) | D |
| `furniture_templates/*.json` | Extend (regions + relations) | B, D |
| `chat_agent.py` | Extend (new repair intents) | C |
| `accuracy_benchmark.py` | Extend (new metrics) | P6 |

---

## 9. Testing Strategy

### Unit Tests (per module):
- `test_component_tree.py` — Build ComponentTree from known entities; verify relations extracted
- `test_relation_verifier.py` — Perfect geometry → all pass; offset geometry → appropriate failures
- `test_constraint_solver.py` — Apply known violation; verify adjustment is minimal + correct
- `test_svg_comparator.py` — Same image → zero gaps; different image → known gap count
- `test_repair_loop.py` — Synthetic gap → verify repair reduces gap_ratio
- `test_symmetry_detector.py` — Known symmetric/imymmetric test images
- `test_structure_verifier.py` — Complete/incomplete component sets

### Integration Tests:
- Full pipeline: image → reconstruction → self-correction → final DXF
- Compare output DXF entity count/positions before/after each phase
- Verify no regression on all 18+ existing furniture types

### Test Fixtures:
- Synthetic images with known ground-truth ComponentTree
- Real hand-drawn furniture drawings with manual ground-truth
- Per-gap-type test fixtures: missing edge, extra edge, dimension mismatch, position offset

---

## 10. Appendix: Module Inventory (Complete)

### Existing Modules (unchanged)
- `ocr_layout_parser.py`, `ocr.py` — OCR dimension extraction
- `vision.py` — OpenCV detection
- `line_role_classifier.py` — Line classification
- `leader_dimension_classifier.py` — Leader line identification
- `dimension_associator.py` — Text↔geometry matching
- `scale_solver.py` — Scale computation + outlier rejection
- `geometry_reconstructor.py` — Contour assembly
- `geometry_cleanup.py` — Snap, merge, straighten
- `entity_confidence.py` — Confidence metadata attachment
- `anti_hallucination_validator.py` — Visibility gating
- `reference_ratio_solver.py` — Proportion-based estimation
- `reference_confidence_scorer.py` — Reference confidence
- `furniture_classifier.py` — Type classification
- `product_classifier.py`, `product_search.py` — Product matching
- `template_selector.py` — Template selection
- `layer_manager.py` — Layer organization
- `dxf_exporter.py` — DXF generation
- `dxf_auditor.py` — DXF quality checks
- `svg_exporter.py` — SVG preview generation
- `svg_skeleton.py` — SVG skeleton
- `drawing_model.py` — IER data model
- `drawing_builders.py` — Per-type model builders
- `component_assembler.py` — Component assembly
- `component_graph.py` — Component grouping
- `furniture_component_segmenter.py` — Component segmentation
- `section_predictor.py` — Cross-section prediction
- `visual_ratio_scaler.py` — Visual proportion scaling
- `text_normalizer.py` — OCR text normalization
- `style_presets.py` — Drawing style presets
- `titleblock_generator.py` — Title block generation
- `feedback_learner.py` — Feedback-based learning
- `fixture_generator.py` — Test fixture generation
- `extents_updater.py` — Bounding box updates
- `correction_api.py` — Correction endpoint
- `smart_workflow.py` — Workflow orchestration
- `accuracy_benchmark.py` — Accuracy measurement
- `chat_agent.py` — Conversational editing
- `unified_router.py` — 3-track fusion
- `pipeline.py` — cad_intelligence pipeline
- `cad_kernel/` — Core CAD engine
- `resource_engine/` — Template + resource system

### New Modules
| Module | File | Phase | Purpose |
|--------|------|-------|---------|
| ComponentTree | `component_tree.py` | A | Furniture-agnostic intermediate representation |
| ComponentRelations | `component_tree.py` | A | Explicit geometric relationship data model |
| RelationVerifier | `relation_verifier.py` | B | Check relations against geometry |
| ConstraintSolver | `constraint_solver.py` | B | Adjust geometry to satisfy constraints |
| RelationTemplates | `relation_templates.py` | B | Per-type relation definitions |
| SymmetryDetector | `symmetry_detector.py` | E | Detect symmetry from image + geometry |
| SymmetryEnforcer | `symmetry_enforcer.py` | E | Enforce symmetry constraints |
| StructureVerifier | `structure_verifier.py` | D | Check schema completeness |
| ComponentDetector | `component_detector.py` | D | Region-specific component detection |
| DimensionRegressor | `dimension_regressor.py` | D | Per-component dimension regression |
| SVGComparator | `svg_comparator.py` | C | Pixel-level SVG vs original comparison |
| GapAnalyzer | `gap_analyzer.py` | C | Classify gap regions into repair types |
| RepairPlanner | `repair_planner.py` | C | Generate repair actions from gaps |
| RepairLoop | `repair_loop.py` | C | Orchestrate render→compare→repair iterations |
