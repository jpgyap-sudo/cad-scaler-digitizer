---
name: dxf-verifier
description: Semantic DXF verification against source product photos using Gemini 2.5 Flash vision API. Judges shape, components, and proportions by comparing meaning (not pixels) between the photo and line drawing.
---

# DXF Verifier Skill

## What it does

After a DXF is generated, this agent sends both the original product photo and the rendered DXF line drawing to **Gemini 2.5 Flash** for semantic comparison. It answers three questions:

1. **Shape match (0-1):** Does the DXF outline match the product's actual shape? (Round table drawn as round? Rectangular table drawn as rectangular? Single pedestal vs dual pedestal?)

2. **Component score (0-1):** Does the DXF capture all visible components? (Legs, backrest, armrests, shelves, drawers, pedestal sections — everything visible in the photo should be in the DXF.)

3. **Proportion score (0-1):** Are the proportions of each component correct? (Seat too tall relative to back? Tabletop too thin? Pedestal too narrow?)

## Score blending

When Gemini verification runs (cloud_verified=True), the scores are blended into the overall comparison result:

- Cloud shape_match × 0.4
- Cloud component_score × 0.35
- Cloud proportion_score × 0.25
- **Total cloud weight: 45%** of the final overall score

## Prerequisites

| Requirement | Source |
|-------------|--------|
| `GEMINI_API_KEY` | Environment variable (set in `.env` or docker-compose) |
| `gemini-2.5-flash` | Google AI model (default, configurable via `GEMINI_OCR_MODEL`) |
| Python deps | `opencv-python`, `httpx`, `numpy` |

## Files

| File | Purpose |
|------|---------|
| `backend-python/app/agents/dxf_verifier_agent.py` | Agent implementation |
| `backend-python/app/agents/__init__.py` | Package exports |
| `.agents/dxf-verifier.agent.md` | Agent definition |
| `.agents/skills/dxf-verifier/SKILL.md` | This skill file |
| `backend-python/app/services/comparison_agent.py` | Integration (calls the agent) |

## Usage in code

```python
from app.agents import verify_dxf_with_gemini

result = await verify_dxf_with_gemini(
    product_image=original_img,
    dxf_raster=dxf_raster,
    furniture_type="rectangular_table",
    page_dimensions={"width_cm": 120, "depth_cm": 80, "overall_height_cm": 75},
)
```

The result dict includes:
```python
{
    "shape_match": 0.95,         # DXF outline matches product shape
    "component_score": 0.80,     # Most components captured
    "proportion_score": 0.70,    # Some proportion issues
    "issues": [
        "Legs in DXF are slightly thicker than in the photo",
        "Tabletop overhang is missing"
    ],
    "explanation": "Rectangular table with correct width-depth ratio, but legs are drawn thicker than the product shows",
    "performed": True
}
```

## Error handling

If Gemini is unavailable (no API key, network error, HTTP error), the agent returns:
```python
{"shape_match": 0.5, "component_score": 0.5, "proportion_score": 0.5,
 "issues": [error_message], "performed": False}
```

The calling code (comparison_agent.py) then falls back to local structured scoring without cloud input. The system degrades gracefully.

## When to use this skill

- Immediately after any DXF generation to verify output quality
- During batch processing to flag products that need manual review
- As a training signal: products with low shape_match indicate the AI classification or template selection was wrong
