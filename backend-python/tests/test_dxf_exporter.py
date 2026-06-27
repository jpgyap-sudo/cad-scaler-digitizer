"""Test DXF exporter produces valid entities."""
from pathlib import Path
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.backend.dxf_exporter import save_round_pedestal_table, save_rectangular_table, save_cabinet, save_sofa, save_generic, save_asymmetric_pedestal_table
import ezdxf
import tempfile


def test_round_table_dxf_valid():
    out = Path(tempfile.mktemp(suffix='.dxf'))
    save_round_pedestal_table(out, 80, 70)
    doc = ezdxf.readfile(out)
    types = [e.dxftype() for e in doc.modelspace()]
    assert 'CIRCLE' in types, f"No CIRCLE in {types}"
    assert 'LINE' in types or 'LWPOLYLINE' in types, f"No geometry in {types}"
    assert 'HATCH' in types, f"No HATCH in {types}"
    mtexts = [e.dxf.text for e in doc.modelspace() if e.dxftype() == 'MTEXT']
    assert any('Pedestal' in str(t) or 'DRAWING' in str(t).upper() for t in mtexts), f"No title text in MTEXT: {mtexts}"
    os.unlink(out)


def test_rectangular_table_dxf():
    out = Path(tempfile.mktemp(suffix='.dxf'))
    save_rectangular_table(out, 120, 80, 70)
    doc = ezdxf.readfile(out)
    types = [e.dxftype() for e in doc.modelspace()]
    assert 'LINE' in types, f"No LINE in {types}"
    os.unlink(out)


def test_cabinet_dxf():
    out = Path(tempfile.mktemp(suffix='.dxf'))
    save_cabinet(out, 100, 50, 180)
    doc = ezdxf.readfile(out)
    types = [e.dxftype() for e in doc.modelspace()]
    assert len(types) > 3, f"Too few entities: {types}"
    os.unlink(out)


def test_sofa_dxf():
    out = Path(tempfile.mktemp(suffix='.dxf'))
    save_sofa(out, 200, 80, 85, 45)
    doc = ezdxf.readfile(out)
    assert len(list(doc.modelspace())) > 5
    os.unlink(out)


def test_asymmetric_pedestal_table_dxf():
    out = Path(tempfile.mktemp(suffix='.dxf'))
    save_asymmetric_pedestal_table(out, length_cm=180, depth_cm=90, height_cm=75,
                                    large_ped_dia_cm=40, small_ped_dia_cm=22,
                                    left_ped_x_cm=30, right_ped_x_cm=-25)
    doc = ezdxf.readfile(out)
    types = [e.dxftype() for e in doc.modelspace()]
    assert 'CIRCLE' in types, f"No CIRCLE in {types}"
    assert 'LWPOLYLINE' in types, f"No LWPOLYLINE in {types}"
    assert 'LINE' in types, f"No LINE in {types}"
    mtexts = [str(e.dxf.text) for e in doc.modelspace() if e.dxftype() == 'MTEXT']
    view_labels = [t for t in mtexts if 'VIEW' in t or 'ELEVATION' in t]
    assert any('TOP' in t for t in view_labels), f"No TOP VIEW label in {mtexts}"
    assert any('FRONT' in t for t in view_labels), f"No FRONT ELEVATION label in {mtexts}"
    assert any('SIDE' in t for t in view_labels), f"No SIDE ELEVATION label in {mtexts}"
    os.unlink(out)


def test_generic_dxf():
    out = Path(tempfile.mktemp(suffix='.dxf'))
    save_generic(out, [((0,0),(100,0))], [(50,50,30)])
    doc = ezdxf.readfile(out)
    types = [e.dxftype() for e in doc.modelspace()]
    assert 'CIRCLE' in types
    assert 'LINE' in types
    os.unlink(out)


if __name__ == '__main__':
    test_round_table_dxf_valid()
    test_rectangular_table_dxf()
    test_cabinet_dxf()
    test_sofa_dxf()
    test_asymmetric_pedestal_table_dxf()
    test_generic_dxf()
    print("All 6 tests passed!")
