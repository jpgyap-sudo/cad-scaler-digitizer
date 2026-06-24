"""
Professional DXF — uses layer_manager, text_normalizer, extents_updater,
titleblock_generator. No layer 0. LWPOLYLINE for all closed shapes.
Ø symbol proper. No duplicate labels.
"""
import math
from datetime import datetime
import ezdxf
from app.backend.layer_manager import setup_layers, validate_no_layer_0
from app.backend.text_normalizer import normalize_dimension_text, clean_text_for_dxf
from app.backend.extents_updater import setup_a3_sheet
from app.backend.titleblock_generator import generate_title_block
from app.backend.dxf_auditor import audit_dxf


def setup_doc():
    doc = ezdxf.new('R2010')
    setup_layers(doc)
    setup_a3_sheet(doc)
    return doc


def _add_polyline(msp, points, closed=False, layer='OBJECT'):
    if len(points) < 2:
        return
    try:
        msp.add_lwpolyline(points, close=closed, dxfattribs={'layer': layer})
    except Exception as e:
        print(f"[DXF] LWPOLYLINE warn: {e}")
        for i in range(len(points) - 1):
            msp.add_line(points[i], points[i + 1], dxfattribs={'layer': layer})
        if closed and len(points) > 2:
            msp.add_line(points[-1], points[0], dxfattribs={'layer': layer})


def _add_mtext(msp, text, pos, height=3, layer='MTEXT'):
    if not text:
        return
    text = clean_text_for_dxf(text)
    try:
        m = msp.add_mtext(text, dxfattribs={'layer': layer, 'char_height': height})
        m.dxf.insert = pos
    except Exception:
        t = msp.add_text(text, dxfattribs={'height': height, 'layer': layer})
        t.dxf.insert = pos


def _add_text(msp, txt, pt, h=2.5, layer='TEXT'):
    if not txt:
        return
    txt = clean_text_for_dxf(txt)
    e = msp.add_text(txt, dxfattribs={'height': h, 'layer': layer})
    e.dxf.insert = pt


def _add_line(msp, a, b, layer='OBJECT'):
    if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-6:
        return
    msp.add_line(a, b, dxfattribs={'layer': layer})


def _add_centerline(msp, p1, p2):
    _add_line(msp, p1, p2, 'CENTER')


def _add_dimension(msp, p1, p2, loc, text=None):
    try:
        d = msp.add_linear_dim(base=loc, p1=p1, p2=p2, override={'dimtxt': 2.5, 'dimasz': 2.0})
        if text:
            d.dimension.dxf.text = normalize_dimension_text(text)
        d.render()
    except Exception:
        _add_line(msp, p1, p2, 'DIMENSION')
        if text:
            _add_text(msp, normalize_dimension_text(text), loc, 2.5, 'TEXT')


def _add_diameter_dim(msp, center, radius, text=None):
    label = text or f'\u00d8{radius * 2:g} cm'
    _add_dimension(msp, (center[0] - radius, center[1]), (center[0] + radius, center[1]),
                   (center[0], center[1] - radius - 8), label)


def _add_hatch_polygon(msp, vertices, pattern='ANSI31', scale=1.0, angle=0.0):
    if len(vertices) < 3:
        return None
    try:
        h = msp.add_hatch(color=8)
        h.dxf.layer = 'HATCH'
        h.dxf.pattern_name = pattern
        h.dxf.pattern_scale = scale
        h.dxf.pattern_angle = angle
        h.paths.add_polyline_path(vertices, is_closed=True)
        return h
    except Exception as e:
        print(f"[DXF] Hatch warn: {e}")
        return None


def _add_hatch_circle(msp, center, radius, pattern='ANSI31', scale=1.0):
    if radius < 0.1:
        return None
    try:
        h = msp.add_hatch(color=8)
        h.dxf.layer = 'HATCH'
        h.dxf.pattern_name = pattern
        h.dxf.pattern_scale = scale
        pts = [(center[0] + radius * math.cos(2 * math.pi * i / 36),
                center[1] + radius * math.sin(2 * math.pi * i / 36)) for i in range(36)]
        h.paths.add_polyline_path(pts, is_closed=True)
        return h
    except Exception as e:
        print(f"[DXF] Hatch warn: {e}")
        return None


# ========= TEMPLATES =========

