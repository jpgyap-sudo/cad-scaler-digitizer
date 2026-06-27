"""Test template loader and resolver end-to-end."""
import sys, traceback
sys.path.insert(0, str(__file__).replace('scripts/test_templates.py', ''))

from app.resource_engine.template_loader import TemplateGraphLoader
from app.resource_engine.template_resolver import TemplateResolver

loader = TemplateGraphLoader().load()
resolver = TemplateResolver(loader)

# Count our 18 templates
our_ids = sorted(t['id'] for t in loader.list_all()
                 if t.get('family') in ('table','cabinet','bed','seating','desk','counter'))
print(f'Our 18 templates: {len(our_ids)}')

# Test resolve for each major type
tests = [
    ('round_pedestal_table',      {'top_diameter_cm':100,'overall_height_cm':75}),
    ('rectangular_table',         {'width_cm':180,'depth_cm':90,'overall_height_cm':75}),
    ('oval_pedestal_table',       {'length_cm':180,'depth_cm':100,'overall_height_cm':75}),
    ('console_table',             {'length_cm':120,'depth_cm':40,'overall_height_cm':75}),
    ('coffee_table',              {'width_cm':120,'depth_cm':60,'overall_height_cm':38}),
    ('side_table',                {'width_cm':50,'depth_cm':50,'overall_height_cm':52}),
    ('office_desk',               {'length_cm':140,'depth_cm':60,'overall_height_cm':75}),
    ('cabinet',                   {'width_cm':180,'depth_cm':45,'overall_height_cm':80}),
    ('tv_console',                {'width_cm':180,'depth_cm':45,'overall_height_cm':60}),
    ('nightstand',                {'width_cm':50,'depth_cm':42,'overall_height_cm':50}),
    ('wardrobe',                  {'width_cm':120,'depth_cm':60,'overall_height_cm':200}),
    ('bed',                       {'width_cm':183,'depth_cm':203,'overall_height_cm':100}),
    ('bed_headboard',             {'width_cm':183,'overall_height_cm':100}),
    ('sofa',                      {'width_cm':220,'depth_cm':95,'overall_height_cm':78}),
    ('lounge_chair',              {'width_cm':80,'depth_cm':85,'overall_height_cm':78}),
    ('dining_chair',              {'width_cm':52,'depth_cm':56,'overall_height_cm':82}),
    ('reception_counter',         {'width_cm':180,'depth_cm':80,'overall_height_cm':110}),
    ('asymmetric_pedestal_table',  {'length_cm':180,'depth_cm':90,'overall_height_cm':75}),
]
passed = 0
failed = 0
for ftype, dims in tests:
    try:
        r = resolver.resolve(ftype, dims)
        name = r['template']['name']
        rp = r['resolved_parameters']
        views = r['component_views']
        cons = r['constraints']
        warn = r['warnings']
        print(f'  OK  {ftype:35s} -> {name:30s} | {len(rp)} params, {len(views)} views, {len(cons)} cons, {len(warn)} warnings')
        passed += 1
    except Exception as e:
        print(f'  FAIL {ftype:35s} -> {e}')
        failed += 1
print(f'\nResults: {passed}/{len(tests)} passed, {failed} failed')
