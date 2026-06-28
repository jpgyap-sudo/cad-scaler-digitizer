# Focus Sync Plan — CFG + Grammar + Self-Critic + Heatmap

**Status:** Planning Stage — No implementation  
**Goal:** Sync 4 key capabilities into your existing workflow without breaking anything  
**Philosophy:** Nothing gets replaced. Everything gets wrapped.

---

## 0. The Genius Sync Strategy

**Most of what you need already exists in your code.** The four capabilities aren't new modules to build from scratch. They're **wrappers around existing code** that introduce a common abstraction layer.

```
Your existing code (OpenCV, templates, builders, exporters, frontend)
         │
         ▼
    WRAPPER LAYER (NEW — thin, non-invasive)
         │
         ├── CanonicalFurnitureGraph → wraps DrawingModel + ProvenanceValue + ComponentGraph
         ├── FurnitureGrammar → wraps template JSONs + geometry resources + builder functions
         ├── SelfCritic → wraps SVG export + correction loop + anti-hallucination
         └── ConfidenceHeatmap → wraps EntityMetadata + frontend confidence UI

Each wrapper is 100-300 lines. The underlying code doesn't change.
```

---

## 1. Canonical Furniture Graph (CFG) — How It Syncs

### What already exists
| Component | Existing Code | CFG Mapping |
|-----------|--------------|-------------|
| Component data | `drawing_model.py` → `DrawingModel`, `View`, `PolygonComponent`, `CircleComponent`, etc. | CFG.components |
| Provenance | `EntityMetadata.source/confidence/evidence` on every entity | CFG.provenance |
| Provenance tracking | `unified_router.py` → `ProvenanceValue` with source/confidence/note | CFG.provenance graph |
| Component grouping | `component_graph.py` → `ComponentNode` with entities, bbox, dimensions | CFG.component_tree |
| Template structure | `furniture_templates/*.json` → parts, required_dimensions, layer_map | CFG.template_metadata |
| Dimension resolution | `template_resolver.py` + `scale_solver.py` → resolved dimensions | CFG.dimensions |
| Confidence scoring | `anti_hallucination_validator.py` → per-entity confidence | CFG.confidence_map |
| Scale | `scale_solver.py` → `ScaleSolution` with mm_per_px, confidence | CFG.scale |
| Correction recording | `feedback_learner.py` → `Correction` dataclass | CFG.corrections |
| Style presets | `style_presets.py` → materials, dimensions, visibility | CFG.materials, CFG.hardware |

### What the wrapper does

```python
# NEW: app/backend/cfg/canonical_furniture_graph.py (~200 lines)

from app.backend.drawing_model import DrawingModel, EntityMetadata
from app.backend.cad_intelligence.component_graph import ComponentGraph
from app.backend.cad_intelligence.unified_router import ProvenanceValue, UnifiedResult
from app.backend.scale_solver import ScaleSolution

class CanonicalFurnitureGraph:
    """Wrapper that reads EXISTING module outputs into ONE structure.
    
    NOT a replacement. Every existing module still works unchanged.
    This just collects their outputs into a single graph.
    """
    
    @classmethod
    def from_pipeline_result(cls, 
        drawing_model: DrawingModel,
        component_graph: ComponentGraph,
        unified_result: UnifiedResult,
        scale: ScaleSolution,
        corrections: List[Correction],
    ) -> 'CanonicalFurnitureGraph':
        """Assembles existing module outputs into CFG."""
        
    def to_drawing_model(self) -> DrawingModel:
        """Convert CFG back to DrawingModel for export."""
        # Existing exporters (svg_exporter, dxf_exporter) read DrawingModel.
        # They don't change. CFG → DrawingModel is a lossless conversion.
```

**Integration pattern:** Every pipeline stage writes to CFG. Existing exporters read CFG → DrawingModel. Nothing breaks.

### Existing flow: 
```
OpenCV → dict → classifier → dict → template → dict → DrawingModel → SVG/DXF
```

### After CFG wrapper:

```
OpenCV → CFG → classifier updates CFG → template updates CFG → CFG → DrawingModel → SVG/DXF
                        ↓
                  (all provenance preserved)
```

