"""Run all engine tests to verify correctness."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend-python'))

PASS, FAIL = 0, 0
def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f'  OK: {name}')
    else: FAIL += 1; print(f'  FAIL: {name}')

print('=== DXF WRITER ===')
from app.engine.dxf_writer import save_round_pedestal_table, save_rectangular_table, save_cabinet, save_sofa, save_generic

for name, fn in [
    ('round_pedestal_table', lambda t: save_round_pedestal_table(t, 80, 70)),
    ('rectangular_table', lambda t: save_rectangular_table(t, 120, 80, 70)),
    ('cabinet', lambda t: save_cabinet(t, 100, 50, 180)),
    ('sofa', lambda t: save_sofa(t, 200, 80, 85, 45)),
    ('generic', lambda t: save_generic(t, [((0,0),(100,0))], [(50,50,30)])),
]:
    t = tempfile.NamedTemporaryFile(suffix='.dxf', delete=False).name
    try:
        fn(t)
        check(f'{name} generates DXF', os.path.getsize(t.name) > 100)
    except Exception as e:
        check(f'{name} no error', False)
        print(f'    ERROR: {e}')
    finally:
        try: os.unlink(t)
        except: pass

print()
print('=== CONSTRAINTS ===')
from app.engine.constraints import clean_geometry, align_dimension_to_ocr, extract_table_proportions, snap_line_angle, snap_endpoints
import math

lines = clean_geometry([((0,0),(100,2)), ((100,98),(200,100))])
check('clean_geometry returns lines', len(lines) > 0)

val = align_dimension_to_ocr(79.2, [{'tag':'diameter','value_cm':80.0,'raw':'80 cm'}], ['dia','diameter'])
check('align_dim snaps 79.2 -> 80.0', val == 80.0)

val2 = align_dimension_to_ocr(50.0, [{'tag':'diameter','value_cm':80.0,'raw':'80 cm'}], ['dia','diameter'])
check('align_dim keeps 50.0 when diff > 15%', val2 == 50.0)

ratios = extract_table_proportions([], [(50,50,30)], [])
check('extract_proportions has base_height_ratio', 'base_height_ratio' in ratios)
check('extract_proportions base_height_ratio=0.15', abs(ratios['base_height_ratio'] - 0.15) < 0.001)

s = snap_line_angle(((0,0),(100,1)), 5)
dy = s[1][1] - s[0][1]
check('angle snap: near-horiz -> horizontal', abs(dy) < 0.01)

snapped = snap_endpoints([((0,0),(100,0)), ((100,2),(200,0))], 5)
d = math.hypot(snapped[0][1][0]-snapped[1][0][0], snapped[0][1][1]-snapped[1][0][1])
check('endpoint snap: 2px offset -> coincident', d < 0.1)

print()
print('=== HYBRID ===')
from app.engine.hybrid import process_hybrid
# Can't fully test hybrid without OpenAI, but verify import works
check('hybrid.process_hybrid importable', callable(process_hybrid))

print()
print(f'RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} tests')
print('PASS' if FAIL == 0 else 'SOME FAILURES')