def save_generic(path, lines, circles, rects=None):
    import ezdxf
    doc = setup_doc()
    msp = doc.modelspace()
    for c in circles:
        if c[2] > 0.01:
            msp.add_circle((c[0], -c[1] + 220), c[2], dxfattribs={'layer': 'OBJECT'})
    for a, b in lines:
        _add_line(msp, (a[0], -a[1] + 220), (b[0], -b[1] + 220), 'OBJECT')
    generate_title_block(msp, "Generic Tracing")
    result = audit_dxf(doc)
    doc.saveas(path)
    return path


def save_round_pedestal_table(path, top_dia_cm=80, height_cm=70, base_dia_cm=None, neck_dia_cm=None, top_thick_cm=4):
    import ezdxf
    base_dia_cm = base_dia_cm or top_dia_cm * 0.55
    neck_dia_cm = neck_dia_cm or top_dia_cm * 0.28
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    r_px = top_dia_cm / 2 * sc
    y_mid = 180
    cx, cy = 100, y_mid
    # TOP VIEW
    msp.add_circle((cx, cy), r_px, dxfattribs={'layer': 'OBJECT'})
    _add_hatch_circle(msp, (cx, cy), r_px, 'ANSI31', 0.5)
    ext = max(4, r_px * 0.1)
    _add_centerline(msp, (cx - r_px - ext, cy), (cx + r_px + ext, cy))
    _add_centerline(msp, (cx, cy - r_px - ext), (cx, cy + r_px + ext))
    _add_diameter_dim(msp, (cx, cy), r_px)
    _add_mtext(msp, 'TOP VIEW', (cx - 15, cy + r_px + ext + 5), 3)
    # FRONT VIEW
    fx = 280
    h_px = height_cm * sc
    thick_px = top_thick_cm * sc
    nr_px = neck_dia_cm * 0.5 * sc
    br_px = base_dia_cm * 0.5 * sc
    top_y = y_mid + h_px / 2
    bot_y = y_mid - h_px / 2
    _add_polyline(msp, [(fx - r_px, top_y), (fx + r_px, top_y), (fx + r_px, top_y - thick_px), (fx - r_px, top_y - thick_px)], True)
    _add_hatch_polygon(msp, [(fx - r_px, top_y), (fx + r_px, top_y), (fx + r_px, top_y - thick_px), (fx - r_px, top_y - thick_px)], 'ANSI31', 0.5)
    _add_line(msp, (fx - nr_px, top_y - thick_px), (fx - nr_px, bot_y + br_px), 'OBJECT')
    _add_line(msp, (fx + nr_px, top_y - thick_px), (fx + nr_px, bot_y + br_px), 'OBJECT')
    _add_hatch_polygon(msp, [(fx - nr_px, top_y - thick_px), (fx + nr_px, top_y - thick_px), (fx + nr_px, bot_y + br_px), (fx - nr_px, bot_y + br_px)], 'ANSI37', 0.3)
    _add_polyline(msp, [(fx - br_px, bot_y), (fx + br_px, bot_y), (fx + br_px, bot_y + br_px), (fx - br_px, bot_y + br_px)], True)
    _add_dimension(msp, (fx - br_px, bot_y - 5), (fx + br_px, bot_y - 5), (fx, bot_y - 12), f'{base_dia_cm:g} cm')
    _add_centerline(msp, (fx, bot_y - 5), (fx, top_y + 5))
    _add_dimension(msp, (fx + r_px + 10, bot_y), (fx + r_px + 10, top_y), (fx + r_px + 20, (bot_y + top_y) / 2), f'{height_cm:g} cm H')
    _add_mtext(msp, 'FRONT VIEW', (fx - r_px, top_y + 10), 3)
    generate_title_block(msp, f"Round Pedestal Table \u00d8{top_dia_cm:.0f} x H{height_cm:.0f}")
    result = audit_dxf(doc)
    doc.saveas(path)
    return path


