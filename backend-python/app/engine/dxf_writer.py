"""
CAD Agent: Generate clean DXF files with proper CAD entities.
Uses ezdxf for R2010 format output with layers: OBJECT, DIMENSION, CENTER, TEXT.
"""
import ezdxf
import math
from pathlib import Path
from typing import List, Tuple, Optional


def setup_doc():
    """Create DXF document with standard layers."""
    doc = ezdxf.new('R2010')
    for name in ['OBJECT', 'DIMENSION', 'CENTER', 'TEXT', 'CONSTRUCTION', 'HIDDEN']:
        if name not in doc.layers:
            doc.layers.new(name=name)
    # Set layer colors
    doc.layers.get('OBJECT').color = 7  # White
    doc.layers.get('DIMENSION').color = 3  # Green
    doc.layers.get('CENTER').color = 5  # Blue
    doc.layers.get('TEXT').color = 2  # Yellow
    doc.layers.get('CONSTRUCTION').color = 8  # Grey
    doc.layers.get('HIDDEN').color = 251  # Dark grey
    return doc


def add_line(msp, a, b, layer='OBJECT'):
    """Add a line entity with minimum length validation."""
    if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-6:
        return
    msp.add_line(a, b, dxfattribs={'layer': layer})


def add_circle(msp, center, radius, layer='OBJECT'):
    """Add a circle entity."""
    if radius < 0.01:
        return
    msp.add_circle(center, radius, dxfattribs={'layer': layer})


def add_text(msp, txt, pt, h=2.5, layer='TEXT'):
    """Add a text entity."""
    e = msp.add_text(txt, dxfattribs={'height': h, 'layer': layer})
    e.dxf.insert = pt


def add_linear_dim(msp, p1, p2, loc, text=None):
    """Add a linear dimension entity with fallback to manual lines."""
    try:
        dim = msp.add_linear_dim(base=loc, p1=p1, p2=p2,
                                 override={'dimtxt': 2.5, 'dimasz': 2.0})
        if text:
            dim.dimension.dxf.text = text
        dim.render()
    except Exception:
        # Fallback: manual dimension lines
        add_line(msp, p1, p2, 'DIMENSION')
        if text:
            add_text(msp, text, loc, 2.5, 'TEXT')


def add_diameter_dim(msp, center, radius, text=None):
    """Add a diameter dimension."""
    p1 = (center[0] - radius, center[1])
    p2 = (center[0] + radius, center[1])
    label = text or f'Ø{radius * 2:g}'
    add_linear_dim(msp, p1, p2, (center[0], center[1] - radius - 8), label)


def save_generic(
    path: str,
    lines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    circles: List[Tuple[float, float, float]],
    rects: List[Tuple[float, float, float, float]] = None,
    scale: float = 1.0
):
    """Save generic CAD primitives to DXF with proper scaling."""
    doc = setup_doc()
    msp = doc.modelspace()

    # Circles
    for c in circles:
        x, y, r = c
        add_circle(msp, (x * scale, -y * scale), r * scale, 'OBJECT')

    # Lines
    for a, b in lines:
        add_line(msp,
                 (a[0] * scale, -a[1] * scale),
                 (b[0] * scale, -b[1] * scale),
                 'OBJECT')

    # Rectangles
    if rects:
        for x1, y1, x2, y2 in rects:
            pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
            for i in range(len(pts) - 1):
                add_line(msp,
                         (pts[i][0] * scale, -pts[i][1] * scale),
                         (pts[i + 1][0] * scale, -pts[i + 1][1] * scale),
                         'OBJECT')

    doc.saveas(path)
    return path


