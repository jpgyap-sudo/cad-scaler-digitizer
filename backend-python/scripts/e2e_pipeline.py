"""Full E2E pipeline validation — validates all 18 templates, resolver, constraints."""
import sys, json
sys.path.insert(0, str(__file__).replace('scripts/e2e_pipeline.py', ''))

from app.resource_engine.template_loader import TemplateGraphLoader
from app.resource_engine.template_resolver import TemplateResolver, PRODUCT_TYPE_MAP

loader = TemplateGraphLoader().load()
resolver = TemplateResolver(loader)

errors = []
passed = 0

# 1. Load count
if loader.count < 18:
    errors.append(f"Expected >=18 templates, got {loader.count}")
passed += 1

# 2. All templates have required fields
for tpl in loader.list_all():
    for field in ['id', 'name', 'product_type', 'family', 'parameters', 'components', 'required_views']:
        if field not in tpl:
            errors.append(f"{tpl.get('id','?')} missing field '{field}'")
    for p in tpl.get('parameters', []):
        for pf in ['name', 'default', 'min_value', 'max_value']:
            if pf not in p:
                errors.append(f"{tpl['id']}.{p.get('name','?')} missing '{pf}'")
passed += 1

# 3. Every product_type maps to a template
unmapped_pts = []
for npt in PRODUCT_TYPE_MAP.values():
    if not loader.find_by_product_type(npt):
        unmapped_pts.append(npt)
if unmapped_pts:
    errors.append(f"Unmapped product_types: {unmapped_pts}")
passed += 1

# 4. Resolve all 18 types
tests = [
    ('round_pedestal_table',      {'top_diameter_cm':100}, 5),
    ('rectangular_table',         {'width_cm':180,'depth_cm':90}, 6),
    ('oval_pedestal_table',       {'length_cm':180,'depth_cm':100}, 6),
    ('console_table',             {'length_cm':120,'depth_cm':40}, 5),
    ('coffee_table',              {'width_cm':120,'depth_cm':60}, 4),
    ('side_table',                {'width_cm':50,'depth_cm':50}, 4),
    ('office_desk',               {'length_cm':140,'depth_cm':60}, 6),
    ('cabinet',                   {'width_cm':180,'depth_cm':45}, 5),
    ('tv_console',                {'width_cm':180,'depth_cm':45}, 4),
    ('nightstand',                {'width_cm':50,'depth_cm':42}, 4),
    ('wardrobe',                  {'width_cm':120,'depth_cm':60}, 4),
    ('bed',                       {'width_cm':183,'depth_cm':203,'overall_height_cm':40}, 4),
    ('bed_headboard',             {'width_cm':183,'overall_height_cm':100}, 3),
    ('sofa',                      {'width_cm':220,'depth_cm':95}, 6),
    ('lounge_chair',              {'width_cm':80,'depth_cm':85}, 4),
    ('dining_chair',              {'width_cm':52,'depth_cm':56}, 5),
    ('reception_counter',         {'width_cm':180,'depth_cm':80}, 5),
    ('asymmetric_pedestal_table', {'length_cm':180,'depth_cm':90}, 9),
]
for ftype, dims, expected_params in tests:
    try:
        r = resolver.resolve(ftype, dims)
        n = len(r['resolved_parameters'])
        if n != expected_params:
            errors.append(f"{ftype}: expected {expected_params} params, got {n}")
    except Exception as e:
        errors.append(f"{ftype}: resolve failed - {e}")
passed += 1

# 5. Constraint evaluation
# bed min size constraint should fire
r = resolver.resolve('bed', {'width_cm': 150})  # too small
bed_fail = [c['id'] for c in r['constraints'] if not c['passed']]
if 'bed_min_size' not in bed_fail:
    errors.append("bed_min_size constraint should have fired")
passed += 1

r2 = resolver.resolve('bed', {'width_cm': 203, 'depth_cm': 183})
bed_pass = [c['id'] for c in r2['constraints'] if not c['passed']]
if 'bed_min_size' in bed_pass:
    errors.append("bed_min_size constraint should pass with valid dims")
passed += 1

# 6. Family indexing
families = ['table', 'cabinet', 'bed', 'seating', 'desk', 'counter']
for fam in families:
    t = loader.find_by_family(fam)
    if not t:
        errors.append(f"Family '{fam}' has no templates")
passed += 1

# 7. Zero warnings with good dims
results = [resolver.resolve('rectangular_table', {'width_cm':180,'depth_cm':90,'overall_height_cm':75})]
results.append(resolver.resolve('sofa', {'width_cm':220,'depth_cm':95,'seat_height_cm':42}))
for r in results:
    if r['warnings']:
        errors.append(f"Unexpected warnings: {r['warnings']}")
passed += 1

print(f"E2E Results: {passed} checks, {len(errors)} errors")
if errors:
    for e in errors:
        print(f"  FAIL: {e}")
else:
    print("  ALL PASSED")
