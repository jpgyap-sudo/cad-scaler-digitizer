from __future__ import annotations
from copy import deepcopy
from typing import Dict, Any, List
from furniture_intelligence.schemas.furniture_analysis import TemplateProposal, UserCorrection, ApprovedTemplate
from furniture_intelligence.services.template_matcher import load_templates


def _set_path(obj: Dict[str, Any], path: str, value: Any):
    parts = path.split('.')
    cur = obj
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def default_parameters_for(template_id: str) -> Dict[str, float]:
    for t in load_templates():
        if t['template_id'] == template_id:
            return dict(t.get('default_parameters_mm', {}))
    return {}


def apply_corrections(proposal: TemplateProposal, corrections: List[UserCorrection]) -> ApprovedTemplate:
    data = proposal.analysis.model_dump()
    for c in corrections:
        _set_path(data, c.field, c.value)
    final = proposal.analysis.__class__.model_validate(data)
    return ApprovedTemplate(
        proposal=proposal,
        corrections=corrections,
        final_analysis=final,
        parameters_mm=default_parameters_for(proposal.template_id)
    )
