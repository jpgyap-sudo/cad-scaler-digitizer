# Pipeline Architecture & Future Integration

## Current Pipeline (4-stage)

```
[Product URL] 
    ↓ Crawl (crawl_to_dxf.py)
  [Shopify JSON + Product Images]
    ↓
  ┌──────────────────────────────────────────────────────────────┐
  │ Stage 1: Classify (furniture_classifier.py + 3-stage DNA)   │
  │   393 DNA entries seeded from Shopify batch files            │
  │   Self-filling via enrich_dna_from_crawl()                   │
  └──────────────────────────────────────────────────────────────┘
    ↓
  ┌──────────────────────────────────────────────────────────────┐
  │ Stage 2: Dimension Extraction (crawl_to_dxf.py)              │
  │   Shopfy JSON variant parsing → width_cm, depth_cm,         │
  │   height_cm. Pattern A (W×L×H), Pattern B (Shopify JSON),   │
  │   Pattern C (JSON-LD), Pattern D (scan). Width/depth sanity  │
  │   swap for D×W×H order.                                      │
  └──────────────────────────────────────────────────────────────┘
    ↓
  ┌──────────────────────────────────────────────────────────────┐
  │ Stage 3: Multi-View SVG Extraction (Gemini/GPT-4o)          │
  │   Single API call → 4 panels (1200×300):                    │
  │     Panel 1: FRONT view (observed from photo)               │
  │     Panel 2: SIDE view (estimated from edge profiles)        │
  │     Panel 3: TOP view (estimated from top surface)           │
  │     Panel 4: ISOMETRIC (3D projection)                      │
  │   3-tier fallback: Flash → Pro → GPT-4o → GPT-4o-mini      │
  │   SVG parsed via xml.etree.ElementTree → regex → position   │
  │   Coordinates extracted server-side (not from AI)           │
  └──────────────────────────────────────────────────────────────┘
    ↓
  ┌──────────────────────────────────────────────────────────────┐
  │ Stage 4: DXF Generation (dxf_exporter.py)                   │
  │   5 views in DXF: FRONT, TOP, SIDE, ISOMETRIC, HERO        │
  │   HERO view = Gemini-traced outline overlayed on FRONT      │
  │   + standalone to the right. Scale-detected from existing   │
  │   DXF bounding box.                                          │
  └──────────────────────────────────────────────────────────────┘
    ↓
  [5-View DXF File]
```

## Planned: StarVector Integration

### Problem

Current Stage 3 (Multi-View SVG) has these pain points:
- **Expensive**: Gemini/GPT-4o API costs per call
- **Inconsistent**: SVG format varies between calls and models
- **Verbose**: 3-6K chars per SVG, with noise and redundant data
- **Slow**: 60-120s per call, 8 retries when overloaded

### Solution: Hybrid Gemini + StarVector

```
  ┌──────────────────────────────────────────────────────────────┐
  │ Stage 3a: Gemini-2.5-Flash (CHEAP, FAST)                    │
  │   Component detection only: "tabletop at (x,y), left_leg"   │
  │   Returns bounding boxes + component labels. ~5s, ~$0.001   │
  └──────────────────────────────────────────────────────────────┘
    ↓ per component
  ┌──────────────────────────────────────────────────────────────┐
  │ Stage 3b: StarVector-1B (CPU, no GPU needed)                │
  │   For each component bounding box → clean SVG path          │
  │   Compact (~200 chars per component), valid, consistent     │
  │   Trained on 2M SVG samples (icons, diagrams, charts)       │
  │   ~5-10s per component on 4-vCPU. 5 components ≈ 40s       │
  └──────────────────────────────────────────────────────────────┘
    ↓
  ┌──────────────────────────────────────────────────────────────┐
  │ Stage 3c: Component → DXF Merger                            │
  │   Deterministic conversion of clean SVG paths to DXF        │
  │   POLYLINE entities. No AI involved. Error-free.            │
  └──────────────────────────────────────────────────────────────┘
```

### Benefits

| Metric | Current | Hybrid (planned) | Improvement |
|--------|---------|------------------|-------------|
| API cost per call | $0.01-0.05 (GPT-4o) | $0.001 (Gemini detection only) | 10-50x cheaper |
| SVG consistency | Varies per model × call | Deterministic (StarVector) | 100% consistent |
| SVG size | 3-6K chars | ~1K chars (5 components × 200) | 3-6x smaller |
| Latency | 60-120s | ~45s (5s detection + 40s rendering) | ~2x faster |
| Component separation | Inconsistent `data-view` | Built-in (one path per component) | Guaranteed |
| Runs on | Cloud API | Local CPU (VPS) | No API dependency |

### Implementation Plan

**Phase 1 — Evaluate StarVector-1B on VPS (this sprint)**:
1. Pull StarVector-1B from HuggingFace (~2GB download)
2. Benchmark CPU inference speed on 4-vCPU VPS
3. Compare SVG quality vs Gemini/GPT-4o on 10 test products
4. Decide: use StarVector for all components, or only for cleanup

**Phase 2 — Optimize (next sprint)**:
1. ONNX conversion for 2x faster CPU inference
2. Parallel component processing (one component per CPU core)
3. Cache frequent components (common leg shapes, tabletop shapes)

**Phase 3 — Fine-tune (future)**:
1. Fine-tune StarVector on our 300+ template JSONs
2. Fine-tune on product_dna.json (393 products)
3. Result: StarVector that outputs furniture CAD SVGs directly
4. No Gemini needed at all for SVG generation

### Architecture Notes

- StarVector-1B (1B params) fits in ~4GB RAM, runs on CPU
- Model loaded once, reused across requests
- VLLM backend for faster inference (PagedAttention)
- Async pipeline: Gemini detection runs while StarVector processes previous product
- Fallback: if StarVector unavailable, revert to current Gemini-only pipeline

## Model Pricing & Performance

| Model | Cost per 1K calls | Latency | SVG Quality | Notes |
|-------|-------------------|---------|-------------|-------|
| gemini-2.5-flash | ~$0.50 | 30-60s | Good | Primary (fast, cheap) |
| gemini-2.5-pro | ~$3.50 | 30-60s | Better | Fallback when Flash overloaded |
| gpt-4o | ~$10.00 | 30-60s | Good | Fallback when both Gemini down |
| gpt-4o-mini | ~$1.50 | 20-40s | OK | Last resort |
| **StarVector-1B** (planned) | **$0.00** (self-hosted) | **5-10s/comp** | **Clean, compact** | **Hybrid with Gemini detection** |

## SVG Parsing Fallback Chain

```
xml.etree.ElementTree (namespace-aware)
    ↓ fails → regex with &quot; decode
    ↓ fails → position-based heuristic (x-coordinate → view)
    ↓ fails → geometric skeleton (svg_skeleton.py)
```

## View Assignment by X-Position (Fallback)

| Panel | X Range | View |
|-------|---------|------|
| 1 | 0-300 | FRONT |
| 2 | 310-600 | SIDE |
| 3 | 620-900 | TOP |
| 4 | 920-1200 | ISOMETRIC |
