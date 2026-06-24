"""
Professional DXF — LWPOLYLINE everywhere, MTEXT for notes, proper layers.
NO layer 0 entities. NO raw LINE for closed shapes.
"""
import ezdxf
import math
from datetime import datetime


def setup_doc():
    doc = ezdxf.new('R2010')
    doc.layers.add('OBJECT', color=7)
    doc.layers.add('DIMENSION', color=3)
    doc.layers.add('CENTER', color=5, linetype='CENTER2')
    doc.layers.add('TEXT', color=2)
    doc.layers.add('MTEXT', color=2)
    doc.layers.add('HATCH', color=8)
    doc.layers.add('HIDDEN', color=251, linetype='HIDDEN')
    doc.layers.add('TITLE', color=6)
    doc.layers.add('BORDER', color=7)
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
    """Add MTEXT entity for professional notes."""
    if not text:
        return
    try:
        mtext = msp.add_mtext(text, dxfattribs={'layer': layer, 'char_height': height})
        mtext.dxf.insert = pos
        mtext.dxf.text_height = height
        return mtext
    except Exception:
        # Fallback to TEXT
        t = msp.add_text(text, dxfattribs={'height': height, 'layer': layer})
        t.dxf.insert = pos


def _add_text(msp, txt, pt, h=2.5, layer='TEXT'):
    if not txt:
        return
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
            d.dimension.dxf.text = text
        d.render()
    except Exception:
        _add_line(msp, p1, p2, 'DIMENSION')
        if text:
            _add_text(msp, text, loc, 2.5, 'TEXT')


def _add_diameter_dim(msp, center, radius, text=None):
    _add_dimension(msp, (center[0] - radius, center[1]), (center[0] + radius, center[1]),
                   (center[0], center[1] - radius - 8), text or f'O{radius * 2:g}')


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


def _draw_title_block(msp, title="Furniture Drawing", w=420, h=297):
    tb_w, tb_h = 180, 50
    ox, oy = w - tb_w - 10, 10
    _add_polyline(msp, [(0, 0), (w, 0), (w, h), (0, h)], True, 'BORDER')
    _add_polyline(msp, [(ox, oy), (ox + tb_w, oy), (ox + tb_w, oy + tb_h), (ox, oy + tb_h)], True, 'TITLE')
    _add_line(msp, (ox, oy + tb_h - 15), (ox + tb_w, oy + tb_h - 15), 'TITLE')
    _add_line(msp, (ox, oy + tb_h - 30), (ox + tb_w, oy + tb_h - 30), 'TITLE')
    now = datetime.now().strftime('%Y-%m-%d')
    _add_mtext(msp, f'DRAWING: {title}', (ox + 5, oy + 2), 3, 'TITLE')
    _add_mtext(msp, f'SCALE: cm    DATE: {now}', (ox + 5, oy + 17), 3, 'TITLE')
    _add_mtext(msp, 'DESIGNER: AI CAD Drafter', (ox + 5, oy + 32), 3, 'TITLE')


def save_generic(path, lines, circles, rects=None):
    doc = setup_doc()
    msp = doc.modelspace()
    for c in circles:
        if c[2] > 0.01:
            msp.add_circle((c[0], -c[1] + 220), c[2], dxfattribs={'layer': 'OBJECT'})
    for a, b in lines:
        _add_line(msp, (a[0], -a[1] + 220), (b[0], -b[1] + 220), 'OBJECT')
    _draw_title_block(msp, "Generic Tracing")
    doc.saveas(path)
    return path


