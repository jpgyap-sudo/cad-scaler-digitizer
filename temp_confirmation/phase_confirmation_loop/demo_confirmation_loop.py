from pathlib import Path
from furniture_intelligence.services.vision_service import sample_melina_analysis
from furniture_intelligence.services.template_matcher import match_template
from furniture_intelligence.services.correction_engine import apply_corrections
from furniture_intelligence.schemas.furniture_analysis import UserCorrection
from furniture_intelligence.geometry.preview_generator import generate_svg_preview
from furniture_intelligence.geometry.dxf_generator import generate_dxf

out = Path('outputs')
out.mkdir(exist_ok=True)

analysis = sample_melina_analysis()
proposal = match_template(analysis)
print('PROPOSED TEMPLATE:', proposal.template_name, 'score=', round(proposal.score, 2))
print('QUESTIONS:', proposal.questions)

# Example user correction. Leave empty if correct.
corrections = [
    UserCorrection(field='top_shape', value='oval', note='User confirmed oval, not circle'),
    UserCorrection(field='base_type', value='truncated_cone', note='User confirmed tapered brass pedestal')
]

approved = apply_corrections(proposal, corrections)
(out / 'melina_approved.json').write_text(approved.model_dump_json(indent=2), encoding='utf-8')
generate_svg_preview(approved, str(out / 'melina_preview.svg'))
generate_dxf(approved, str(out / 'melina_template.dxf'))

print('Generated:')
print(' - outputs/melina_approved.json')
print(' - outputs/melina_preview.svg')
print(' - outputs/melina_template.dxf')
