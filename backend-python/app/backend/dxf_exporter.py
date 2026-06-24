"""
Professional DXF — fixes from QC audit:
- Proper pedestal proportions (wide base, narrow neck)
- Radial sunburst veneer lines in top view (not ANSI31)
- %%c diameter symbol (not letter O)
- Material callout leaders
- Proper %%c diameter symbol
- No duplicate labels
"""
import math
from datetime import datetime
import ezdxf
from app.backend.layer_manager import setup_layers
from app.backend.text_tokenizer import clean_dimension_string, format_dimension_for_dxf
from app.backend.extents_updater import setup_a3_sheet, update_extents
from app.backend.titleblock_generator import generate_title_block
from app.backend.dxf_auditor import audit_dxf
from app.backend.semantic_proportion_validator import validate_furniture_proportions, get_semantic_hierarchy


def setup_doc():
    doc = ezdxf.new('R2010')
    setup_layers(doc)
    setup_a3_sheet(doc)
    return doc


def _add_polyline(msp, points, closed=False, layer='OBJECT'):
    if len(points) < 2: return
    try:
        msp.add_lwpolyline(points, close=closed, dxfattribs={'layer': layer})
    except Exception as e:
        for i in range(len(points) - 1):
            _add_line(msp, points[i], points[i + 1], layer)
        if closed and len(points) > 2:
            _add_line(msp, points[-1], points[0], layer)


def _add_mtext(msp, text, pos, height=3, layer='MTEXT'):
    if not text: return
    text = str(text).replace('\u00d8', '%%c').strip()
    try:
        m = msp.add_mtext(text, dxfattribs={'layer': layer, 'char_height': height})
        m.dxf.insert = pos
    except Exception:
        t = msp.add_text(text, dxfattribs={'height': height, 'layer': layer})
        t.dxf.insert = pos


def _add_text(msp, txt, pt, h=2.5, layer='TEXT'):
    if not txt: return
    txt = clean_text_for_dxf(txt)
    e = msp.add_text(txt, dxfattribs={'height': h, 'layer': layer})
    e.dxf.insert = pt


def _add_line(msp, a, b, layer='OBJECT'):
    if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-6: return
    msp.add_line(a, b, dxfattribs={'layer': layer})


def _add_centerline(msp, p1, p2):
    _add_line(msp, p1, p2, 'CENTER')


def _add_dimension(msp, p1, p2, loc, text=None):
    try:
        override = {'dimtxt': 2.5, 'dimasz': 2.0, 'dimdec': 0}
        d = msp.add_linear_dim(base=loc, p1=p1, p2=p2, override=override)
        if text:
            d.dimension.dxf.text = clean_dimension_string(str(text))
        d.render()
    except Exception:
        _add_line(msp, p1, p2, 'DIMENSION')
        if text:
            _add_text(msp, clean_dimension_string(str(text)), loc, 2.5, 'TEXT')


def _add_diameter_dim(msp, center, radius, text=None):
    """Use %%c for proper diameter symbol."""
    label = text or format_dimension_for_dxf(radius * 2, 'cm', is_diameter=True)
    _add_dimension(msp, (center[0] - radius, center[1]), (center[0] + radius, center[1]),
                   (center[0], center[1] - radius - 8), label)


def _add_hatch_polygon(msp, vertices, pattern='ANSI31', scale=1.0, angle=0.0):
    if len(vertices) < 3: return None
    try:
        h = msp.add_hatch(color=8)
        h.dxf.layer = 'HATCH'
        h.dxf.pattern_name = pattern
        h.dxf.pattern_scale = scale
        h.dxf.pattern_angle = angle
        h.paths.add_polyline_path(vertices, is_closed=True)
        return h
    except Exception as e:
        return None


