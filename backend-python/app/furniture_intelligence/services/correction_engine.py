from __future__ import annotations
from copy import deepcopy
from typing import Dict, Any, List
from app.furniture_intelligence.schemas.furniture_analysis import (
    TemplateProposal, UserCorrection, ApprovedTemplate, FurnitureAnalysis,
)
from app.furniture_intelligence.services.template_matcher import load_templates


def _set_path(obj: Dict[str, Any], path: str, value: Any):
    parts = path.split('.')
    cur = obj
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def default_parameters_for(template_id: str) -> Dict[str, float]:
    for t in load_templates():
        if t.get('template_id') == template_id:
            return dict(t.get('default_parameters_mm', {}))
    return {}


def get_required_dimensions_for(template_id: str) -> Dict[str, float]:
    """B-3 FIX: Fallback to required_dimensions when default_parameters_mm not available.
    Derives sensible defaults from the template's required_dimensions list."""
    for t in load_templates():
        if t.get('template_id') == template_id:
            # First try explicit default_parameters_mm
            if t.get('default_parameters_mm'):
                return dict(t['default_parameters_mm'])
            # Next try parameters dict (spec.json format)
            params = t.get('parameters', {})
            if params:
                return {k: float(v) for k, v in params.items() if isinstance(v, (int, float))}
            # Fallback: generate from required_dimensions with reasonable defaults
            rd = t.get('required_dimensions', [])
            result = {}
            for dim_name in rd:
                # Assign sensible defaults per dimension type
                dim_lower = dim_name.lower()
                if 'height' in dim_lower or 'overall_height' in dim_lower:
                    result[dim_name] = 750 if 'table' in str(t.get('template_id','')) else 850
                elif 'width' in dim_lower or 'overall_width' in dim_lower:
                    result[dim_name] = 1200 if 'sofa' in str(t.get('template_id','')) else 800
                elif 'depth' in dim_lower or 'overall_depth' in dim_lower:
                    result[dim_name] = 600
                elif 'diameter' in dim_lower or 'dia' in dim_lower:
                    result[dim_name] = 800
                elif 'length' in dim_lower:
                    result[dim_name] = 1400
                elif 'thickness' in dim_lower or 'thick' in dim_lower:
                    result[dim_name] = 40
                elif 'leg' in dim_lower:
                    result[dim_name] = 40
                elif 'seat' in dim_lower:
                    result[dim_name] = 450
                elif 'arm' in dim_lower:
                    result[dim_name] = 220
                elif 'spacing' in dim_lower or 'gap' in dim_lower:
                    result[dim_name] = 30
                else:
                    result[dim_name] = 100
            return result
    return {}


def apply_corrections(proposal: TemplateProposal, corrections: List[UserCorrection]) -> ApprovedTemplate:
    data = proposal.analysis.model_dump()
    for c in corrections:
        _set_path(data, c.field, c.value)
    # B-2 FIX: Use direct class reference, not __class__
    final = FurnitureAnalysis.model_validate(data)
    params = default_parameters_for(proposal.template_id)
    if not params:
        # B-3 FIX: Fallback to required_dimensions-derived defaults
        params = get_required_dimensions_for(proposal.template_id)
    return ApprovedTemplate(
        proposal=proposal,
        corrections=corrections,
        final_analysis=final,
        parameters_mm=params
    )
