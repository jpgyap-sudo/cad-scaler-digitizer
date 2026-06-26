"""Quick test: what does Tesseract read from a generated fixture image?"""
import sys
sys.path.insert(0, 'backend-python')
from app.backend.ocr_layout_parser import extract_layout

for fixture_name in ['round_table', 'rectangular_table', 'cabinet']:
    img_path = f'fixtures/{fixture_name}/reference.jpg'
    print(f'\n=== {fixture_name} ===')
    result = extract_layout(img_path)
    print(f'  Total boxes: {len(result.text_boxes)}')
    for d in result.dimension_labels[:8]:
        print(f'  DIM: text="{d.text}" value={d.value_cm} diam={d.is_diameter}')
    for t in result.text_boxes[:12]:
        if t.text_type != 'DIMENSION_LABEL':
            print(f'  TXT: [{t.x},{t.y}] text="{t.text}" type={t.text_type}')