def _add_leader(msp, text, start_point, end_point, height=3):
    """Add a leader with text annotation pointing to a feature."""
    try:
        # Add leader line
        msp.add_line(start_point, end_point, dxfattribs={'layer': 'DIMENSION'})
        # Add arrow at end
        angle = math.atan2(end_point[1] - start_point[1], end_point[0] - start_point[0])
        arrow_size = 3
        p1 = (end_point[0] - arrow_size * math.cos(angle - 0.5),
              end_point[1] - arrow_size * math.sin(angle - 0.5))
        p2 = (end_point[0] - arrow_size * math.cos(angle + 0.5),
              end_point[1] - arrow_size * math.sin(angle + 0.5))
        _add_line(msp, end_point, p1, 'DIMENSION')
        _add_line(msp, end_point, p2, 'DIMENSION')
        # Add text at start
        _add_mtext(msp, text, start_point, height, 'MTEXT')
    except Exception as e:
        pass


# ========= TEMPLATES =========

def save_round_pedestal_table(path, top_dia_cm=80, height_cm=70,
                               base_dia_cm=None, neck_dia_cm=None, top_thick_cm=4):
    """Fixed: Proper wide base, narrow neck, radial veneer, %%c symbol, material leaders."""
    base_dia_cm = base_dia_cm or top_dia_cm * 0.55  # 44cm base for 80cm top
    neck_dia_cm = neck_dia_cm or top_dia_cm * 0.28  # 22cm neck
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    r_px = top_dia_cm / 2 * sc  # 20
    y_mid = 180
    cx, cy = 100, y_mid

    # ===== TOP VIEW =====
    # Main circle
    msp.add_circle((cx, cy), r_px, dxfattribs={'layer': 'OBJECT'})

    # Radial sunburst lines (24 segments for veneer)
    for i in range(24):
        angle = 2 * math.pi * i / 24
        x1 = cx + (r_px * 0.1) * math.cos(angle)
        y1 = cy + (r_px * 0.1) * math.sin(angle)
        x2 = cx + r_px * math.cos(angle)
        y2 = cy + r_px * math.sin(angle)
        _add_line(msp, (x1, y1), (x2, y2), 'HATCH')

    # Centerlines
    ext = max(4, r_px * 0.1)
    _add_centerline(msp, (cx - r_px - ext, cy), (cx + r_px + ext, cy))
    _add_centerline(msp, (cx, cy - r_px - ext), (cx, cy + r_px + ext))

    # Diameter dimension with %%c
    _add_diameter_dim(msp, (cx, cy), r_px)
    _add_mtext(msp, 'TOP VIEW', (cx - 15, cy + r_px + ext + 5), 3)

    # ===== FRONT VIEW =====
    fx = 280
    h_px = height_cm * sc        # 35
    thick_px = top_thick_cm * sc  # 2
    # PROPER proportions: wide base, narrow neck
    nr_px = neck_dia_cm * 0.5 * sc   # 5.5 (narrow neck)
    br_px = base_dia_cm * 0.5 * sc    # 11 (wide base)
    top_y = y_mid + h_px / 2
    bot_y = y_mid - h_px / 2
    neck_top_y = top_y - thick_px
    neck_bot_y = bot_y + br_px * 0.3  # neck extends 30% up from base
    base_top_y = bot_y + br_px * 0.3
    base_bot_y = bot_y

    # Tabletop LWPOLYLINE
    _add_polyline(msp, [(fx - r_px, top_y), (fx + r_px, top_y),
                        (fx + r_px, neck_top_y), (fx - r_px, neck_top_y)], True)

    # NARROW neck (upper, between tabletop and textured column)
    _add_polyline(msp, [(fx - nr_px, neck_top_y), (fx + nr_px, neck_top_y),
                        (fx + nr_px, neck_bot_y), (fx - nr_px, neck_bot_y)], True)

    # WIDE textured column (main body)
    _add_polyline(msp, [(fx - nr_px, neck_bot_y), (fx + nr_px, neck_bot_y),
                        (fx + br_px, base_top_y), (fx - br_px, base_top_y)], True)

    # WIDE base
    _add_polyline(msp, [(fx - br_px, base_top_y), (fx + br_px, base_top_y),
                        (fx + br_px, base_bot_y), (fx - br_px, base_bot_y)], True)

    # Hatch textured column
    _add_hatch_polygon(msp, [(fx - nr_px, neck_bot_y), (fx + nr_px, neck_bot_y),
                             (fx + br_px, base_top_y), (fx - br_px, base_top_y)], 'ANSI37', 0.3)

    # Dimensions
    _add_dimension(msp, (fx - br_px, bot_y - 5), (fx + br_px, bot_y - 5),
                   (fx, bot_y - 12), f'%%c{base_dia_cm:g} cm')
    _add_centerline(msp, (fx, bot_y - 5), (fx, top_y + 5))
    _add_dimension(msp, (fx + r_px + 10, bot_y), (fx + r_px + 10, top_y),
                   (fx + r_px + 20, (bot_y + top_y) / 2), f'H = {height_cm:g} cm')

    # Material callout leaders
    _add_leader(msp, 'WOOD TOP', (fx + r_px + 15, top_y - thick_px/2), (fx + r_px, top_y - thick_px/2))
    _add_leader(msp, 'TEXTURED PEDESTAL BASE', (fx + br_px + 15, (neck_bot_y + base_top_y)/2),
                (fx + br_px, (neck_bot_y + base_top_y)/2))

    _add_mtext(msp, 'FRONT VIEW', (fx - r_px, top_y + 10), 3)
    generate_title_block(msp, f"Round Pedestal Table %%c{top_dia_cm:.0f} x H{height_cm:.0f}")
    result = audit_dxf(doc)
    doc.saveas(path)
    return path


