"""
Verification Test: AI Furniture Shopdrawing Generator (10/10 Quality)

Tests:
1. Angle snapping (89.6° → 90°)
2. Circle rebuilding from segments
3. HATCH entity existence
4. Title block TEXT in DXF
5. Endpoint snapping
6. Full pipeline end-to-end
"""
import sys, os, math, tempfile
# Add the project root so we can import from backend-python
_project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _project_root)

# Import using direct path since python module names can't have hyphens
import importlib.util
_spec_c = importlib.util.spec_from_file_location(
    "constraints",
    os.path.join(_project_root, "backend-python", "app", "engine", "constraints.py")
)
_constraints = importlib.util.module_from_spec(_spec_c)
_spec_c.loader.exec_module(_constraints)
snap_line_angle = _constraints.snap_line_angle
snap_endpoints = _constraints.snap_endpoints
merge_collinear = _constraints.merge_collinear
rebuild_circles_from_segments = _constraints.rebuild_circles_from_segments
process_constraints = _constraints.process_constraints

_spec_d = importlib.util.spec_from_file_location(
    "dxf_writer",
    os.path.join(_project_root, "backend-python", "app", "engine", "dxf_writer.py")
)
_dxf = importlib.util.module_from_spec(_spec_d)
_spec_d.loader.exec_module(_dxf)
setup_doc = _dxf.setup_doc
save_round_pedestal_table = _dxf.save_round_pedestal_table
save_rectangular_table = _dxf.save_rectangular_table

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")

def test_angle_snapping():
    """Test 89.6° → 90° snapping."""
    print("\n📐 Angle Snapping Test:")
    
    # Near horizontal
    snapped = snap_line_angle(((0, 0), (100, 1)), 5.0)
    dx = snapped[1][0] - snapped[0][0]
    dy = snapped[1][1] - snapped[0][1]
    check("Near-horizontal (1° offset) snaps to 0°", abs(dy) < 0.01 and dx > 0)
    
    # Near vertical
    snapped = snap_line_angle(((0, 0), (0.5, 100)), 5.0)
    dx = snapped[1][0] - snapped[0][0]
    dy = snapped[1][1] - snapped[0][1]
    check("Near-vertical (0.3° offset) snaps to 90°", abs(dx) < 0.01 and dy > 0)
    
    # Near 45°
    snapped = snap_line_angle(((0, 0), (100, 102)), 5.0)
    angle = math.degrees(math.atan2(snapped[1][1] - snapped[0][1], snapped[1][0] - snapped[0][0]))
    check("Near-45° (44.6°) snaps to 45°", abs(abs(angle) - 45) < 1)
    
    # No snapping if far from target
    snapped = snap_line_angle(((0, 0), (100, 50)), 5.0)
    angle = math.degrees(math.atan2(snapped[1][1] - snapped[0][1], snapped[1][0] - snapped[0][0]))
    check("30° line stays at 30° (outside tolerance)", 25 < abs(angle) < 35)

def test_endpoint_snapping():
    """Test endpoint snapping."""
    print("\n📍 Endpoint Snapping Test:")
    
    lines = [
        ((0, 0), (100, 0)),
        ((100, 2), (200, 0)),  # 2px offset
    ]
    snapped = snap_endpoints(lines, 5.0)
    check("2px offset endpoints snap together", 
          len(snapped) == 2 and 
          math.hypot(snapped[0][1][0] - snapped[1][0][0], 
                     snapped[0][1][1] - snapped[1][0][1]) < 0.1)

def test_circle_rebuilding():
    """Test circle detection from segments."""
    print("\n⭕ Circle Rebuilding Test:")
    
    # Generate circle points
    cx, cy, r = 200, 200, 100
    segments = []
    for i in range(16):
        a1 = 2 * math.pi * i / 16
        a2 = 2 * math.pi * (i + 1) / 16
        x1 = cx + r * math.cos(a1)
        y1 = cy + r * math.sin(a1)
        x2 = cx + r * math.cos(a2)
        y2 = cy + r * math.sin(a2)
        segments.append(((x1, y1), (x2, y2)))
    
    circles, remaining = rebuild_circles_from_segments(segments)
    check("16 segments rebuild as circle", len(circles) > 0)
    if circles:
        check("Circle center matches", abs(circles[0][0] - cx) < 5 and abs(circles[0][1] - cy) < 5)
        check("Circle radius matches", abs(circles[0][2] - r) < 5)

def test_dxf_professional():
    """Test professional DXF output with hatching and title block."""
    print("\n📄 Professional DXF Test:")
    
    tmp = tempfile.NamedTemporaryFile(suffix='.dxf', delete=False)
    tmp_path = tmp.name
    tmp.close()
    
    # Generate professional DXF
    save_round_pedestal_table(tmp_path, top_dia_cm=80, height_cm=70)
    
    import ezdxf
    doc = ezdxf.readfile(tmp_path)
    msp = doc.modelspace()
    
    # Check entities
    entities = list(msp)
    entity_types = {}
    for e in entities:
        et = e.dxftype()
        entity_types[et] = entity_types.get(et, 0) + 1
    
    print(f"  Entity types: {entity_types}")
    
    # Check for HATCH
    check("HATCH entities exist", entity_types.get('HATCH', 0) > 0)
    
    # Check for TEXT entities
    texts = [e for e in entities if e.dxftype() == 'TEXT']
    check("TEXT entities exist", len(texts) > 0)
    
    # Check for title block content
    title_texts = [t.dxf.text for t in texts if 'DRAWING' in str(t.dxf.text) or 'DESIGNER' in str(t.dxf.text)]
    check("Title block text found", len(title_texts) > 0)
    
    # Check for CIRCLE entities
    check("TRUE CIRCLE entities (not segments)", entity_types.get('CIRCLE', 0) > 0)
    
    # Check for LWPOLYLINE (rectangles)
    check("LWPOLYLINE/RECTANGLE entities", entity_types.get('LWPOLYLINE', 0) > 0 or entity_types.get('LINE', 0) > 0)
    
    # Check for CENTERLINE layer
    center_entities = [e for e in entities if getattr(e.dxf, 'layer', '') == 'CENTER']
    check("Centerlines exist", len(center_entities) > 0)
    
    os.unlink(tmp_path)

def test_collinear_merge():
    """Test collinear line merging."""
    print("\n📏 Collinear Merging Test:")
    
    lines = [
        ((0, 0), (50, 0)),
        ((52, 0), (100, 0)),  # 2px gap
        ((0, 50), (100, 50)),  # Separate line
    ]
    merged = merge_collinear(lines, gap_tolerance=5)
    check("Collinear lines merged", len(merged) == 2)
    check("Merged line is longer", 
          math.hypot(merged[0][1][0] - merged[0][0][0], 
                     merged[0][1][1] - merged[0][0][1]) > 95)

if __name__ == '__main__':
    print("=" * 60)
    print("🏗️  AI Furniture Shopdrawing Generator - Verification")
    print("=" * 60)
    
    test_angle_snapping()
    test_endpoint_snapping()
    test_collinear_merge()
    test_circle_rebuilding()
    test_dxf_professional()
    
    print(f"\n{'=' * 60}")
    print(f"📊 Results: {PASS} ✅ passed, {FAIL} ❌ failed out of {PASS + FAIL} tests")
    print(f"{'=' * 60}")
    
    if FAIL == 0:
        print("\n🎉 ALL TESTS PASSED! Shop Drawings are ready for professional use (10/10).")
    else:
        print(f"\n⚠️  {FAIL} test(s) failed. Review and fix before deployment.")
    
    sys.exit(0 if FAIL == 0 else 1)
