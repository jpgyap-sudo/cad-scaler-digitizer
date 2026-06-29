from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.furniture_intelligence.schemas.furniture_analysis import FurnitureAnalysis, TemplateProposal
from app.backend.resource_paths import resolve_resources_dir

_RESOURCES_DIR = resolve_resources_dir(Path(__file__))

# Load from ALL template directories
TEMPLATE_DIRS = [
    _RESOURCES_DIR / 'furniture_templates',
    _RESOURCES_DIR / 'product_catalog' / 'templates',
]

logger = logging.getLogger('template_matcher')

# Category extraction from filenames — maps common filename patterns to categories
FILENAME_CATEGORY_MAP = [
    (r'(?i)center_table', 'center_table'),
    (r'(?i)coffee_table|coffee.table', 'coffee_table'),
    (r'(?i)console_table', 'console_table'),
    (r'(?i)dining_table', 'dining_table'),
    (r'(?i)dining_chair', 'dining_chair'),
    (r'(?i)bar_stool', 'bar_stool'),
    (r'(?i)side_table', 'side_table'),
    (r'(?i)nightstand|bedside', 'nightstand'),
    (r'(?i)tv_console|tv_cabinet|media_console', 'tv_console'),
    (r'(?i)sideboard|side_board|buffet', 'sideboard'),
    (r'(?i)armchair|arm_chair', 'armchair'),
    (r'(?i)lounge_chair', 'lounge_chair'),
    (r'(?i)sofa|settee|couch', 'sofa'),
    (r'(?i)sectional', 'sectional'),
    (r'(?i)ottoman|pouf', 'ottoman'),
    (r'(?i)bench|chaise', 'bench'),
    (r'(?i)office_desk|desk', 'desk'),
    (r'(?i)bookcase|bookshelf|shelf', 'bookshelf'),
    (r'(?i)wardrobe|armoire|closet', 'wardrobe'),
    (r'(?i)cabinet|credenza', 'cabinet'),
    (r'(?i)bed.*frame|bed_frame|platform.*bed', 'bed_frame'),
    (r'(?i)headboard', 'headboard'),
    (r'(?i)rug|runner|mat', 'rug'),
    (r'(?i)pendant|chandelier|ceiling.*light', 'pendant_light'),
    (r'(?i)table_lamp|table.*lamp|tablelamp', 'table_lamp'),
    (r'(?i)floor_lamp|floor.*lamp', 'floor_lamp'),
    (r'(?i)wall.*panel|wpc.*panel', 'wall_panel'),
    (r'(?i)sconce|wall.*light', 'wall_sconce'),
    (r'(?i)throw.*pillow|cushion|pillow', 'throw_pillow'),
    (r'(?i)ceiling.*fan|ceiling_fan', 'ceiling_fan'),
    (r'(?i)mirror', 'mirror'),
    (r'(?i)planter|pot|vase', 'planter'),
    (r'(?i)stone.*slab|marble.*slab|sintered.*stone', 'stone_slab'),
    (r'(?i)oval.*pedestal|sculptural.*pedestal', 'oval_pedestal_table'),
    (r'(?i)round.*pedestal|single.*pedestal|pedestal.*table', 'round_pedestal_table'),
    (r'(?i)rectangular.*table|4.*leg.*table|four.*leg.*table', 'rectangular_table'),
]

# Load visual DNA index for scoring enhancement
_DNA_CACHE: Optional[Dict[str, Any]] = None

def get_visual_dna() -> Dict[str, Any]:
    global _DNA_CACHE
    if _DNA_CACHE is None:
        dna_path = _RESOURCES_DIR / 'product_catalog' / 'visual_dna_index.json'
        if dna_path.exists():
            try:
                _DNA_CACHE = json.loads(dna_path.read_text(encoding='utf-8'))
                logger.info(f"Loaded visual DNA index: {len(_DNA_CACHE)} entries")
            except Exception as e:
                logger.warning(f"Failed to load visual DNA index: {e}")
                _DNA_CACHE = {}
        else:
            _DNA_CACHE = {}
    return _DNA_CACHE


def _infer_category_from_filename(filename: str) -> Optional[str]:
    """Extract category from template filename using regex patterns."""
    for pattern, category in FILENAME_CATEGORY_MAP:
        if re.search(pattern, filename):
            return category
    return None


