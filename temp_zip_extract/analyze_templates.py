"""Analyze the 25 HomeU furniture templates for categories, dimensions, and parts."""
import json, os
from collections import defaultdict

d = r'C:\Users\user\Desktop\autocad-scaler-digitizer-upgraded\temp_zip_extract\homeu_template_upgrade\resources\furniture_templates'
cat_map = defaultdict(list)
dim_map = defaultdict(set)
all_cats = set()

for f in sorted(os.listdir(d)):
    if not f.endswith('.json') or f.startswith('_'):
        continue
    with open(os.path.join(d, f), encoding='utf-8') as fp:
        t = json.load(fp)
    tid = t['template_id']
    cat = t.get('category', 'unknown')
    cat_map[cat].append(tid)
    all_cats.add(cat)
    for dim in t.get('required_dimensions', []):
        dim_map[cat].add(dim)

print(f"Total templates: {sum(len(v) for v in cat_map.values())}")
print(f"Unique categories: {len(cat_map)}")
print()
for cat in sorted(cat_map):
    templates = cat_map[cat]
    dims = sorted(dim_map.get(cat, []))
    print(f"\n## {cat} ({len(templates)} templates)")
    print(f"Required dims: {', '.join(dims)}")
    for tid in sorted(templates):
        print(f"  - {tid}")

print(f"\n\nAll categories: {sorted(all_cats)}")
print(f"Current KNOWN_TYPES in routes.py: round_pedestal_table, rectangular_table, cabinet, sofa, coffee_table, dining_chair, chair, wardrobe, reception_counter, bed_headboard, asymmetric_pedestal_table, oval_pedestal_table, console_table, office_desk, side_table, lounge_chair, nightstand, bed, sideboard, tv_console")
