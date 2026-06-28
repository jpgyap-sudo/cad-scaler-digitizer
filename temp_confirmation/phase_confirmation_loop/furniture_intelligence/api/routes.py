from __future__ import annotations
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File
from furniture_intelligence.schemas.furniture_analysis import UserCorrection
from furniture_intelligence.services.vision_service import analyze_image_openai, sample_melina_analysis
from furniture_intelligence.services.template_matcher import match_template
from furniture_intelligence.services.correction_engine import apply_corrections
from furniture_intelligence.geometry.preview_generator import generate_svg_preview
from furniture_intelligence.geometry.dxf_generator import generate_dxf

router = APIRouter(prefix='/furniture-intelligence', tags=['furniture-intelligence'])
WORK = Path('outputs')
WORK.mkdir(exist_ok=True)
LAST_PROPOSAL = None

@router.post('/analyze')
async def analyze(file: UploadFile = File(...), provider: str = 'sample'):
    global LAST_PROPOSAL
    path = WORK / file.filename
    path.write_bytes(await file.read())
    if provider == 'openai':
        analysis = analyze_image_openai(str(path))
    else:
        analysis = sample_melina_analysis()
    proposal = match_template(analysis)
    LAST_PROPOSAL = proposal
    return proposal.model_dump()

@router.post('/confirm')
async def confirm(corrections: List[UserCorrection] = []):
    if LAST_PROPOSAL is None:
        return {'error': 'No proposal yet. Call /analyze first.'}
    approved = apply_corrections(LAST_PROPOSAL, corrections)
    approved_path = WORK / 'approved_template.json'
    approved_path.write_text(approved.model_dump_json(indent=2), encoding='utf-8')
    svg_path = generate_svg_preview(approved, str(WORK / 'preview.svg'))
    dxf_path = generate_dxf(approved, str(WORK / 'output.dxf'))
    return {
        'approved': approved.model_dump(),
        'preview_svg': svg_path,
        'dxf': dxf_path
    }
