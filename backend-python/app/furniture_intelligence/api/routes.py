from __future__ import annotations
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Query
from app.furniture_intelligence.schemas.furniture_analysis import UserCorrection
from app.furniture_intelligence.services.vision_service import analyze_image_openai, sample_melina_analysis
from app.furniture_intelligence.services.template_matcher import match_template
from app.furniture_intelligence.services.correction_engine import apply_corrections
from app.furniture_intelligence.geometry.preview_generator import generate_svg_preview
from app.furniture_intelligence.geometry.dxf_generator import generate_dxf

router = APIRouter(prefix='/furniture-intelligence', tags=['furniture-intelligence'])
WORK = Path('outputs')
WORK.mkdir(exist_ok=True)
# B-1 FIX: session_id → proposal dict, not module-level global
PROPOSALS: dict = {}


@router.post('/analyze')
async def analyze(file: UploadFile = File(...), provider: str = 'sample',
                  session_id: str = 'default'):
    path = WORK / file.filename
    path.write_bytes(await file.read())
    if provider == 'openai':
        analysis = analyze_image_openai(str(path))
    else:
        analysis = sample_melina_analysis()
    proposal = match_template(analysis)
    PROPOSALS[session_id] = proposal
    result = proposal.model_dump()
    result['proposal_id'] = session_id
    return result


@router.post('/confirm')
async def confirm(corrections: List[UserCorrection] = [],
                  proposal_id: Optional[str] = Query(default=None)):
    pid = proposal_id or 'default'
    proposal = PROPOSALS.get(pid)
    if proposal is None:
        return {'error': f'No proposal found for id={pid}. Call /analyze first.'}
    approved = apply_corrections(proposal, corrections)
    approved_path = WORK / f'approved_{pid}.json'
    approved_path.write_text(approved.model_dump_json(indent=2), encoding='utf-8')
    svg_path = generate_svg_preview(approved, str(WORK / f'preview_{pid}.svg'))
    dxf_path = generate_dxf(approved, str(WORK / f'output_{pid}.dxf'))
    return {
        'approved': approved.model_dump(),
        'preview_svg': svg_path,
        'dxf': dxf_path,
        'proposal_id': pid,
    }
