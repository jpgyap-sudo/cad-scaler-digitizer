# Furniture Engineering OS — Full Architecture Plan

**Status:** Planning Stage — No implementation  
**Based on:** Existing codebase audit + user vision for super-app  
**Key philosophy:** Nothing gets replaced. Every existing module becomes a specialist inside an orchestration engine.

---

## 0. What You Already Have (The Foundation)

You already have 80% of the infrastructure. Here's exactly what maps to the vision:

| Vision Concept | Your Existing Code/Data |
|----------------|------------------------|
| **Furniture DNA** | `resources/product_catalog/visual_dna_index.json` — 4122 lines, 101 families, component graphs, SVG skeletons, symmetry, materials |
| **25 Templates** | `resources/furniture_templates/*.json` — 25 types with parts, required dimensions, visual signatures, generation rules, layer maps |
| **259 Products** | `resources/product_catalog/_fixture_spec.json` — 259 Shopify products, 101 families, mapping to template files |
| **Geometry Primitives** | `resources/geometry/*.json` — 14+ primitives (rectangular_top, round_top, oval_top, casework, seating_arms, sofa_back, etc.) |
| **Joinery Knowledge** | `resources/joinery/*.json` — hidden_steel_frame, cabinet_carcass, sofa_internal_frame, wood_apron |
| **Support Types** | `resources/supports/*.json` — 10+ types (four_leg, pedestal, plinth, dual_cylinder, etc.) |
| **Construction Rules** | `resources/construction_rules/bed.json`, `resources/dimension_styles/metric_a3.json` |
| **Manufacturer Knowledge** | `resources/manufacturers/home_u.json`, `homeu_modern.json` |
| **Echo Drafter (Learning)** | `backend-python/app/backend/feedback_learner.py` — Correction recording, preference model, pattern extraction |
| **Style Presets** | `backend-python/app/backend/style_presets.py` — Named presets with materials, dimensions, visibility |
| **Closed-Loop Learning** | `backend-python/app/backend/resource_engine/closed_loop/` — decision_memory, delta_engine, recommendation_engine, template_ranking |
| **3-Track Fusion** | `backend-python/app/backend/cad_intelligence/unified_router.py` — AI Vision + OpenCV+OCR + Template Graph with provenance |
| **Multi-Agent System** | `backend-python/app/backend/chat_agent.py`, `services/engineering_agent.py`, `services/comparison_agent.py` |
| **CAD Kernel** | `backend-python/app/backend/cad_kernel/` — spatial_index, hidden_line, section_generator, annotation_engine, learning_engine, sheet_layout, view_generator |
| **DXF Export** | `backend-python/app/backend/dxf_exporter.py` + `frontend/utils/dxf.ts` — 18+ type-specific save functions |
| **SVG Preview** | `backend-python/app/backend/svg_exporter.py` — Browser preview renderer |
| **Dimension Intelligence** | `cad_intelligence/` — dimension_associator, scale_solver, line_role_classifier, geometry_reconstructor |
| **Anti-Hallucination** | `backend-python/app/backend/anti_hallucination_validator.py` — Confidence-gated visibility |
| **Reference Library** | `backend-python/app/backend/reference_retriever.py` — Product reference lookup via Node API + Qdrant |
| **Benchmarking** | `backend-python/app/backend/accuracy_benchmark.py` — Accuracy measurement |
| **Template Graphs** | `backend-python/app/backend/resource_engine/template_loader.py`, `template_resolver.py` — JSON template graphs for 18 types |
| **Validation Pipeline** | `backend-python/app/backend/resource_engine/validation/` — correction_engine, validators, report_builder |
| **View Generation** | `backend-python/app/backend/cad_kernel/view_generator/` — projection, section_locator, exploded_view, viewport_layout, hidden_line_stub |
| **Section Generation** | `backend-python/app/backend/cad_kernel/section_generator/` — cutter, detail_builder, locator, quality |
| **Sheet Layout** | `backend-python/app/backend/cad_kernel/sheet_layout/` — bom, notes, placer, revision, templates, titleblock |
| **Annotation Engine** | `backend-python/app/backend/cad_kernel/annotation_engine/` — layout, leaders, materials, bom, pipeline |
| **Cloud Vision** | `backend-python/app/backend/resource_engine/cloud_vision.py` — GPT-4o/Gemini integration |
| **Product Crawler** | `crawler-worker/` + `scripts/crawl-jardan.mjs` + `scripts/find-*.py` |
| **FreeCAD Plugin** | `freecad_workbench/FreeCADDigitizer/` — commands, Init, InitGui |
| **Docker** | `docker-compose.yml`, `Dockerfile.*` — Frontend, Node API, Python worker, MCP server, crawler |
| **Chat Agent** | `frontend/components/ChatBox.tsx` + `backend-python/app/backend/chat_agent.py` — conversational dimension/material/visibility editing |

