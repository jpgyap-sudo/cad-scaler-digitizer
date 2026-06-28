from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List
from furniture_intelligence.schemas.furniture_analysis import FurnitureAnalysis, TemplateProposal

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / 'templates'


def load_templates(template_dir: Path = TEMPLATE_DIR) -> List[Dict[str, Any]]:
    return [json.loads(p.read_text(encoding='utf-8')) for p in template_dir.glob('*.json')]


def _has_component(analysis: FurnitureAnalysis, type_name: str) -> bool:
    return any(c.type == type_name or type_name in c.label.lower() for c in analysis.components)


def score_template(analysis: FurnitureAnalysis, template: Dict[str, Any]) -> float:
    score = 0.0
    if analysis.category == template.get('category'):
        score += 0.15
    text = ' '.join(analysis.design_family + [analysis.top_shape, analysis.base_type] + [c.label for c in analysis.components]).lower()
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
    if template.get('template_id') == 'ct_oval_sculptural_pedestal_bowl':
        if analysis.top_shape == 'oval': score += 0.18
        if analysis.base_type in ['truncated_cone', 'pedestal']: score += 0.18
        if _has_component(analysis, 'recessed_bowl'): score += 0.18
    return min(score, 1.0)


def build_questions(analysis: FurnitureAnalysis) -> List[Dict[str, Any]]:
    q = []
    if analysis.uncertainty.get('top_shape', 1.0) < 0.75 or analysis.top_shape in ['irregular']:
        q.append({'field':'top_shape','question':'What is the tabletop shape?', 'options':['oval','circle','rectangle','rounded_rectangle']})
    if analysis.uncertainty.get('base_type', 1.0) < 0.75 or analysis.base_type == 'unknown':
        q.append({'field':'base_type','question':'What type of base/support does it have?', 'options':['truncated_cone','pedestal','four_legs','panel_legs','solid_block']})
    if analysis.uncertainty.get('bowl_offset', 1.0) < 0.75 and _has_component(analysis, 'recessed_bowl'):
        q.append({'field':'relationships.bowl.alignment','question':'Is the brass bowl centered or offset?', 'options':['centered','slightly offset','unknown']})
    return q


def match_template(analysis: FurnitureAnalysis) -> TemplateProposal:
    templates = load_templates()
    scored = sorted([(score_template(analysis, t), t) for t in templates], key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    return TemplateProposal(
        template_id=best['template_id'],
        template_name=best['template_name'],
        score=best_score,
        analysis=analysis,
        questions=build_questions(analysis)
    )
