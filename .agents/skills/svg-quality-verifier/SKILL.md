---
name: svg-quality-verifier
description: Post-generation SVG quality verification agent. Sends the rendered SVG and original product photo to Gemini Vision to score shape accuracy, component completeness, and proportion correctness. Feeds a structured correction signal back into the dimension system.
---

# SVG Quality Verifier

## What it does

After the SVG is generated from a `DrawingModel`, this agent compares it against the original product photo using **Gemini 2.5 Flash** vision. It answers:

1. **Shape match (0–1):** Does the SVG outline match the product? (circle vs rectangle, single vs dual pedestal)
2. **Component score (0–1):** Does the SVG show all visible parts? (legs, tabletop thickness, backrest, shelves)
3. **Proportion score (0–1):** Are relative sizes correct? (legs too thick? tabletop too thin?)
4. **View completeness (0–1):** Are TOP, FRONT, and SIDE views all present and correct?

## When to trigger

- After every `/digitize/hybrid` or `/digitize/unified` response
- During crawl_processor batch jobs (async, after SVG saved)
- When `confidence_review.average_confidence < 0.70`

## Scoring thresholds

| Score | Action |
|-------|--------|
| ≥ 0.85 | Accept — return SVG as-is |
| 0.65–0.84 | Warn — add `quality_warnings` to response |
| < 0.65 | Reject — trigger `_repair_from_feedback()` with corrections |

## Repair signal format

```json
{
  "shape_match": 0.72,
  "component_score": 0.60,
  "proportion_score": 0.55,
  "view_completeness": 0.80,
  "issues": [
    "Legs are drawn too thick relative to tabletop width",
    "Tabletop thickness appears too thin for marble material",
    "No side view present"
  ],
  "corrections": {
    "leg_thickness_cm": { "current": 8, "suggested": 5, "reason": "visual proportion" },
    "top_thick_cm": { "current": 2, "suggested": 4, "reason": "marble slab typical 3-5cm" }
  },
  "performed": true
}
```

## Gemini prompt used

The verifier sends this prompt with both images:

```
You are reviewing a CAD shop drawing SVG against the original product photo.
Compare MEANING and STRUCTURE — not pixel-perfect match.

Score each dimension 0.0-1.0:
- shape_match: Does the outline match? (round/rect/oval, single/dual pedestal)
- component_score: Are all visible parts drawn? (legs, tabletop, backrest, shelves, etc.)
- proportion_score: Are relative sizes correct? (height:width ratio, leg thickness vs tabletop width)
- view_completeness: Are multiple views shown? (top + front + side for shop drawings)

For each issue, suggest a specific parameter correction if applicable.

Return JSON: {shape_match, component_score, proportion_score, view_completeness,
              issues: [strings], corrections: {param: {current, suggested, reason}},
              overall_quality: weighted_average}
```

## Files

| File | Purpose |
|------|---------|
| `backend-python/app/agents/svg_quality_verifier.py` | Agent implementation |
| `backend-python/app/backend/self_critic/loop.py` | Integration point (_adjust_dimension) |
| `.agents/skills/svg-quality-verifier/SKILL.md` | This file |
| `.agents/skills/svg-quality-verifier/resources/quality_thresholds.json` | Configurable thresholds |