**What you DON'T have yet (the gaps to fill):**
1. A single shared data model that all modules read/write (Canonical Furniture Graph)
2. Furniture Grammar (formal composition rules instead of hardcoded builders)
3. AI Council (orchestrated multi-specialist agents with consensus)
4. Self-Critic render→compare→repair loop
5. Progressive resolution (stage-by-stage refinement)
6. Furniture Manufacturing Intent Graph (joinery, materials, hardware, assembly)
7. Continuous learning from user corrections (you have Echo Drafter but it's not wired to all outputs)
8. AI Confidence Heatmap per component (you have confidence metadata but not visualized)
9. BOM/Assembly/Cost outputs (you have sheet_layout/BOM but not productionized)

---

## 1. The Canonical Furniture Graph (CFG)

**This is the single most important addition.** Everything reads from and writes to this graph. No more passing data between modules as ad-hoc dicts.

### 1.1 What the CFG Contains

```python
@dataclass
class FurnitureGraph:
    # === Identity ===
    graph_id: str                              # UUID
    source: str                                # "upload" | "ai_vision" | "template" | "catalog" | "user_edit"
    furniture_type: str                        # "dining_table_rectangular_4_leg"
    furniture_family: str                      # "dining_table" — the grammar family
    
    # === Measurement ===
    overall_dimensions: Dict[str, float]       # length_cm, width_cm, height_cm
    scale: ScaleSolution                       # from existing scale_solver
    
    # === Component Hierarchy (Furniture Grammar) ===
    grammar: FurnitureGrammar                  # the rule tree used to compose this
    components: List[ComponentNode]            # all detected/manufactured components
    relations: List[ComponentRelation]         # geometric relationships
    
    # === Manufacturing ===
    materials: Dict[str, MaterialSpec]         # per-component material, finish
    joinery: List[JointSpec]                   # how parts connect
    hardware: List[HardwareSpec]               # screws, brackets, cam locks
    bom: BillOfMaterials                       # computed from components
    
    # === Engineering ===
    views: Dict[str, ViewSpec]                 # top, front, side, section, exploded
    section_planes: List[SectionPlane]         # where to cut for section views
    annotations: List[AnnotationSpec]          # dimensions, leaders, notes
    
    # === Provenance ===
    provenance: ProvenanceGraph                # which specialist produced what, confidence
    corrections: List[Correction]              # user corrections applied
    
    # === Learning ===
    confidence_map: Dict[str, float]           # per-component confidence
    dna_signature: str                         # fingerprint for similarity search
```

### 1.2 How Existing Modules Map to CFG Slots

| Existing Module | CFG Slot |
|----------------|----------|
| `visual_dna_index.json` | `furniture_family`, `dna_signature` |
| `furniture_templates/*.json` | `components` structure, `furniture_type` |
| `geometry/*.json` | ComponentNode geometry templates |
| `joinery/*.json` | `joinery` |
| `supports/*.json` | ComponentNode support-type templates |
| `construction_rules/*.json` | `section_planes`, `views` |
| `manufacturers/*.json` | `materials` defaults |
| `unified_router.py` ProvenanceValue | `provenance` |
| `feedback_learner.py` Correction | `corrections` |
| `anti_hallucination_validator.py` | `confidence_map` |
| `component_graph.py` ComponentNode | `components` |
| `reference_retriever.py` | `dna_signature` similarity |
| `cad_kernel/sheet_layout/` | `annotations`, `bom` |
| `cad_kernel/view_generator/` | `views` |
| `cad_kernel/section_generator/` | `section_planes` |
| `cad_kernel/annotation_engine/` | `annotations` |
| `style_presets.py` | `materials`, `hardware` defaults |
| `drawing_model.py` DrawingModel | OUTPUT format, not CFG itself |

### 1.3 Why This Changes Everything

**Before CFG:**
```
OpenCV → dict_A → classifier → dict_B → template → dict_C → DXF
                                                    → SVG
                              (3 different dict formats, no shared schema)
```

**After CFG:**
```
OpenCV ──┐
         ├──→ CFG ←── classifier
template ─┘     │
                ├──→ DXF exporter
                ├──→ SVG exporter
                ├──→ BOM generator
                ├──→ Assembly guide
                ├──→ Cost estimator
                ├──→ CNC output
                ├──→ FreeCAD workbench
                ├──→ Correction recorder
                ├──→ Similarity search
                └──→ Learning system
```

**New module needed:** `app/backend/cfg/` (canonical_furniture_graph.py)

---

## 2. Furniture Grammar — Replace Template Hardcoding with Composition Rules

**What you have:** 25 hardcoded templates. Each template is hand-authored JSON with fixed parts.

**What to build:** A furniture composition grammar where templates become INSTANCES of grammar rules.

### 2.1 Grammar Definition

```python
# A furniture type is defined as a composition of parts with constraints

FURNITURE_GRAMMAR = {
    "dining_table": {
        "family": "table",
        "inherits": ["has_top", "has_base"],
        "rules": {
            "top": {
                "type": "horizontal_surface",
                "allowed_profiles": ["rectangle", "round", "oval", "boat", "organic"],
                "thickness_range": [15, 60],  # mm
                "overhang_default": 20,        # mm past base
            },
            "base": {
                "type": "vertical_support",
                "allowed_subtypes": ["legs", "pedestal", "metal_frame", "trestle"],
            },
            "apron": {
                "required": "when base_type='legs' AND length > 150cm",
                "thickness_range": [15, 25],
                "height_range": [60, 120],
            },
            "stretcher": {
                "optional": True,
                "condition": "base_type='legs' AND height > 75cm",
            },
        },
        "proportions": {
            "top_thickness_to_height": 0.04,      # top 4% of height
            "leg_height_to_total": 0.92,           # legs 92% below top
            "apron_height_to_leg": 0.30,            # apron 30% of leg
        },
        "views": ["top", "front", "side"],
    },
    
    "coffee_table": {
        "family": "table",
        "inherits": ["dining_table"],
        "overrides": {
            "height_range": [30, 50],     # cm (lower than dining)
            "proportions.top_thickness_to_height": 0.06,
        },
    },
    
    "console_table": {
        "family": "table",
        "inherits": ["dining_table"],
        "overrides": {
            "width_range": [30, 50],      # cm (narrower than dining)
            "proportions.top_thickness_to_height": 0.05,
        },
    },
}
```

### 2.2 Inheritance Chain

```
furniture
├── table
│   ├── dining_table
│   │   ├── dining_table_rectangular_4_leg
│   │   ├── dining_table_round_pedestal
│   │   └── dining_table_metal_frame
│   ├── coffee_table
│   │   ├── coffee_table_rectangular_4_leg
│   │   ├── coffee_table_round_nesting_set
│   │   ├── coffee_table_organic_blob
│   │   ├── coffee_table_glass_wire_mesh
│   │   └── coffee_table_block_plinth
│   ├── console_table_slim
│   ├── side_table
│   │   ├── side_table_round
│   │   └── side_table_rectangular
│   └── nightstand_bedside_drawer (table + storage)
├── seating
│   ├── sofa
│   │   ├── sofa_straight_2_3_seat
│   │   ├── sofa_sectional_l_shape
│   │   └── bench_chaise (long seating)
│   ├── chair
│   │   ├── dining_chair
│   │   ├── armchair_lounge
│   │   └── bar_stool (chair + pedestal)
│   └── ottoman_pouf (seat without back)
├── storage
│   ├── cabinet
│   │   ├── sideboard_2_4_door
│   │   ├── tv_cabinet_low
│   │   └── nightstand_bedside_drawer
│   └── wardrobe
├── bed
│   └── bed_frame_upholstered
├── rug_rectangle
└── wall_panel_fluted
```

### 2.3 What Happens to Templates

**Existing 25 template JSONs** become **instances** of grammar rules:

```json
{
  "template_id": "dining_table_rectangular_4_leg",
  "grammar_type": "dining_table",
  "base_subtype": "legs",
  "leg_count": 4,
  "leg_profile": "square",
  "parameter_overrides": {
    "leg_corner_radius_mm": 10,
    "apron_height_pct": 0.25
  },
  "visual_signature": { ... }  // kept for classification
}
```

The template no longer hardcodes coordinate math. It says "I'm a dining table with 4 square legs" and the grammar engine knows how to construct that.

**New module needed:** `app/backend/grammar/` — grammar_engine.py, grammar_definitions.py, grammar_renderer.py

---

## 3. AI Council — Multi-Specialist Consensus Engine

**What you have:** `chat_agent.py` (general-purpose), `engineering_agent.py` (engineering), `comparison_agent.py` (comparison)

**What to build:** A council that runs multiple specialized agents in parallel and votes on consensus.

### 3.1 Specialist Agents

```
                        ┌────────────────────────┐
                        │        User Photo       │
                        └───────────┬────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │      Image Preprocessor        │
                    │  (adaptive threshold, contour  │
                    │   cleanup, skeletonization,    │
                    │   corner detection, line merge)│  ← Image2CAD preprocessing
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │       AI Council Engine        │
                    │  (runs agents, collects votes) │
                    │                               │
                    │  Specialist Agents:            │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │ Vision Agent             │  │  → "dining table, conf 97%"
                    │  │ (classifies furniture    │  │
                    │  │  type, materials, style)  │  │
                    │  └─────────────────────────┘  │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │ Dimension Agent          │  │  → "width 180cm, conf 85%"
                    │  │ (reads OCR + pixel dims) │  │
                    │  └─────────────────────────┘  │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │ Construction Agent       │  │  → "mortise & tenon, conf 82%"
                    │  │ (predicts joinery,       │  │
                    │  │  materials, build method)│  │
                    │  └─────────────────────────┘  │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │ Furniture Historian      │  │  → "matches Product X, conf 91%"
                    │  │ (searches DNA database   │  │
                    │  │  for similar products)   │  │
                    │  └─────────────────────────┘  │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │ Manufacturing Agent     │  │  → "should have apron, conf 90%"
                    │  │ (checks manufacturability│  │
                    │  │  construction viability)│  │
                    │  └─────────────────────────┘  │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │ DXF Agent               │  │  → plan for view generation
                    │  │ (plans views, dimensions,│  │
                    │  │  annotations to produce) │  │
                    │  └─────────────────────────┘  │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │       Consensus Engine         │
                    │  (weighted voting per field)   │
                    │  • Vision: 0.35 weight (type)  │
                    │  • Dimension: 0.25 (dims)      │
                    │  • Construction: 0.15 (joinery)│
                    │  • Historian: 0.15 (similarity)│
                    │  • Manufacturing: 0.10 (viable)│
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                           Canonical Furniture Graph
```

### 3.2 Consensus Voting Algorithm

```python
class ConsensusEngine:
    def resolve(self, votes: Dict[str, List[Vote]], field: str) -> ConsensusResult:
        """Weighted voting per field."""
        
        WEIGHTS = {
            "furniture_type": {"vision": 0.50, "historian": 0.30, "construction": 0.10, "manufacturing": 0.10},
            "dimensions": {"dimension": 0.50, "vision": 0.20, "historian": 0.20, "construction": 0.10},
            "material": {"construction": 0.40, "vision": 0.30, "historian": 0.20, "manufacturing": 0.10},
            "joinery": {"construction": 0.60, "manufacturing": 0.30, "historian": 0.10},
        }
        
        weights = WEIGHTS.get(field, {})
        weighted_votes = defaultdict(float)
        
        for agent_name, vote_list in votes.items():
            weight = weights.get(agent_name, 0.10)
            for vote in vote_list:
                weighted_votes[vote.value] += vote.confidence * weight
        
        best = max(weighted_votes, key=weighted_votes.get)
        total_weight = sum(weighted_votes.values())
        
        return ConsensusResult(
            value=best,
            confidence=weighted_votes[best] / total_weight if total_weight > 0 else 0,
            all_votes=dict(weighted_votes),
            agreement=len(weighted_votes) == 1,  # perfect agreement
        )
```

**New module needed:** `app/backend/council/` — engine.py, agents.py, consensus.py

**Modified modules:**
- `chat_agent.py` — becomes one voice in the council (DXF Agent)
- `engineering_agent.py` — becomes Construction Agent
- `comparison_agent.py` — becomes Quality Agent (after self-critic)

---

## 4. Progressive Resolution Pipeline

Instead of "detect everything → output", do stages that cascade:

```
Stage 1: Category
    ↓
"What kind of furniture?"
    → Table, Chair, Sofa, Cabinet, Bed, Rug, Other
    → Confidence: 97%

Stage 2: Family
    ↓
"Which family?"
    → Dining Table, Coffee Table, Console, Side Table
    → Confidence: 94%

Stage 3: Configuration
    ↓
"Which configuration?"
    → 4 Leg, Pedestal, Metal Frame, Trestle
    → Confidence: 91%

Stage 4: Materials
    ↓
"What materials?"
    → Wood Top, Metal Legs
    → Confidence: 85%

Stage 5: Dimensions
    ↓
"What dimensions?"
    → 1800x900x750mm
    → Confidence per dimension

Stage 6: Joinery
    ↓
"How is it built?"
    → Mortise & Tenon, Hidden Screws
    → Confidence: 82%

Stage 7: Components
    ↓
"What components?"
    → Top, 4 Legs, 2 Side Aprons, 2 End Aprons
    → Confidence per component

Stage 8: Geometry + Views
    ↓
"Generate drawings"
    → Top, Front, Side, Section A-A, Exploded

Stage 9: Annotations
    ↓
"Add dimensions, labels, BOM"
    → Complete shop drawing
```

**Why this is better:** Each stage constrains the next. If Stage 1 says "not a table" with 97%, Stage 3 never tries "4 leg" configuration. This eliminates entire classes of hallucination.

**What you have that feeds this:** The entire `cad_intelligence/` pipeline already does stages, but not as an explicit cascade with confidence gates.

**New module needed:** `app/backend/progressive_pipeline.py` — orchestrates stage gates

---

## 5. Manufacturing Intent Graph (MIG)

**What you have:** Individual resource files for joinery, construction rules, materials, supports. They're not connected into a manufacturing model.

**What to build:** The MIG lives INSIDE the CFG and adds manufacturing-specific data.

```python
@dataclass
class ManufacturingIntent:
    """Everything needed to BUILD the furniture, not just draw it."""
    
    # Materials
    material_specs: Dict[str, MaterialSpec]   # per component
    # e.g. "tabletop": {species: "European Oak", grade: "A", finish: "Satin Lacquer"}
    
    # Joinery
    joints: List[JointSpec]
    # e.g. {type: "mortise_tenon", components: ["apron", "leg"], depth_mm: 20}
    
    # Hardware
    hardware: List[HardwareSpec]
    # e.g. {type: "confirmat_screw", qty: 4, size: "7x50mm", components: ["apron", "leg"]}
    
    # Assembly
    assembly_order: List[AssemblyStep]
    # e.g. {step: 1, description: "Attach aprons to legs", tools: ["clamp", "screwgun"]}
    
    # Manufacturing
    manufacturing_notes: List[str]
    estimated_hours: float
    difficulty: str            # "easy" | "medium" | "hard" | "expert"
    cnc_ready: bool
    requires_special_tools: List[str]
    
    # Costing
    material_cost: float
    hardware_cost: float
    labor_cost: float
    total_estimated_cost: float
    
    # Packaging
    packaging_dims: Dict[str, float]
    shipping_volume_m3: float
    flat_pack_possible: bool
```

**What maps to this from existing code:**
- `resources/joinery/*.json` → JointSpec templates
- `resources/construction_rules/bed.json` → manufacturing_notes
- `backend-python/app/backend/resource_engine/closed_loop/recommendation_engine.py` → learning for better recommendations
- `backend-python/app/backend/cad_kernel/annotation_engine/bom.py` → BOM (partially)
- `backend-python/app/backend/sheet_layout/bom.py` → BOM layout

**New module needed:** `app/backend/manufacturing/` — mig_builder.py, cost_estimator.py, assembly_planner.py

---

## 6. Self-Critic — Render → Compare → Repair Loop

**What you have:** `anti_hallucination_validator.py` for confidence gating. No visual feedback loop.

**What to build:**

```
┌──────────────────────────────────────────────────────────────┐
│                     Self-Critic Loop                          │
│                                                               │
│  Initial CFG ──→ Render SVG ──→ Compare vs Original           │
│       │                         │                             │
│       │                    ┌────▼────────┐                    │
│       │                    │ Gap Regions │                    │
│       │                    │ per view     │                    │
│       │                    └────┬────────┘                    │
│       │                         │                             │
│       │              ┌──────────▼──────────┐                  │
│       │              │ Gap Classifier       │                 │
│       │              │ • missing_component  │                 │
│       │              │ • dimension_mismatch │                 │
│       │              │ • position_offset    │                 │
│       │              │ • extra_geometry     │                 │
│       │              │ • symmetry_violation │                 │
│       │              └──────────┬──────────┘                 │
│       │                         │                             │
│       │              ┌──────────▼──────────┐                  │
│       │              │ Repair Planner       │                 │
│       │              │ • re_detect region   │                 │
│       │              │ • adjust dimension   │                 │
│       │              │ • remove component   │                 │
│       │              │ • enforce constraint │                 │
│       │              │ • modify CFG         │                 │
│       │              └──────────┬──────────┘                 │
│       │                         │                             │
│       └──────────┬──────────────┘                             │
│                  │ (loop up to 3 iterations)                  │
│                  ▼                                            │
│           Gap Score < 5%? → Final CFG                         │
└──────────────────────────────────────────────────────────────┘
```

**What you already have** that maps here:
- `svg_exporter.py` — renders CFG → SVG
- `accuracy_benchmark.py` — can measure gap
- `anti_hallucination_validator.py` — existing repair feedback
- `feedback_learner.py` — records corrections (can be used for repair learning)

**New module needed:** `app/backend/self_critic/` — comparator.py, classifier.py, planner.py, loop.py

---

## 7. AI Confidence Heatmap

**What you have:** `EntityMetadata.source/confidence/evidence` on every entity. `ConfidencePanel.tsx` in frontend.

**What to build:** Visual heatmap overlaid on SVG preview.

```typescript
interface ConfidenceHeatmap {
  components: Array<{
    name: string;           // "tabletop"
    confidence: number;     // 0.95
    source: string;         // "measured"
    color: string;          // "#22c55e" (green)
    evidence: string[];     // ["ocr_box:12", "line:45"]
    boundingBox: BBox;      // for overlay
  }>;
  overall: {
    average: number;
    weakest: string;        // component with lowest confidence
    needsReview: string[];  // components below threshold
  };
}
```

**Visual treatment:**
- Green highlight (≥85%) → Trusted
- Yellow highlight (60-84%) → Check
- Red highlight (<60%) → Verify
- Click on component → show evidence + source
- "Needs review" panel → list of low-confidence items

**What you already have:** `CadConfidenceLegend.tsx`, `EntityMetadata` on every entity, `ConfidencePanel.tsx`

**Modified modules:**
- `frontend/components/CadCanvas.tsx` — add heatmap overlay
- `frontend/components/ConfidencePanel.tsx` — extend with clickable component list
- `backend-python/app/backend/entity_confidence.py` — add heatmap aggregation

---

## 8. The Complete Orchestrated Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER UPLOAD                                   │
│                    (Photo / Drawing / PDF)                           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  Stage 1: Image Preprocessor        ← Image2CAD preprocessing idea  │
│  • Adaptive threshold                                                │
│  • Contour cleanup                                                   │
│  • Skeletonization                                                   │
│  • Corner detection                                                   │
│  • Line merging                                                      │
│  Output: Clean binary image + detected line segments                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  Stage 2: AI Council (Parallel Specialists)  ← Multi-agent idea     │
│                                                                      │
│  ┌────────────┐ ┌─────────┐ ┌────────────┐ ┌──────────┐ ┌────────┐ │
│  │ Vision     │ │Dimension│ │Construction│ │Historian │ │Mfg     │ │
│  │ Agent      │ │ Agent   │ │ Agent      │ │Agent     │ │ Agent  │ │
│  └─────┬──────┘ └────┬────┘ └─────┬──────┘ └────┬─────┘ └───┬────┘ │
│        └──────────────┴────────────┴─────────────┴───────────┘      │
│                           │                                          │
│                      ┌────▼────┐                                    │
│                      │Consensus│ ← Weighted voting per field        │
│                      └────┬────┘                                    │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  Stage 3: Progressive Resolution          ← Img2CAD factorization  │
│                                                                     │
│  Level 1: Furniture Category      (Table / Chair / Sofa / ...)     │
│  Level 2: Family                  (Dining / Coffee / Console)       │
│  Level 3: Configuration           (4 Leg / Pedestal / Metal Frame) │
│  Level 4: Materials               (Wood / Metal / Stone / Glass)    │
│  Level 5: Dimensions              (Width / Depth / Height / Thick)  │
│  Level 6: Joinery                 (Mortise / Screw / Cam Lock)      │
│  Level 7: Components              (Top / Aprons / Legs / Stretcher) │
│                                                                     │
│  Each level constrains the next. Gates at <70% confidence trigger   │
│  re-resolution before proceeding.                                   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  Stage 4: Furniture Grammar Engine      ← CAD-Coder IER idea        │
│                                                                     │
│  • Loads grammar definition for detected furniture family           │
│  • Inherits rules from parent families                              │
│  • Applies configuration from Stage 3                               │
│  • Resolves proportions and constraints                             │
│  • Outputs ComponentNode tree with all geometry + relations         │
│                                                                     │
│  Also: Load Manufacturing Intent from resource files:               │
│  • joinery/*.json → JointSpec                                       │
│  • supports/*.json → SupportSpec                                    │
│  • geometry/*.json → Component template                             │
│  • manufacturers/*.json → MaterialSpec defaults                     │
│  • dimensions_styles/*.json → AnnotationSpec defaults               │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  Stage 5: Canonical Furniture Graph (CFG) ← THE unified data model  │
│                                                                     │
│  All previous stages write to CFG. No dicts, no ad-hoc objects.     │
│  CFG is the SINGLE SOURCE OF TRUTH for everything downstream.       │
│                                                                     │
│  CFG fields populated so far:                                       │
│  ✓ furniture_type, family                                           │
│  ✓ overall_dimensions, scale                                        │
│  ✓ grammar, components, relations                                   │
│  ✓ materials, joinery, hardware                                     │
│  ✓ provenance (which agent produced what)                           │
│  ✓ confidence_map (per-component confidence)                        │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  Stage 6: Engineering View Generation   ← Your existing cad_kernel │
│                                                                     │
│  For each requested view:                                           │
│  • Top View       → cad_kernel/view_generator/projection.py        │
│  • Front View     → cad_kernel/view_generator/projection.py        │
│  • Side View      → cad_kernel/view_generator/projection.py        │
│  • Section A-A    → cad_kernel/section_generator/pipeline.py       │
│  • Section B-B    → cad_kernel/section_generator/pipeline.py       │
│  • Exploded View  → cad_kernel/view_generator/exploded_view.py     │
│                                                                     │
│  For each view:                                                     │
│  • Hidden line removal → cad_kernel/hidden_line/pipeline.py        │
│  • Centerlines        → cad_kernel/hidden_line/centerline_gen.py   │
│  • Dimension placement → annotation_engine/layout.py               │
│  • Leaders + notes    → annotation_engine/leaders.py               │
│  • Title block        → sheet_layout/titleblock.py                 │
│                                                                     │
│  Each view gets its own section in the CFG                          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  Stage 7: BOM + Cost + Assembly Generation                          │
│                                                                     │
│  • Bill of Materials → cad_kernel/sheet_layout/bom.py              │
│  • Material cost     → manufacturing/cost_estimator.py (NEW)       │
│  • Assembly guide    → manufacturing/assembly_planner.py (NEW)     │
│  • Estimated hours   → manufacturing/cost_estimator.py             │
│  • Packing estimate  → manufacturing/packaging.py (NEW)            │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  Stage 8: Export                  ← Your existing exporters          │
│                                                                     │
│  • DXF Export  → dxf_exporter.py (reads from CFG)                  │
│  • SVG Preview → svg_exporter.py (reads from CFG)                  │
│  • PDF Export  → pdf_exporter.py (reads from CFG)                  │
│  • FreeCAD     → freecad_exporter.py (reads from CFG)              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  Stage 9: Self-Critic Loop           ← CADReasoner render-compare  │
│                                                                     │
│  RENDER COMPARE REPAIR (up to 3 iterations):                       │
│                                                                     │
│  1. Render SVG from current CFG                                    │
│  2. Compare rasterized SVG vs original image                       │
│  3. Classify gap regions: missing/hallucinated/misaligned          │
│  4. If gap score < 5%: DONE                                        │
│  5. Plan repair actions per gap type                               │
│  6. Apply repairs to CFG                                           │
│  7. Goto 1                                                         │
│                                                                     │
│  After loop: Write repair record to CFG.corrections[]              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  Stage 10: User Review + Correction                                 │
│                                                                     │
│  • Heatmap overlay (green/yellow/red per component)                │
│  • User edits dimension via slider → CFG update                    │
│  • User changes material → CFG update                              │
│  • User toggles visibility → CFG update                            │
│  • User corrects furniture type → re-trigger from Stage 2          │
│  • ALL corrections recorded → feedback_learner.py                  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  Stage 11: Continuous Learning                                      │
│                                                                     │
│  • feedback_learner.py analyzes correction patterns                │
│  • Echo Dracher updates PreferenceModel                            │
│  • closed_loop/delta_engine detects template drift                 │
│  • template_ranking adjusts recommendation weights                  │
│  • Style presets auto-suggest based on user history                 │
│                                                                     │
│  Every user becomes training data.                                 │
│  1000 users × 5 corrections each = 5000 correction patterns        │
│  → Your own manufacturing dataset (impossible to replicate)        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. Implementation Roadmap — What to Build, In Order

This does NOT replace anything. Each addition layers on top of existing code.

### Phase 0: CFG Data Model (1 week)
**New module:** `app/backend/cfg/models.py`

Build the `FurnitureGraph` dataclass, `ComponentNode`, `ComponentRelation`, `JointSpec`, `MaterialSpec`, `HardwareSpec`, `BillOfMaterials`, `ProvenanceGraph`, `ConfidenceMap`.

**What connects to existing code:**
- `ComponentNode` ← merging `ComponentGraph.ComponentNode` + `drawing_builders.ComponentNode`
- `ComponentRelation` ← new, but relationship detection uses existing geometry_utils
- `ProvenanceGraph` ← inherits from `unified_router.ProvenanceValue`
- `EntityMetadata` ← already exists in drawing_model.py

### Phase 1: Progressive Resolution Pipeline (1 week)
**New module:** `app/backend/progressive_pipeline.py`

Build the stage-gated cascade. Each stage outputs a more specific CFG. Gates check confidence thresholds.

**What maps to existing code:**
- Stage 1 (Category) → already in `furniture_classifier.py`
- Stage 2 (Family) → already in `product_classifier.py`
- Stage 3 (Configuration) → partially in `template_selector.py`
- Stage 4-7 → partially in `visual_ratio_scaler.py`, `reference_ratio_solver.py`
- **No existing module is removed.** The pipeline just orchestrates them.

### Phase 2: Furniture Grammar Engine (1.5 weeks)
**New module:** `app/backend/grammar/engine.py`, `definitions.py`, `renderer.py`

**What maps to existing code:**
- 25 template JSONs become grammar instances
- Grammar renderer replaces the ad-hoc coordinate math in drawing_builders.py
- `drawing_builders.py` functions delegate to grammar engine instead of hardcoded math
- Proportions come from `resources/furniture_templates/*.json` aspect_ratio_hint

### Phase 3: AI Council (1.5 weeks)
**New module:** `app/backend/council/engine.py`

**What maps to existing code:**
- Vision Agent = `chat_agent.py` with furniture_type prompt
- Dimension Agent = `dimension_associator.py` + `scale_solver.py` + OCR
- Construction Agent = `engineering_agent.py` + joinery resources
- Historian Agent = `reference_retriever.py` + visual DNA index
- Manufacturing Agent = manufacturing resources + construction rules
- DXF Agent = existing `drawing_builders.py` knowledge

**Each agent is a WRAPPER around existing modules,** not a replacement. The council just orchestrates them.

### Phase 4: Self-Critic Loop (2 weeks)
**New module:** `app/backend/self_critic/`

**What maps to existing code:**
- `svg_exporter.py` already renders
- `accuracy_benchmark.py` already measures
- `anti_hallucination_validator.py` already does some correction
- The loop just connects these with a gap classifier + repair planner

### Phase 5: Manufacturing Intent (1 week)
**New module:** `app/backend/manufacturing/`

**What maps to existing code:**
- `resources/joinery/*.json` → JointSpec loader
- `cad_kernel/annotation_engine/bom.py` → BillOfMaterials builder
- Style presets → MaterialSpec defaults
- Construction rules → manufacturing notes

### Phase 6: Frontend Upgrades (1.5 weeks)
**Modified modules:**
- `CadCanvas.tsx` → heatmap overlay, component click highlights
- `ConfidencePanel.tsx` → needs-review list, evidence display
- `ChatBox.tsx` → display "Council voted..." with per-agent breakdown
- New panel: Manufacturing View (BOM, cost, assembly)

### Phase 7: Continuous Learning Wiring (1 week)
**Modified modules:**
- `feedback_learner.py` → wire to ALL CFG corrections (not just dimensions)
- `closed_loop/delta_engine.py` → detect when grammar proportions need updating
- `template_ranking.py` → rank templates by user acceptance rate
- `style_presets.py` → auto-suggest presets from usage patterns

### Total: ~10-11 weeks for full build

---

## 10. Precedence & Priority

```
Priority     Phase     Why This Order
──────────────────────────────────────────────────
P0           CFG       Everything depends on it
P1           Pipeline  No intelligence without stages
P2           Grammar   No correct geometry without rules
P3           Council   No accuracy without consensus
P4           Self-Critic  No quality without feedback
P5           Mfg       Additive — works without it
P6           Frontend  Polish — works without it
P7           Learning  Polish — works without it
```

**But you can deliver value incrementally:**
- Week 1: CFG data model + migration of one template (e.g., round_pedestal_table)
- Week 2: Progressive pipeline for tables category
- Week 3: Grammar for table family → all 10 table types
- Week 4: AI Council for tables
- Week 5: Self-Critic for tables
- Week 6: Manufacturing intent for tables
- Weeks 7-10: Expand to seating, storage, beds

Each week delivers a working system with MORE furniture types supported, not broken features.

---

## 11. What Changed vs Current Architecture

| Current | New | Change |
|---------|-----|--------|
| Ad-hoc dicts between modules | CFG shared data model | NEW — the key structural change |
| 25 hardcoded templates | 25 grammar instances | Templates become data, not code |
| Single LLM call | Multi-agent council | Agents become specialized wrappers |
| Single-pass generation | Self-critic loop | ADDITIVE — no existing code changes |
| One DXF output | BOM + cost + assembly + DXF | ADDITIVE — new outputs only |
| Manual template authoring | Grammar inheritance | Templates become 10× simpler |
| Feedback stored per-user | Feedback evolves grammar | Learning becomes structural |
| Confidence metadata on entities | Heatmap overlay on CAD preview | ADDITIVE — visualization only |
| OpenCV → AI → template sequential | Progressive resolution cascade | Stages gate at confidence thresholds |
| Module-specific data formats | Everything speaks CFG | Integration cost pays for itself |

**Zero modules are removed. Zero existing pipelines are broken. Everything is additive or wrapping.**

---

## 12. What Makes This a Moat

1. **Canonical Furniture Graph** — Once all modules speak CFG, adding a new furniture type requires: new grammar definition (50 lines) + resource files (existing). No new code. No other system has this.

2. **Continuous Learning from User Corrections** — Most systems train once and ship. Your system gets better with every DXF download. After 5000 user corrections, your furniture historian can spot a product from its silhouette with >95% accuracy. This data is impossible to replicate.

3. **Manufacturing Intent** — Most Image→CAD systems output a shape. You output a manufacturing-ready engineering package: materials, joinery, BOM, cost, assembly, CNC. Furniture manufacturers pay 10× more for this than for a DXF.

4. **Furniture DNA Database** — 101 families, 259 products, growing with every crawl. No competitor has a structured furniture engineering database. This becomes the training set for everything.

5. **Self-Critic Loop** — Single-pass AI is inherently limited. Your render→compare→repair loop means the system verifies its own work. Every iteration catches errors the first pass missed. No other app does this (yet).

6. **Furniture Grammar** — Templates hardcode knowledge. Grammar LEARNS knowledge. When a user corrects "coffee table height should be 45cm not 40cm", the grammar adjusts the proportion rule for ALL coffee tables, not just that one.

7. **AI Council** — One model hallucinates. Seven models voting together hallucinate 7× less. The vision agent says "table", the construction agent says "has apron", the historian says "matches Product X" — the consensus is stronger than any single model.
