"""
DXF Regression Tests — ensure every build maintains entity quality.
A "cleaner" DXF isn't better if it loses semantic entities.
"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ezdxf
from app.backend.dxf_exporter import (save_round_pedestal_table, save_rectangular_table,
                                       save_cabinet, save_sofa, save_coffee_table,
                                       save_dining_chair, save_wardrobe, save_reception_counter)

PASS = 0
FAIL = 0
TOTAL_TESTS = 0


def check(name, condition):
    global PASS, FAIL, TOTAL_TESTS
    TOTAL_TESTS += 1
    if condition:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def analyze_dxf(path):
    doc = ezdxf.readfile(path)
    types = {}
    for e in doc.modelspace():
        et = e.dxftype()
        types[et] = types.get(et, 0) + 1
    return types, doc


def test_round_table():
    """All semantic entities required for shop drawing."""
    t = tempfile.mktemp(suffix='.dxf')
    save_round_pedestal_table(t, 80, 70)
    types, doc = analyze_dxf(t)
    os.unlink(t)

    print(f"\nRound Pedestal Table: {types}")
    check("CIRCLE >= 1", types.get('CIRCLE', 0) >= 1)
    check("DIMENSION >= 2", types.get('DIMENSION', 0) >= 2)
    check("LWPOLYLINE >= 3", types.get('LWPOLYLINE', 0) >= 3)
    check("HATCH >= 1", types.get('HATCH', 0) >= 1)
    check("MTEXT >= 3", types.get('MTEXT', 0) >= 3)
    check("Total entities >= 30", sum(types.values()) >= 30)


def test_rectangular_table():
    t = tempfile.mktemp(suffix='.dxf')
    save_rectangular_table(t, 120, 80, 70)
    types, doc = analyze_dxf(t)
    os.unlink(t)
    print(f"\nRectangular Table: {types}")
    check("LWPOLYLINE >= 2", types.get('LWPOLYLINE', 0) >= 2)
    check("HATCH >= 1", types.get('HATCH', 0) >= 1)
    check("MTEXT >= 2", types.get('MTEXT', 0) >= 2)


def test_cabinet():
    t = tempfile.mktemp(suffix='.dxf')
    save_cabinet(t, 100, 50, 180)
    types, doc = analyze_dxf(t)
    os.unlink(t)
    print(f"\nCabinet: {types}")
    check("LWPOLYLINE >= 1", types.get('LWPOLYLINE', 0) >= 1)
    check("MTEXT >= 1", types.get('MTEXT', 0) >= 1)


def test_sofa():
    t = tempfile.mktemp(suffix='.dxf')
    save_sofa(t, 200, 80, 85, 45)
    types, doc = analyze_dxf(t)
    os.unlink(t)
    print(f"\nSofa: {types}")
    check("LWPOLYLINE >= 1", types.get('LWPOLYLINE', 0) >= 1)
    check("MTEXT >= 1", types.get('MTEXT', 0) >= 1)


def test_all_templates():
    """Ensure ALL 8 templates generate without errors."""
    templates = [
        (save_round_pedestal_table, (80, 70)),
        (save_rectangular_table, (120, 80, 70)),
        (save_cabinet, (100, 50, 180)),
        (save_sofa, (200, 80, 85, 45)),
        (save_coffee_table, (100, 60, 45)),
        (save_dining_chair, (45, 45, 90, 45)),
        (save_wardrobe, (120, 60, 200)),
        (save_reception_counter, (180, 80, 110, 75)),
    ]
    for fn, args in templates:
        t = tempfile.mktemp(suffix='.dxf')
        try:
            fn(t, *args)
            doc = ezdxf.readfile(t)
            check(f"{fn.__name__} generates valid DXF", len(list(doc.modelspace())) > 0)
        except Exception as e:
            check(f"{fn.__name__} no error", False)
            print(f"    ERROR: {e}")
        finally:
            try: os.unlink(t)
            except: pass


if __name__ == '__main__':
    print("=" * 60)
    print("DXF Regression Tests — Entity Quality Check")
    print("=" * 60)
    test_round_table()
    test_rectangular_table()
    test_cabinet()
    test_sofa()
    test_all_templates()
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS}/{TOTAL_TESTS} passed, {FAIL} failed")
    if FAIL == 0:
        print("ALL REGRESSION TESTS PASSED")
    else:
        print(f"{FAIL} regression(s) detected -- quality regression!")
    sys.exit(0 if FAIL == 0 else 1)