def save_rectangular_table(path, width_cm=120, depth_cm=80, height_cm=70):
    doc = setup_doc(); msp = doc.modelspace()
    sc = 0.4; w, d, h = width_cm * sc, depth_cm * sc, height_cm * sc; w2, d2 = w / 2, d / 2
    ox, y_mid = 100, 180
    _add_polyline(msp, [(ox - w2, y_mid - d2), (ox + w2, y_mid - d2), (ox + w2, y_mid + d2), (ox - w2, y_mid + d2)], True)
    _add_centerline(msp, (ox - w2 - 5, y_mid), (ox + w2 + 5, y_mid))
    _add_mtext(msp, 'TOP VIEW', (ox - 15, y_mid + d2 + 8), 3)
    fx = 280
    _add_polyline(msp, [(fx - w2, h), (fx + w2, h), (fx + w2, h - 3), (fx - w2, h - 3)], True)
    _add_hatch_polygon(msp, [(fx - w2, h), (fx + w2, h), (fx + w2, h - 3), (fx - w2, h - 3)], 'ANSI31', 0.5)
    _add_mtext(msp, 'FRONT VIEW', (fx - w2, h + 10), 3)
    generate_title_block(msp, f"Rectangular Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path); return path


def save_cabinet(path, width_cm=100, depth_cm=50, height_cm=180):
    doc = setup_doc(); msp = doc.modelspace()
    sc = 0.3; w, h = width_cm * sc, height_cm * sc; fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_centerline(msp, (fx + w / 2, 50), (fx + w / 2, 50 + h))
    for i in range(1, 4): _add_line(msp, (fx, 50 + h * i / 4), (fx + w, 50 + h * i / 4), 'HIDDEN')
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3)
    generate_title_block(msp, f"Cabinet {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path); return path


def save_sofa(path, width_cm=200, depth_cm=80, height_cm=85, seat_height_cm=45):
    doc = setup_doc(); msp = doc.modelspace()
    sc = 0.3; w, h = width_cm * sc, height_cm * sc; sh = seat_height_cm * sc; fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_line(msp, (fx, 50 + sh), (fx + w, 50 + sh), 'HIDDEN')
    arm_w = w * 0.08
    _add_line(msp, (fx, 50 + sh), (fx + arm_w, 50 + sh))
    _add_line(msp, (fx + arm_w, 50 + sh), (fx + arm_w, 50))
    _add_line(msp, (fx + w - arm_w, 50 + sh), (fx + w, 50 + sh))
    _add_line(msp, (fx + w - arm_w, 50 + sh), (fx + w - arm_w, 50))
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3)
    generate_title_block(msp, f"Sofa {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path); return path


def save_coffee_table(path, width_cm=100, depth_cm=60, height_cm=45):
    doc = setup_doc(); msp = doc.modelspace()
    sc = 0.6; r = min(width_cm, depth_cm) / 2 * sc; cx, y_mid = 100, 190
    msp.add_circle((cx, y_mid), r, dxfattribs={'layer': 'OBJECT'})
    _add_centerline(msp, (cx - r - 5, y_mid), (cx + r + 5, y_mid))
    _add_centerline(msp, (cx, y_mid - r - 5), (cx, y_mid + r + 5))
    _add_diameter_dim(msp, (cx, y_mid), r)
    _add_mtext(msp, 'TOP VIEW', (cx - 10, y_mid + r + 10), 3)
    generate_title_block(msp, f"Coffee Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path); return path


def save_dining_chair(path, width_cm=45, depth_cm=45, height_cm=90, seat_height_cm=45):
    doc = setup_doc(); msp = doc.modelspace()
    sc = 0.5; w, sh = width_cm * sc, seat_height_cm * sc; bh = (height_cm - seat_height_cm) * sc; fx = (420 - w) / 2
    _add_polyline(msp, [(fx, sh), (fx + w, sh), (fx + w, sh + bh), (fx, sh + bh)], True)
    _add_line(msp, (fx - 5, sh + bh * 0.1), (fx + w + 5, sh + bh * 0.1), 'HIDDEN')
    _add_mtext(msp, 'SIDE VIEW', (fx, sh + bh + 10), 3)
    generate_title_block(msp, f"Dining Chair {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path); return path


def save_wardrobe(path, width_cm=120, depth_cm=60, height_cm=200):
    doc = setup_doc(); msp = doc.modelspace()
    sc = 0.25; w, h = width_cm * sc, height_cm * sc; fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_centerline(msp, (fx + w / 2, 50), (fx + w / 2, 50 + h))
    for i in range(1, 5): _add_line(msp, (fx, 50 + h * i / 5), (fx + w, 50 + h * i / 5), 'HIDDEN')
    _add_line(msp, (fx + 5, 50 + h * 0.8), (fx + w - 5, 50 + h * 0.8), 'HIDDEN')
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3)
    generate_title_block(msp, f"Wardrobe {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path); return path


def save_reception_counter(path, width_cm=180, depth_cm=80, height_cm=110, counter_height_cm=75):
    doc = setup_doc(); msp = doc.modelspace()
    sc = 0.25; w, d, h = width_cm * sc, depth_cm * sc, height_cm * sc; ch = counter_height_cm * sc; fx = (420 - w) / 2
    _add_polyline(msp, [(fx, 190), (fx + w, 190), (fx + w, 190 + d * 0.5), (fx, 190 + d * 0.5)], True)
    _add_mtext(msp, 'TOP VIEW', (fx, 190 + d * 0.5 + 10), 3)
    _add_polyline(msp, [(fx, 50), (fx + w, 50), (fx + w, 50 + h), (fx, 50 + h)], True)
    _add_line(msp, (fx, 50 + ch), (fx + w, 50 + ch), 'HIDDEN')
    _add_mtext(msp, 'FRONT VIEW', (fx, 50 + h + 8), 3)
    generate_title_block(msp, f"Reception Counter {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    doc.saveas(path); return path