**The genius move:** `CFG.to_drawing_model()` is the ONLY new code that touches existing exporters. Everything upstream sees CFG. Everything downstream still sees DrawingModel. They never know they were wrapped.

---

## 2. Furniture Grammar — How It Syncs

### What already exists
| Component | Existing Code | Grammar Mapping |
|-----------|--------------|----------------|
| 25 templates | `resources/furniture_templates/*.json` — parts, dimensions, aspect ratios | Grammar instances |
| Geometry primitives | `resources/geometry/*.json` — 14+ (rectangular_top, round_top, oval_top, etc.) | Grammar component templates |
| Support types | `resources/supports/*.json` — 10+ (four_leg, pedestal, plinth, etc.) | Grammar base subtypes |
| Joinery | `resources/joinery/*.json` — (hidden_steel_frame, cabinet_carcass, etc.) | Grammar joint specs |
| Construction rules | `resources/construction_rules/bed.json` | Grammar rules |
| 18 builder functions | `drawing_builders.py` — each produces coordinate math | Grammar RENDERER — not replacement |
| Template selection | `template_selector.py` — picks template by type | Grammar instance lookup |
| Visual DNA | `visual_dna_index.json` — component_graph per family | Grammar inheritance chain |
| Smart workflow | `smart_workflow.py` — route selection, confirmation questions | Grammar-powered gating |

### What the wrapper does

```python
# NEW: app/backend/grammar/engine.py (~300 lines)

from app.backend.drawing_builders import build_round_pedestal_model, build_rectangular_table_model, ...

class FurnitureGrammar:
    """Wrapper that READS template JSONs + geometry resources to 
    generate the SAME output as existing builder functions.
    
    NOT a replacement. Builders still work. Grammar engine just 
    delegates to them or generates equivalent output.
    """
    
    GRAMMAR_DEFINITIONS = {
        "dining_table": {
            "family": "table",
            "inherits": [],
            "allowed_top_types": ["rectangle", "round", "oval"],
            "allowed_base_types": ["four_leg", "pedestal", "metal_frame"],
            "default_view_order": ["top", "front", "side"],
            "proportions": {
                "top_thickness_to_height": 0.04,
                "base_height_to_total": 0.92,
            },
            "template_instances": {
                "dining_table_rectangular_4_leg": {
                    "top": "rectangle",
                    "base": "four_leg",
                    "leg_count": 4,
                    "builder_fn": build_rectangular_table_model,
                },
                "dining_table_round_pedestal": {
                    "top": "round",
                    "base": "pedestal",
                    "builder_fn": build_round_pedestal_model,
                },
            }
        },
        "coffee_table": {
            "family": "table",
            "inherits": ["dining_table"],
            "overrides": {
                "height_range": [30, 50],  # cm, coffee tables are lower
                "proportions.top_thickness_to_height": 0.06,
            },
            "template_instances": {
                "coffee_table_rectangular_4_leg": {
                    "top": "rectangle", 
                    "base": "four_leg",
                    "leg_count": 4,
                    "builder_fn": build_coffee_table_model,
                },
                # ... more instances
            }
        },
    }
    
    def get_template(self, furniture_type: str) -> GrammarTemplate:
        """Look up by type. Inherits from parent family."""
        # First loads template JSON from resources/
        # Then applies grammar rules to fill in defaults
        # Then applies any type-specific overrides
        # Returns GrammarTemplate that builder can use
    
    def compose(self, template: GrammarTemplate, params: Dict) -> DrawingModel:
        """EITHER delegates to existing builder function OR 
        generates geometry from primitives if no builder exists.
        
        This is how you add furniture type #26 without writing
        a builder function — grammar engine generates from primitives.
        """
```

### Integration pattern

**When a known template exists:**
```
Grammar Engine → loads template JSON → delegates to builder function
    (same output as today, zero code changes)
```

**When a NEW type is detected (no builder):**
```
Grammar Engine → loads parent grammar → composes from geometry primitives
    → generates DrawingModel directly (no builder needed)
```