def save_round_pedestal_table(
    path: str,
    top_dia_cm: float = 80.0,
    height_cm: float = 70.0,
    base_dia_cm: Optional[float] = None,
    neck_dia_cm: Optional[float] = None,
    top_thick_cm: float = 4.0
):
    """
    Generate parametric round pedestal table DXF.
    Left side: TOP VIEW (circle with centerlines + diameter dimension).
    Right side: FRONT VIEW (tabletop rectangle + pedestal neck + base + height dimension).
    """
    base_dia_cm = base_dia_cm or top_dia_cm * 0.55
    neck_dia_cm = neck_dia_cm or top_dia_cm * 0.28

    doc = setup_doc()
    msp = doc.modelspace()

    # === TOP VIEW (left side) ===
    cx, cy = 0, 0
    r = top_dia_cm / 2

    # Table top circle
    add_circle(msp, (cx, cy), r, 'OBJECT')

    # Centerlines
    add_line(msp, (-r - 15, 0), (r + 15, 0), 'CENTER')
    add_line(msp, (0, -r - 15), (0, r + 15), 'CENTER')

    # Diameter dimension
    add_diameter_dim(msp, (cx, cy), r, f'Ø{top_dia_cm:g} cm')

    # Label
    add_text(msp, 'TOP VIEW', (-r, r + 15), 3, 'TEXT')

    # === FRONT VIEW (right side, offset by 1.5x top_dia) ===
    ox = top_dia_cm * 1.5
    bottom = 0
    top = height_cm
    top_thick = top_thick_cm

    # Tabletop rectangle
    add_line(msp, (ox - r, top), (ox + r, top), 'OBJECT')
    add_line(msp, (ox - r, top - top_thick), (ox + r, top - top_thick), 'OBJECT')
    add_line(msp, (ox - r, top), (ox - r, top - top_thick), 'OBJECT')
    add_line(msp, (ox + r, top), (ox + r, top - top_thick), 'OBJECT')

    # Pedestal neck
    nr = neck_dia_cm / 2
    add_line(msp, (ox - nr, top - top_thick), (ox - nr, bottom + 12), 'OBJECT')
    add_line(msp, (ox + nr, top - top_thick), (ox + nr, bottom + 12), 'OBJECT')

    # Pedestal base
    br = base_dia_cm / 2
    add_line(msp, (ox - br, bottom + 12), (ox + br, bottom + 12), 'OBJECT')
    add_line(msp, (ox - br, bottom), (ox + br, bottom), 'OBJECT')
    add_line(msp, (ox - br, bottom), (ox - br, bottom + 12), 'OBJECT')
    add_line(msp, (ox + br, bottom), (ox + br, bottom + 12), 'OBJECT')

    # Symmetry centerline for front view
    add_line(msp, (ox, bottom), (ox, top + 10), 'CENTER')

    # Height dimension
    add_linear_dim(msp,
                   (ox + r + 15, bottom),
                   (ox + r + 15, top),
                   (ox + r + 25, height_cm / 2),
                   f'{height_cm:g} cm H')

    # Label
    add_text(msp, 'FRONT VIEW', (ox - r, top + 15), 3, 'TEXT')

    doc.saveas(path)
    return path


def save_rectangular_table(
    path: str,
    width_cm: float = 120.0,
    depth_cm: float = 80.0,
    height_cm: float = 70.0,
    leg_width_cm: float = 5.0
):
    """Generate parametric rectangular table DXF."""
    doc = setup_doc()
    msp = doc.modelspace()
    w2, d2 = width_cm / 2, depth_cm / 2

    # TOP VIEW
    pts = [(-w2, -d2), (w2, -d2), (w2, d2), (-w2, d2), (-w2, -d2)]
    for i in range(4):
        add_line(msp, pts[i], pts[i + 1], 'OBJECT')
    # Centerlines
    add_line(msp, (-w2 - 10, 0), (w2 + 10, 0), 'CENTER')
    add_line(msp, (0, -d2 - 10), (0, d2 + 10), 'CENTER')
    add_text(msp, 'TOP VIEW', (-w2, d2 + 15), 3, 'TEXT')

    # Width dimension
    add_linear_dim(msp, (-w2, -d2 - 10), (w2, -d2 - 10), (0, -d2 - 20), f'{width_cm:g} cm')

    # FRONT VIEW (right side)
    ox = width_cm + 40
    add_line(msp, (ox - w2, height_cm), (ox + w2, height_cm), 'OBJECT')
    add_line(msp, (ox - w2, height_cm - 3), (ox + w2, height_cm - 3), 'OBJECT')
    add_line(msp, (ox - w2, height_cm), (ox - w2, height_cm - 3), 'OBJECT')
    add_line(msp, (ox + w2, height_cm), (ox + w2, height_cm - 3), 'OBJECT')
    # Legs
    lw = leg_width_cm / 2
    add_line(msp, (ox - w2 + lw, height_cm - 3), (ox - w2 + lw, 0), 'OBJECT')
    add_line(msp, (ox - w2, height_cm - 3), (ox - w2, 0), 'OBJECT')
    add_line(msp, (ox + w2 - lw, height_cm - 3), (ox + w2 - lw, 0), 'OBJECT')
    add_line(msp, (ox + w2, height_cm - 3), (ox + w2, 0), 'OBJECT')
    add_text(msp, 'FRONT VIEW', (ox - w2, height_cm + 15), 3, 'TEXT')

    doc.saveas(path)
    return path