def save_round_pedestal_table(path, top_dia_cm=80, height_cm=70, base_dia_cm=None, neck_dia_cm=None, top_thick_cm=4):
    base_dia_cm = base_dia_cm or top_dia_cm * 0.55
    neck_dia_cm = neck_dia_cm or top_dia_cm * 0.28
    doc = setup_doc()
    msp = doc.modelspace()
    y_mid = 180
    r_px = top_dia_cm / 2 * 0.5
    cx, cy = 100, y_mid
    # TOP VIEW — CIRCLE
    msp.add_circle((cx, cy), r_px, dxfattribs={'layer': 'OBJECT'})
    _add_hatch_circle(msp, (cx, cy), r_px, 'ANSI31', 0.5)
    ext = max(4, r_px * 0.1)
    _add_centerline(msp, (cx - r_px - ext, cy), (cx + r_px + ext, cy))
    _add_centerline(msp, (cx, cy - r_px - ext), (cx, cy + r_px + ext))
    _add_diameter_dim(msp, (cx, cy), r_px, f'O{top_dia_cm:g} cm')
    _add_mtext(msp, 'TOP VIEW', (cx - 20, cy + r_px + ext + 5), 3, 'MTEXT')
    # FRONT VIEW — all LWPOLYLINE
    fx = 280
    sc = 0.5
    h_px = height_cm * sc
    thick_px = top_thick_cm * sc
    nr_px = neck_dia_cm * 0.5 * sc
    br_px = base_dia_cm * 0.5 * sc
    top_y = y_mid + h_px / 2
    bot_y = y_mid - h_px / 2
    _add_polyline(msp, [(fx - r_px, top_y), (fx + r_px, top_y), (fx + r_px, top_y - thick_px), (fx - r_px, top_y - thick_px)], True)
    _add_hatch_polygon(msp, [(fx - r_px, top_y), (fx + r_px, top_y), (fx + r_px, top_y - thick_px), (fx - r_px, top_y - thick_px)], 'ANSI31', 0.5)
    # Pedestal neck (LINE is OK for thin structural elements)
    _add_line(msp, (fx - nr_px, top_y - thick_px), (fx - nr_px, bot_y + br_px), 'OBJECT')
    _add_line(msp, (fx + nr_px, top_y - thick_px), (fx + nr_px, bot_y + br_px), 'OBJECT')
    _add_hatch_polygon(msp, [(fx - nr_px, top_y - thick_px), (fx + nr_px, top_y - thick_px), (fx + nr_px, bot_y + br_px), (fx - nr_px, bot_y + br_px)], 'ANSI37', 0.3)
    # Base as LWPOLYLINE
    _add_polyline(msp, [(fx - br_px, bot_y), (fx + br_px, bot_y), (fx + br_px, bot_y + br_px), (fx - br_px, bot_y + br_px)], True)
    _add_dimension(msp, (fx - br_px, bot_y - 5), (fx + br_px, bot_y - 5), (fx, bot_y - 12), f'{base_dia_cm:g} cm')
    _add_centerline(msp, (fx, bot_y - 5), (fx, top_y + 5))
    _add_dimension(msp, (fx + r_px + 10, bot_y), (fx + r_px + 10, top_y), (fx + r_px + 20, (bot_y + top_y) / 2), f'{height_cm:g} cm H')
    _add_mtext(msp, 'FRONT VIEW', (fx - r_px, top_y + 10), 3, 'MTEXT')
    _draw_title_block(msp, f"Round Table O{top_dia_cm:.0f}xH{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_rectangular_table(path, width_cm=120, depth_cm=80, height_cm=70):
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.4
    w, d, h = width_cm * sc, depth_cm * sc, height_cm * sc
    w2, d2 = w / 2, d / 2
    ox, y_mid = 100, 180
    # TOP VIEW — LWPOLYLINE
    _add_polyline(msp, [(ox - w2, y_mid - d2), (ox + w2, y_mid - d2), (ox + w2, y_mid + d2), (ox - w2, y_mid + d2)], True)
    _add_centerline(msp, (ox - w2 - 5, y_mid), (ox + w2 + 5, y_mid))
    _add_mtext(msp, 'TOP VIEW', (ox - 20, y_mid + d2 + 8), 3, 'MTEXT')
    # FRONT VIEW — LWPOLYLINE
    fx = 280
    _add_polyline(msp, [(fx - w2, h), (fx + w2, h), (fx + w2, h - 3), (fx - w2, h - 3)], True)
    _add_hatch_polygon(msp, [(fx - w2, h), (fx + w2, h), (fx + w2, h - 3), (fx - w2, h - 3)], 'ANSI31', 0.5)
    _add_mtext(msp, 'FRONT VIEW', (fx - w2, h + 10), 3, 'MTEXT')
    _draw_title_block(msp, f"Rect Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_cabinet(path, width_cm=100, depth_cm=50, height_cm=180):
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.3
    w, h = width_cm * sc, height_cm * sc
    fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_centerline(msp, (fx + w / 2, 50), (fx + w / 2, 50 + h))
    for i in range(1, 4):
        _add_line(msp, (fx, 50 + h * i / 4), (fx + w, 50 + h * i / 4), 'HIDDEN')
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3, 'MTEXT')
    _draw_title_block(msp, f"Cabinet {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_sofa(path, width_cm=200, depth_cm=80, height_cm=85, seat_height_cm=45):
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
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3, 'MTEXT')
    _draw_title_block(msp, f"Sofa {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_coffee_table(path, width_cm=100, depth_cm=60, height_cm=45):
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.6
    r = min(width_cm, depth_cm) / 2 * sc
    cx, y_mid = 100, 190
    msp.add_circle((cx, y_mid), r, dxfattribs={'layer': 'OBJECT'})
    _add_centerline(msp, (cx - r - 5, y_mid), (cx + r + 5, y_mid))
    _add_centerline(msp, (cx, y_mid - r - 5), (cx, y_mid + r + 5))
    _add_diameter_dim(msp, (cx, y_mid), r, f'O{min(width_cm, depth_cm):g} cm')
    _add_mtext(msp, 'TOP VIEW', (cx - 10, y_mid + r + 10), 3, 'MTEXT')
    _draw_title_block(msp, f"Coffee Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_dining_chair(path, width_cm=45, depth_cm=45, height_cm=90, seat_height_cm=45):
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    w, sh = width_cm * sc, seat_height_cm * sc
    bh = (height_cm - seat_height_cm) * sc
    fx = (420 - w) / 2
    _add_polyline(msp, [(fx, sh), (fx + w, sh), (fx + w, sh + bh), (fx, sh + bh)], True)
    _add_line(msp, (fx - 5, sh + bh * 0.1), (fx + w + 5, sh + bh * 0.1), 'HIDDEN')
    _add_mtext(msp, 'SIDE VIEW (Chair)', (fx, sh + bh + 10), 3, 'MTEXT')
    _draw_title_block(msp, f"Dining Chair {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_wardrobe(path, width_cm=120, depth_cm=60, height_cm=200):
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
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3, 'MTEXT')
    _draw_title_block(msp, f"Wardrobe {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path


def save_reception_counter(path, width_cm=180, depth_cm=80, height_cm=110, counter_height_cm=75):
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.25
    w, d, h = width_cm * sc, depth_cm * sc, height_cm * sc
    ch = counter_height_cm * sc
    fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 190), (fx + w, 190), (fx + w, 190 + d * 0.5), (fx, 190 + d * 0.5)], True)
    _add_mtext(msp, 'TOP VIEW (Counter)', (fx, 190 + d * 0.5 + 10), 3, 'MTEXT')
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_line(msp, (fx, 50 + ch), (fx + w, 50 + ch), 'HIDDEN')
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3, 'MTEXT')
    _draw_title_block(msp, f"Reception Counter {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path)
    return path