def save_rectangular_table(path, width_cm=120, depth_cm=80, height_cm=70):
    import ezdxf
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.4
    w, d, h = width_cm * sc, depth_cm * sc, height_cm * sc
    w2, d2 = w / 2, d / 2
    ox, y_mid = 100, 180
    _add_polyline(msp, [(ox - w2, y_mid - d2), (ox + w2, y_mid - d2), (ox + w2, y_mid + d2), (ox - w2, y_mid + d2)], True)
    _add_centerline(msp, (ox - w2 - 5, y_mid), (ox + w2 + 5, y_mid))
    _add_mtext(msp, 'TOP VIEW', (ox - 15, y_mid + d2 + 8), 3)
    fx = 280
    _add_polyline(msp, [(fx - w2, h), (fx + w2, h), (fx + w2, h - 3), (fx - w2, h - 3)], True)
    _add_hatch_polygon(msp, [(fx - w2, h), (fx + w2, h), (fx + w2, h - 3), (fx - w2, h - 3)], 'ANSI31', 0.5)
    _add_mtext(msp, 'FRONT VIEW', (fx - w2, h + 10), 3)
    generate_title_block(msp, f"Rectangular Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_cabinet(path, width_cm=100, depth_cm=50, height_cm=180):
    import ezdxf
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.3
    w, h = width_cm * sc, height_cm * sc
    fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_centerline(msp, (fx + w / 2, 50), (fx + w / 2, 50 + h))
    for i in range(1, 4):
        _add_line(msp, (fx, 50 + h * i / 4), (fx + w, 50 + h * i / 4), 'HIDDEN')
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3)
    generate_title_block(msp, f"Cabinet {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_sofa(path, width_cm=200, depth_cm=80, height_cm=85, seat_height_cm=45):
    import ezdxf
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.3
    w, h = width_cm * sc, height_cm * sc
    sh = seat_height_cm * sc
    fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_line(msp, (fx, 50 + sh), (fx + w, 50 + sh), 'HIDDEN')
    arm_w = w * 0.08
    _add_line(msp, (fx, 50 + sh), (fx + arm_w, 50 + sh), 'OBJECT')
    _add_line(msp, (fx + arm_w, 50 + sh), (fx + arm_w, 50), 'OBJECT')
    _add_line(msp, (fx + w - arm_w, 50 + sh), (fx + w, 50 + sh), 'OBJECT')
    _add_line(msp, (fx + w - arm_w, 50 + sh), (fx + w - arm_w, 50), 'OBJECT')
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3)
    generate_title_block(msp, f"Sofa {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_coffee_table(path, width_cm=100, depth_cm=60, height_cm=45):
    import ezdxf
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.6
    r = min(width_cm, depth_cm) / 2 * sc
    cx, y_mid = 100, 190
    msp.add_circle((cx, y_mid), r, dxfattribs={'layer': 'OBJECT'})
    _add_centerline(msp, (cx - r - 5, y_mid), (cx + r + 5, y_mid))
    _add_centerline(msp, (cx, y_mid - r - 5), (cx, y_mid + r + 5))
    _add_diameter_dim(msp, (cx, y_mid), r)
    _add_mtext(msp, 'TOP VIEW', (cx - 10, y_mid + r + 10), 3)
    generate_title_block(msp, f"Coffee Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_dining_chair(path, width_cm=45, depth_cm=45, height_cm=90, seat_height_cm=45):
    import ezdxf
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    w, sh = width_cm * sc, seat_height_cm * sc
    bh = (height_cm - seat_height_cm) * sc
    fx = (420 - w) / 2
    _add_polyline(msp, [(fx, sh), (fx + w, sh), (fx + w, sh + bh), (fx, sh + bh)], True)
    _add_line(msp, (fx - 5, sh + bh * 0.1), (fx + w + 5, sh + bh * 0.1), 'HIDDEN')
    _add_mtext(msp, 'SIDE VIEW', (fx, sh + bh + 10), 3)
    generate_title_block(msp, f"Dining Chair {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_wardrobe(path, width_cm=120, depth_cm=60, height_cm=200):
    import ezdxf
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.25
    w, h = width_cm * sc, height_cm * sc
    fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_centerline(msp, (fx + w / 2, 50), (fx + w / 2, 50 + h))
    for i in range(1, 5):
        _add_line(msp, (fx, 50 + h * i / 5), (fx + w, 50 + h * i / 5), 'HIDDEN')
    _add_line(msp, (fx + 5, 50 + h * 0.8), (fx + w - 5, 50 + h * 0.8), 'HIDDEN')
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3)
    generate_title_block(msp, f"Wardrobe {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_reception_counter(path, width_cm=180, depth_cm=80, height_cm=110, counter_height_cm=75):
    import ezdxf
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.25
    w, d, h = width_cm * sc, depth_cm * sc, height_cm * sc
    ch = counter_height_cm * sc
    fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 190), (fx + w, 190), (fx + w, 190 + d * 0.5), (fx, 190 + d * 0.5)], True)
    _add_mtext(msp, 'TOP VIEW', (fx, 190 + d * 0.5 + 10), 3)
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_line(msp, (fx, 50 + ch), (fx + w, 50 + ch), 'HIDDEN')
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3)
    generate_title_block(msp, f"Reception Counter {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path
