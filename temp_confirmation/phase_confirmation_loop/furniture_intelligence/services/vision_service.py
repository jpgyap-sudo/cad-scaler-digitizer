from __future__ import annotations
import base64, json, os
from pathlib import Path
from typing import Optional
from furniture_intelligence.schemas.furniture_analysis import FurnitureAnalysis
from furniture_intelligence.services.vision_prompt import VISION_SYSTEM_PROMPT, VISION_USER_PROMPT


def _image_to_data_url(path: str) -> str:
    ext = Path(path).suffix.lower().replace('.', '') or 'png'
    mime = 'jpeg' if ext in ['jpg', 'jpeg'] else ext
    data = base64.b64encode(Path(path).read_bytes()).decode('utf-8')
    return f'data:image/{mime};base64,{data}'


def analyze_image_openai(image_path: str, model: str = 'gpt-4o') -> FurnitureAnalysis:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': VISION_SYSTEM_PROMPT},
            {'role': 'user', 'content': [
                {'type': 'text', 'text': VISION_USER_PROMPT},
                {'type': 'image_url', 'image_url': {'url': _image_to_data_url(image_path)}}
            ]}
        ],
        response_format={'type': 'json_object'},
        temperature=0.1,
    )
    raw = resp.choices[0].message.content or '{}'
    return FurnitureAnalysis.model_validate_json(raw)


def analyze_image_gemini(image_path: str, model: str = 'gemini-2.5-pro') -> FurnitureAnalysis:
    import google.generativeai as genai
    from PIL import Image
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    m = genai.GenerativeModel(model_name=model, system_instruction=VISION_SYSTEM_PROMPT)
    resp = m.generate_content([VISION_USER_PROMPT, Image.open(image_path)])
    text = (resp.text or '').strip()
    if text.startswith('```'):
        text = text.strip('`').replace('json\n', '', 1)
    return FurnitureAnalysis.model_validate_json(text)


def sample_melina_analysis() -> FurnitureAnalysis:
    return FurnitureAnalysis.model_validate({
        'product_name': 'Melina Coffee Table',
        'category': 'coffee_table',
        'design_family': ['modern luxury', 'sculptural pedestal', 'stone and brass'],
        'top_shape': 'oval',
        'base_type': 'truncated_cone',
        'components': [
            {'id':'top','type':'tabletop','label':'thin oval stone tabletop','shape':'oval','material':'stone','finish':'honed grey terrazzo/marble','confidence':0.96},
            {'id':'bowl','type':'recessed_bowl','label':'recessed circular brass bowl','shape':'circle','material':'brass','finish':'brushed brass','confidence':0.98},
            {'id':'base','type':'pedestal','label':'tapered truncated cone brass pedestal','shape':'truncated_cone','material':'brass','finish':'brushed brass','confidence':0.95}
        ],
        'relationships': {
            'top': {'supported_by': 'base', 'overhang': 'large'},
            'bowl': {'position': 'recessed into tabletop', 'alignment': 'near center'},
            'base': {'alignment': 'centered under top'}
        },
        'required_views': ['top','front','side','section','isometric'],
        'assumptions': ['No visible legs or apron', 'Hidden mounting plate under stone top', 'Base is hollow metal shell'],
        'uncertainty': {'exact_dimensions':0.7, 'bowl_offset':0.35},
        'confidence': 0.94
    })