**The genius move:** The grammar engine is a **gradual migration path**. Today it delegates to existing builders. Tomorrow, when a type's builder is refactored, the grammar engine can generate it directly. Eventually all 25 templates work without builders, but you never had to stop the world to get there.

### What changes in existing code

| File | Change | Lines |
|------|--------|-------|
| `drawing_builders.py` | Each builder gets a `@grammar_compatible` decorator that records which grammar instance it serves | +1 line per function |
| `template_selector.py` | Now also looks up grammar hierarchy when no exact template exists | +20 lines |
| `smart_workflow.py` | Route selection considers grammar compatibility | +5 lines |

**No builder is removed or rewritten. The grammar is additive.**

---

## 3. Self-Critic Loop — How It Syncs

### What already exists

| Component | Existing Code | Self-Critic Mapping |
|-----------|--------------|---------------------|
| SVG render | `svg_exporter.py` → renders DrawingModel to SVG | Render step |
| Accuracy measurement | `accuracy_benchmark.py` → measures output quality | Compare step |
| Correction loop | `App.tsx` → `MAX_CORRECTION_LOOPS = 3` + `runCadVerifier()` + `runCadCorrector()` | Loop orchestrator |
| Anti-hallucination | `anti_hallucination_validator.py` → confidence-based filtering | Repair mechanism |
| Image comparison | `comparison_agent.py` → compares AI output to input | Gap detection |
| Smart workflow | `smart_workflow.py` → confirmation questions | User-in-the-loop repair |
| Feedback learning | `feedback_learner.py` → records corrections | Post-repair learning |
| Route selection | `smart_workflow.py` → `choose_internal_route()` | When to trigger critic |

**THE GENIUS DISCOVERY:** Your `App.tsx` ALREADY has a 3-iteration correction loop. It calls `runCadVerifier()` after generation, then `runCadCorrector()` if the verification fails. You just need to add the IMAGE COMPARISON step:

```
Current:  generate → verify → correct (compares against internal rules)
Upgrade:  generate → render → compare vs ORIGINAL IMAGE → detect gaps → correct
                                      ↓
                          (adds pixel-level feedback, not just rule-based)
```

### What the wrapper does

```python
# NEW: app/backend/self_critic/loop.py (~250 lines)

from app.backend.svg_exporter import render_svg
from app.backend.anti_hallucination_validator import ValidationResult
from app.backend.comparison_agent import ComparisonReport

class SelfCritic:
    """Wraps existing SVG export + comparison + correction into a loop.
    
    Each step uses existing code. Nothing new under the hood.
    """
    
    def run(self, 
        drawing_model: DrawingModel, 
        original_image_path: str,
        max_iterations: int = 3,
    ) -> SelfCriticResult:
        
        for i in range(max_iterations):
            # STEP 1: Render (uses EXISTING svg_exporter.py)
            svg = render_svg(drawing_model)
            
            # STEP 2: Compare (uses EXISTING comparison logic + OpenCV)
            gap_report = self.compare(svg, original_image_path)
            
            # STEP 3: Check threshold (EXISTING accuracy_benchmark.py concept)
            if gap_report.gap_ratio < 0.05:
                return SelfCriticResult(drawing_model, gap_report, iterations=i+1, converged=True)
            
            # STEP 4: Repair (uses EXISTING anti_hallucination_validator.py)
            drawing_model = self.repair(drawing_model, gap_report)
        
        return SelfCriticResult(drawing_model, gap_report, iterations=max_iterations, converged=False)
    
    def compare(self, svg: str, original_path: str) -> GapReport:
        """Uses OpenCV to compare SVG render vs original image.
        OpenCV already exists in your pipeline — this is just a new call to it.
        """
        # 1. Convert SVG to bitmap (via cairosvg or headless Chrome)
        # 2. OpenCV absdiff between rendered bitmap and original
        # 3. Threshold diff to get gap regions
        # 4. Classify each gap region
        
    def repair(self, model: DrawingModel, report: GapReport) -> DrawingModel:
        """Uses existing mechanisms to fix detected gaps."""
        for gap in report.gaps:
            if gap.type == "extra_edge":
                # Use existing visibility system
                model.set_component_visible(gap.component_name, False)
            elif gap.type == "dimension_mismatch":
                # Use existing dimension override
                model.override_dimension(gap.dimension_key, gap.suggested_value)
            elif gap.type == "missing_component":
                # Lower confidence threshold for this component
                model.set_component_threshold(gap.component_name, 0.3)
```

