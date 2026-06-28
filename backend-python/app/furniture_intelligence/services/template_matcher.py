from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List
from app.furniture_intelligence.schemas.furniture_analysis import FurnitureAnalysis, TemplateProposal

TEMPLATE_DIR = Path(__file__).resolve().parents[4] / 'resources' / 'furniture_templates'


def load_templates(template_dir: Path = TEMPLATE_DIR) -> List[Dict[str, Any]]:
    results = []
    for p in sorted(template_dir.glob('*.json')):
        try:
            results.append(json.loads(p.read_text(encoding='utf-8')))
        except Exception:
            pass
    # Also load pack's own templates from local templates/ dir
    local_dir = Path(__file__).resolve().parents[1] / 'templates'
    if local_dir.exists():
        for p in sorted(local_dir.glob('*.json')):
            try:
                results.append(json.loads(p.read_text(encoding='utf-8')))
            except Exception:
                pass
    return results


def _has_component(analysis: FurnitureAnalysis, type_name: str) -> bool:
    return any(c.type == type_name or type_name in c.label.lower() for c in analysis.components)


def _score_via_required_components(analysis: FurnitureAnalysis, template: Dict[str, Any]) -> float:
    """Score using pack schema: required_components (list of {type, shape, material})."""
    score = 0.0
    if analysis.category == template.get('category'):
        score += 0.15
    text = ' '.join(analysis.design_family + [analysis.top_shape, analysis.base_type]
                    + [c.label for c in analysis.components]).lower()
    for kw in template.get('keywords', []):
        if kw.lower() in text:
            score += 0.06
    for comp in template.get('required_components', []):
        ctype = comp.get('type')
        shape = comp.get('shape')
        material = comp.get('material')
        matched = False
        for ac in analysis.components:
            if ctype and ctype in [ac.type, ac.label.lower()]:
                matched = True
            if shape and (ac.shape == shape or analysis.top_shape == shape or analysis.base_type == shape):
                matched = True
            if material and (ac.material and material in ac.material.lower()):
                matched = True
        if matched:
            score += 0.12
    return score


def _score_via_visual_signature(analysis: FurnitureAnalysis, template: Dict[str, Any]) -> float:
    """Score using HomeU schema: parts (list of {name, required}) + visual_signature ({positive, negative})."""
    score = 0.0
    if analysis.category == template.get('category'):
        score += 0.15
    text = ' '.join(analysis.design_family + [analysis.top_shape, analysis.base_type]
                    + [c.label for c in analysis.components]).lower()
    for kw in template.get('keywords', []):
        if kw.lower() in text:
            score += 0.06
    # Score against visual_signature positive/negative
    vsig = template.get('visual_signature', {})
    pos = vsig.get('positive', [])
    neg = vsig.get('negative', [])
    positive_hits = sum(1 for sig in pos if sig.lower() in text)
    negative_hits = sum(1 for sig in neg if sig.lower() in text)
    score += positive_hits * 0.10
    score -= negative_hits * 0.15
    # Score against required parts
    parts = template.get('parts', [])
    for part in parts:
        pname = part.get('name', '')
        required = part.get('required', False)
        if pname.lower() in text:
            score += 0.08 if required else 0.04
    return score


def score_template(analysis: FurnitureAnalysis, template: Dict[str, Any]) -> float:
    score = 0.0
    # Schema detection: pack's template has required_components; HomeU has parts + visual_signature
    if 'required_components' in template:
        score = _score_via_required_components(analysis, template)
    elif 'parts' in template and 'visual_signature' in template:
        score = _score_via_visual_signature(analysis, template)
    else:
        # Fallback: basic keyword + category match
        if analysis.category == template.get('category'):
            score += 0.15
        text = ' '.join(analysis.design_family + [analysis.top_shape, analysis.base_type]
                        + [c.label for c in analysis.components]).lower()
        for kw in template.get('keywords', []):
            if kw.lower() in text:
                score += 0.06
    # Special-case boost for oval_sculptural_pedestal_bowl (pack's template)
    if template.get('template_id') == 'ct_oval_sculptural_pedestal_bowl':
        if analysis.top_shape == 'oval':
            score += 0.18
        if analysis.base_type in ['truncated_cone', 'pedestal']:
            score += 0.18
        if _has_component(analysis, 'recessed_bowl'):
            score += 0.18
    return min(score, 1.0)


def build_questions(analysis: FurnitureAnalysis) -> List[Dict[str, Any]]:
    q = []
    uncertainty = analysis.uncertainty or {}
    if uncertainty.get('top_shape', 1.0) < 0.75 or analysis.top_shape in ['irregular', 'unknown']:
        q.append({
            'field': 'top_shape',
            'question': 'What is the tabletop shape?',
            'options': ['oval', 'circle', 'rectangle', 'rounded_rectangle', 'square']
        })
    if uncertainty.get('base_type', 1.0) < 0.75 or analysis.base_type == 'unknown':
        q.append({
            'field': 'base_type',
            'question': 'What type of base/support does it have?',
            'options': ['truncated_cone', 'pedestal', 'four_legs', 'panel_legs', 'solid_block', 'sled']
        })
    if uncertainty.get('bowl_offset', 1.0) < 0.75 and _has_component(analysis, 'recessed_bowl'):
        q.append({
            'field': 'relationships.bowl.alignment',
            'question': 'Is the brass bowl centered or offset?',
            'options': ['centered', 'slightly offset', 'unknown']
        })
    return q


def match_template(analysis: FurnitureAnalysis) -> TemplateProposal:
    templates = load_templates()
    if not templates:
        return TemplateProposal(
            template_id='fallback_generic',
            template_name='Generic Template',
            score=0.0,
            analysis=analysis,
            questions=build_questions(analysis)
        )
    scored = sorted(
        [(score_template(analysis, t), t) for t in templates],
        key=lambda x: x[0],
        reverse=True
    )
    best_score, best = scored[0]
    # Determine best template name
    tname = best.get('template_name') or best.get('template_id', 'unknown')
    return TemplateProposal(
        template_id=best['template_id'],
        template_name=tname,
        score=best_score,
        analysis=analysis,
        questions=build_questions(analysis)
    )