def normalize_template(t: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a template dict — fill missing category from filename."""
    t = dict(t)  # copy
    # Infer category from filename if missing
    if not t.get('category') or t.get('category') in ('NO_CAT', 'Furniture', ''):
        fname = t.get('template_id', '') or t.get('file', '')
        inferred = _infer_category_from_filename(fname)
        if inferred:
            t['category'] = inferred
            logger.debug(f"Inferred category '{inferred}' from filename '{fname}'")
    return t


def load_templates() -> List[Dict[str, Any]]:
    """Load templates from ALL template directories."""
    results = []
    seen_ids = set()
    
    for template_dir in TEMPLATE_DIRS:
        if not template_dir.exists():
            continue
        for p in sorted(template_dir.glob('*.json')):
            if p.name.startswith('_registry'):  # skip registry
                continue
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                # Set template_id from filename if missing
                if not data.get('template_id'):
                    data['template_id'] = p.stem
                data['file'] = p.stem
                # Deduplicate by template_id
                tid = data.get('template_id', p.stem)
                if tid not in seen_ids:
                    seen_ids.add(tid)
                    results.append(normalize_template(data))
            except Exception as e:
                logger.warning(f"Malformed template JSON: {p} — {e}")
    
    # Also load pack's own templates
    local_dir = Path(__file__).resolve().parents[1] / 'templates'
    if local_dir.exists():
        for p in sorted(local_dir.glob('*.json')):
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                tid = data.get('template_id', p.stem)
                if tid not in seen_ids:
                    seen_ids.add(tid)
                    results.append(normalize_template(data))
            except Exception:
                pass
    
    logger.info(f"Loaded {len(results)} templates from {len(TEMPLATE_DIRS)} directories")
    return results


def _has_component(analysis: FurnitureAnalysis, type_name: str) -> bool:
    return any(c.type == type_name or type_name in c.label.lower() for c in analysis.components)


def _category_match(analysis_cat: str, template_cat: str) -> bool:
    """B-4 FIX: Normalized category matching with alias map."""
    if not template_cat:
        return False
    norm = analysis_cat.lower().replace('-', '_').replace(' ', '_').strip()
    tcat = template_cat.lower().replace('-', '_').replace(' ', '_').strip()
    if norm == tcat:
        return True
    # Alias map: AI category → expected template category
    alias = {
        'coffee_table': 'center_table',
        'center_table': 'coffee_table',
        'dining_table': 'rectangular_table',
        'round_pedestal_table': 'center_table',
        'dining_chair': 'chair',
        'bed': 'bed_headboard',
        'oval_pedestal_table': 'dining_table',
        'console_table': 'console_table',
        'office_desk': 'office_desk',
        'side_table': 'side_table',
    }
    return alias.get(norm) == tcat or alias.get(tcat) == norm


def _score_via_required_components(analysis: FurnitureAnalysis, template: Dict[str, Any]) -> float:
    """Score using pack schema: required_components (list of {type, shape, material})."""
    score = 0.0
    if _category_match(analysis.category, template.get('category', '')):
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
    if _category_match(analysis.category, template.get('category', '')):
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
    # DNA boost: match template against visual_dna_index for archetype score
    dna = get_visual_dna()
    tid = template.get('template_id', '')
    if tid in dna:
        dna_entry = dna[tid]
        archetype = dna_entry.get('archetype_score', 0.0)
        if archetype > 0:
            score += min(archetype * 0.15, 0.15)  # up to 0.15 boost for confident DNA matches
        # Component graph overlap boost
        dna_comp = set(dna_entry.get('component_graph', []))
        if dna_comp:
            analysis_comp = set(c.type for c in analysis.components)
            overlap = len(dna_comp & analysis_comp) / max(len(dna_comp), 1)
            score += min(overlap * 0.10, 0.10)  # up to 0.10 for component overlap
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
    """B-5 FIX: Generate uncertainty questions dynamically from analysis.
    For each dimension with high uncertainty, generate a question.
    """
    q = []
    uncertainty = analysis.uncertainty or {}
    
    # Shape questions (furniture-agnostic)
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
    
    # Dynamic questions from uncertainty keys — ANY field with confidence < 0.6
    for field, conf in uncertainty.items():
        if field in ('top_shape', 'base_type', 'bowl_offset'):
            continue  # Already handled above
        if conf < 0.6:
            q.append({
                'field': field,
                'question': f'Is the {field.replace("_", " ")} correct?',
                'options': ['yes', 'no', 'unknown']
            })
    
    # If we have detected components with low confidence, ask about them
    for comp in analysis.components:
        if comp.confidence < 0.6:
            q.append({
                'field': f'components.{comp.id}.type',
                'question': f'Is this a {comp.label}?',
                'options': ['yes, correct', 'no, different type', 'unknown']
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