### Integration pattern

```
BEFORE:  OpenCV → AI → template → DXF
                                         ↓
AFTER:   OpenCV → AI → template → DXF → SelfCritic → (3 iterations) → final DXF
                                              ↓
                                     If self-critic disagrees:
                                     ask user → record correction → improve next time
```

### What changes in existing code

| File | Change | Lines |
|------|--------|-------|
| `App.tsx` | Replace inner correction loop with SelfCritic API call | +15, -10 |
| `smart_workflow.py` | Add "self-critic" as a route choice | +10 |
| `backend-python/app/main.py` | Add `/api/self-critic` endpoint | +20 |
| `package.json` | Add cairosvg dependency | +1 line |

**The genius move:** You already had `MAX_CORRECTION_LOOPS = 3` in App.tsx. You already had `runCadVerifier()` and `runCadCorrector()`. The only missing piece is the IMAGE COMPARISON — comparing the SVG render BACK to the original photo. That's one new OpenCV call. The loop infrastructure already exists.

---

## 4. AI Confidence Heatmap — How It Syncs

### What already exists

| Component | Existing Code | Heatmap Mapping |
|-----------|--------------|-----------------|
| Per-entity confidence | `EntityMetadata.confidence` on every CircleComponent, PolygonComponent, etc. | Per-component score |
| Source tracking | `EntityMetadata.source` — "measured", "ocr", "ratio", "default", "user" | Color coding |
| Evidence | `EntityMetadata.evidence` — list of evidence strings | Tooltip details |
| Color coding | `getSourceColor()` in `frontend/services/templateMatcher.ts` | Color scheme |
| Source labels | `getSourceLabel()` in `frontend/services/templateMatcher.ts` | Legend text |
| Confidence legend | `frontend/components/CadConfidenceLegend.tsx` | Legend panel |
| Confidence panel | `frontend/components/ConfidencePanel.tsx` — shows dimensions with source | Detail panel |
| Frontend types | `types.ts` → `CadPrimitive` with layer, style | Canvas overlay data |

**THE GENIUS DISCOVERY:** Your frontend ALREADY has `getSourceColor()`, `getSourceLabel()`, `CadConfidenceLegend.tsx`, and `ConfidencePanel.tsx`. The heatmap is just **rendering what these already know onto the canvas itself** instead of only in a sidebar.

### What the wrapper does

```typescript
// NEW: frontend/services/confidenceHeatmap.ts (~100 lines)

import { EntityMetadata } from '../../backend-python/app/backend/drawing_model';
import { getSourceColor, getSourceLabel } from './templateMatcher';

interface HeatmapComponent {
  name: string;
  confidence: number;
  source: string;       // "measured" | "ocr" | "ratio" | "default" | "user"
  color: string;        // from getSourceColor
  label: string;        // from getSourceLabel
  evidence: string[];
  boundingBox: BBox;    // for overlay positioning
}

export function buildHeatmap(drawingModel: DrawingModel): HeatmapComponent[] {
  // Extract every component's metadata → heatmap entry
  // Uses EXISTING EntityMetadata, getSourceColor, getSourceLabel
}

export function getHeatmapColor(confidence: number): string {
  if (confidence >= 0.85) return '#22c55e';  // green
  if (confidence >= 0.60) return '#eab308';  // yellow
  return '#ef4444';                            // red
}
```

```typescript
// MODIFIED: frontend/components/CadCanvas.tsx (~30 lines added)

// NEW: After drawing each component, overlay a translucent heatmap fill
function drawHeatmapOverlay(ctx: CanvasRenderingContext2D, heatmap: HeatmapComponent[]) {
  for (const component of heatmap) {
    ctx.fillStyle = component.color + '33';  // 20% opacity
    ctx.fillRect(component.bbox.x1, component.bbox.y1, 
                  component.bbox.width, component.bbox.height);
    // On hover: show tooltip with source + evidence
  }
}
```