def save_cabinet(
    path: str,
    width_cm: float = 100.0,
    depth_cm: float = 50.0,
    height_cm: float = 180.0
):
    """Generate parametric cabinet DXF."""
    doc = setup_doc()
    msp = doc.modelspace()

    # FRONT VIEW
    add_line(msp, (0, 0), (width_cm, 0), 'OBJECT')
    add_line(msp, (width_cm, 0), (width_cm, height_cm), 'OBJECT')
    add_line(msp, (width_cm, height_cm), (0, height_cm), 'OBJECT')
    add_line(msp, (0, height_cm), (0, 0), 'OBJECT')
    # Door centerline
    add_line(msp, (width_cm / 2, 0), (width_cm / 2, height_cm), 'CENTER')
    # Shelves (optional, 3 shelves)
    shelf_h = height_cm / 4
    for i in range(1, 4):
        add_line(msp, (0, shelf_h * i), (width_cm, shelf_h * i), 'HIDDEN')
    add_text(msp, 'FRONT VIEW', (0, height_cm + 10), 3, 'TEXT')
    # Dimensions
    add_linear_dim(msp, (0, -10), (width_cm, -10), (width_cm / 2, -20), f'{width_cm:g} cm')
    add_linear_dim(msp, (-15, 0), (-15, height_cm), (-25, height_cm / 2), f'{height_cm:g} cm H')

    doc.saveas(path)
    return path


def save_sofa(
    path: str,
    width_cm: float = 200.0,
    depth_cm: float = 80.0,
    height_cm: float = 85.0,
    seat_height_cm: float = 45.0
):
    """Generate parametric sofa DXF."""
    doc = setup_doc()
    msp = doc.modelspace()
    w2 = width_cm / 2

    # FRONT VIEW
    add_line(msp, (-w2, 0), (w2, 0), 'OBJECT')
    add_line(msp, (w2, 0), (w2, height_cm), 'OBJECT')
    add_line(msp, (w2, height_cm), (-w2, height_cm), 'OBJECT')
    add_line(msp, (-w2, height_cm), (-w2, 0), 'OBJECT')
    # Seat line
    add_line(msp, (-w2, seat_height_cm), (w2, seat_height_cm), 'HIDDEN')
    # Armrests (small rectangles on sides)
    arm_w = width_cm * 0.08
    add_line(msp, (-w2, seat_height_cm), (-w2 + arm_w, seat_height_cm), 'OBJECT')
    add_line(msp, (-w2 + arm_w, seat_height_cm), (-w2 + arm_w, 0), 'OBJECT')
    add_line(msp, (w2 - arm_w, seat_height_cm), (w2, seat_height_cm), 'OBJECT')
    add_line(msp, (w2 - arm_w, seat_height_cm), (w2 - arm_w, 0), 'OBJECT')
    add_text(msp, 'FRONT VIEW', (-w2, height_cm + 10), 3, 'TEXT')

    doc.saveas(path)
    return path