### Integration pattern

```
Before:
  SVG preview ← components drawn in black
  Sidebar: ConfidencePanel shows numbers
  (user must cross-reference)

After:
  SVG preview ← components drawn in green/yellow/red with 20% fill
  Click component → tooltip: "Tabletop • 95% confidence • from OCR"
  Sidebar: ConfidencePanel shows the SAME data (unchanged)
  (user sees confidence directly on the drawing)
```

### What changes in existing code

| File | Change | Lines |
|------|--------|-------|
| `CadCanvas.tsx` | Add heatmap overlay rendering | +30 |
| `ConfidencePanel.tsx` | Add click-to-highlight component on canvas | +15 |
| `CadConfidenceLegend.tsx` | Already exists — no change needed | 0 |
| `services/templateMatcher.ts` | Already has getSourceColor/getSourceLabel | 0 |

**The genius move:** The heatmap doesn't require ANY backend changes. EntityMetadata already carries confidence/source/evidence on every entity — it's serialized in the JSON response. The frontend just needs to VISUALIZE what's already there.

---

## 5. THE SYNC — How All 4 Connect to Your Current Pipeline

### Current pipeline (today):

```
Upload → OpenCV + OCR → 3-track Fusion → DrawingModel → SVG + DXF
                            ↓                       ↓
                     smart_workflow.py        ChatBox adjusts
                     (route selection)        (dimensions, materials)
                            ↓
                    feedback_learner.py
                    (records corrections)
```

### After sync (additive layers, no changes to existing):

```
Upload ──→ Image Preprocess ──→ OpenCV + OCR ──→ 3-track Fusion ──→ CFG
              (NEW)             (unchanged)         (unchanged)      (WRAPPER)
                                                                        │
                                    ┌───────────────────────────────────┘
                                    ▼
                            GRAMMAR ENGINE (WRAPPER)
                                    │
                            delegates to EXISTING builder
                            OR generates from primitives
                                    │
                                    ▼
                            DrawingModel (unchanged)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              SVG Exporter    DXF Exporter    Self-Critic (WRAPPER)
              (unchanged)     (unchanged)         │
                                          compare vs original
                                          repair gaps
                                                  │
                                                  ▼
                                          final DrawingModel
                                                  │
                    ┌───────────────────────────────┘
                    ▼
            Frontend Preview + HEATMAP (NEW OVERLAY)
                    │
            ConfidencePanel (unchanged)
                    │
            ChatBox adjusts CFG → re-render
                    │
            feedback_learner records ALL corrections
                    │
            Next time: grammar proportions adjust
```

### What's ADDED to the codebase (total ~1,000 new lines)

| Module | File | Lines | Depends On |
|--------|------|-------|------------|
| CFG | `backend/cfg/canonical_furniture_graph.py` | ~200 | Existing DrawingModel + ProvenanceValue + ComponentGraph |
| CFG serializer | `backend/cfg/serializer.py` | ~80 | CFG |
| Grammar engine | `backend/grammar/engine.py` | ~300 | Existing template JSONs + geometry resources + builder decorators |
| Grammar definitions | `backend/grammar/definitions.py` | ~100 | Existing templates |
| Self-Critic | `backend/self_critic/loop.py` | ~200 | Existing SVG exporter + OpenCV + anti-hallucination |
| Self-Critic endpoint | `backend/main.py` route | ~30 | SelfCritic |
| Heatmap service | `frontend/services/confidenceHeatmap.ts` | ~100 | Existing EntityMetadata + getSourceColor |
| CadCanvas overlay | `frontend/components/CadCanvas.tsx` | +30 | Heatmap service |
| Pipeline integration | `backend/smart_workflow.py` update | +30 | CFG + Grammar + SelfCritic |

**Total: ~1,070 new lines, ~0 existing lines modified (only additive)**

### What's on the ROADMAP (not building now)

| Phase | Capability | When | Why Later |
|-------|-----------|------|-----------|
| AI Council | Multi-specialist consensus | After CFG | Needs CFG as shared data model to vote on |
| Progressive Resolution | Stage-gated cascade | After CFG + Grammar | Grammar defines stages; CFG holds progressive state |
| Manufacturing Intent | BOM, cost, assembly | After CFG + SelfCritic | Manufacturing needs verified geometry |
| Symmetry Engine | Detect + enforce | After SelfCritic | Self-critic can verify symmetry fixes |
| Continuous Learning | Grammar evolution | After Grammar | Grammar needs usage data to evolve |
| DNA Search | Runtime similarity | After CFG | Needs CFG schema to index |

---

## 6. Implementation Plan — 4 Weeks, Parallelizable

### Week 1: CFG + Heatmap (parallel)

**CFG (3 days):**
1. `backend/cfg/models.py` — `FurnitureGraph` dataclass with all fields
2. `backend/cfg/canonical_furniture_graph.py` — `from_pipeline_result()` builder
3. `backend/cfg/serializer.py` — CFG ↔ DrawingModel conversion
4. Update `smart_workflow.py` — store result as CFG
5. Update `/digitize` endpoint — return CFG alongside existing response

**Heatmap (2 days, can run in parallel):**
1. `frontend/services/confidenceHeatmap.ts` — extract from DrawingModel JSON
2. `CadCanvas.tsx` — add heatmap overlay rendering
3. `ConfidencePanel.tsx` — link panel hover to canvas highlight

### Week 2: Grammar Engine

1. `backend/grammar/definitions.py` — grammar definitions for all 10 table types
2. `backend/grammar/engine.py` — template lookup + builder delegation + inheritance
3. Decorate existing `drawing_builders.py` functions with `@grammar_template`
4. `template_selector.py` — add grammar fallback when no exact template exists
5. Test: grammar delegates to builders → identical output to today

### Week 3: Self-Critic Loop

1. `backend/self_critic/loop.py` — compare + classify + repair loop
2. Add SVG → bitmap rendering (cairosvg)
3. Add OpenCV absdiff comparison
4. Wire gap classification using existing comparison_agent logic
5. Wire repair using existing anti_hallucination mechanisms
6. `POST /api/self-critic` endpoint
7. Update `App.tsx` to call self-critic instead of local correction loop

### Week 4: Integration + Expansion

1. Wire CFG through entire pipeline
2. Pipe self-critic output back to CFG
3. Update SmartConfirmations to show heatmap-based warnings
4. Expand grammar to seating family (sofa, chair, ottoman)
5. Regression tests: all 25 templates produce identical output
6. Demo: full pipeline with heatmap + self-critic for one furniture type

---

## 7. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Builder functions produce different output when grammar delegates** | Low | High | Grammar tests compare byte-identical SVG against today's builders |
| **Self-critic false positives (lighting differences)** | Medium | Medium | Diff threshold calibration; ignore high-edge-density regions on both sides |
| **Heatmap performance (100+ components)** | Low | Low | Canvas heatmap rendered in requestAnimationFrame; only re-draw on confidence change |
| **CFG ↔ DrawingModel conversion loses data** | Low | High | Both directions tested with ALL 25 furniture types; entity-count assertions |
| **Existing users depend on current API format** | Low | Medium | `POST /digitize` returns BOTH old format + CFG; legacy response untouched |

---

## 8. What Ships After Each Week

| Week | Delivers | User Sees |
|------|----------|-----------|
| 1 | CFG + Heatmap | Components colored green/yellow/red on preview; hover shows source |
| 2 | Grammar Engine | New furniture types work without builder functions; existing types unchanged |
| 3 | Self-Critic | DXF visibly closer to original photo; fewer manual corrections needed |
| 4 | Full Integration | Complete pipeline with confidence feedback + self-correction + grammar |

---

## 9. Key Principle: The Wrapper Pattern

Every new capability follows the same pattern:

```
1. Identify what existing code already does
2. Build a thin wrapper (100-300 lines) that:
   a. Reads existing outputs
   b. Adds the missing abstraction
   c. Writes back to existing formats
3. Existing code never changes
4. Wrapper can be turned off with a feature flag
5. Over time, wrapper gradually replaces legacy paths
```

This is the strategy that lets you build the Furniture Engineering OS without stopping the world.
