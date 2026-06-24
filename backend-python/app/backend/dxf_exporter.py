"""
Professional DXF exporter — furniture templates with proper CAD geometry.
Fixes applied:
- save_generic() added (was missing — caused import crash)
- rectangular_table: proper legs added
- dining_chair: seat rectangle + legs added
- sofa: proper armrest LWPOLYLINE + cushion lines
- cabinet/wardrobe: door panels + handles
- update_extents() called before every saveas()
- CENTER linetype loaded safely (CENTER2 not always available)
- No dependency on text_tokenizer (only text_normalizer)
"""
import math
from datetime import datetime
import ezdxf
from app.backend.layer_manager import setup_layers
from app.backend.text_normalizer import normalize_dimension_text, clean_text_for_dxf
from app.backend.extents_updater import setup_a3_sheet, update_extents
from app.backend.titleblock_generator import generate_title_block
from app.backend.dxf_auditor import audit_dxf


def setup_doc():
    doc = ezdxf.new('R2010')
    setup_layers(doc)
    setup_a3_sheet(doc)
    # Load CENTER linetype — always available; CENTER2 may not be
    try:
        if 'CENTER' not in doc.linetypes:
            doc.linetypes.load_ltype_from_description('CENTER')
    except Exception:
        pass
    return doc


def _save(doc, path):
    """Finalize: update extents, audit, save, then force-patch extents in file."""
    try:
        update_extents(doc)
    except Exception:
        pass
    try:
        audit_dxf(doc)
    except Exception:
        pass
    doc.saveas(path)
    # Post-save: force-patch $EXTMIN/$EXTMAX directly in DXF text
    _force_extents_in_file(path)
    return path


def _force_extents_in_file(path):
    """Last-resort: directly patch $EXTMIN/$EXTMAX in the saved DXF file."""
    import re
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return
    # Parse DXF line-by-line: group codes (10/20) precede values on next line.
    # Only scan ENTITIES section — skip HEADER coordinates (EXTMIN/EXTMAX defaults).
    all_x, all_y = [], []
    lines = content.split('\n')
    in_entities = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == 'ENTITIES':
            in_entities = True
            continue
        if stripped == 'ENDSEC' and in_entities:
            break
        if not in_entities:
            continue
        code = stripped
        if code in ('10', '20') and i + 1 < len(lines):
            try:
                val = float(lines[i + 1].strip())
                if code == '10':
                    all_x.append(val)
                else:
                    all_y.append(val)
            except ValueError:
                continue
    if not all_x or not all_y:
        return
    mnx, mxx = min(all_x), max(all_x)
    mny, mxy = min(all_y), max(all_y)
    margin_x = max(10, (mxx - mnx) * 0.05)
    margin_y = max(10, (mxy - mny) * 0.05)
    new_min = f'$EXTMIN\n 10\n{mnx - margin_x}\n 20\n{mny - margin_y}\n 30\n0.0'
    new_max = f'$EXTMAX\n 10\n{mxx + margin_x}\n 20\n{mxy + margin_y}\n 30\n0.0'
    # Replace existing $EXTMIN/$EXTMAX groups spanning 7 lines each
    content = re.sub(
        r'\$EXTMIN\n\s*10\n[-\d.e+]+\n\s*20\n[-\d.e+]+\n\s*30\n[-\d.e+]+',
        new_min, content
    )
    content = re.sub(
        r'\$EXTMAX\n\s*10\n[-\d.e+]+\n\s*20\n[-\d.e+]+\n\s*30\n[-\d.e+]+',
        new_max, content
    )
    try:
        with open(path, 'w', encoding='utf-8', errors='replace') as f:
            f.write(content)
    except Exception:
        pass


def _add_polyline(msp, points, closed=False, layer='OBJECT'):
    if len(points) < 2:
        return
    try:
        msp.add_lwpolyline(points, close=closed, dxfattribs={'layer': layer})
    except Exception:
        for i in range(len(points) - 1):
            _add_line(msp, points[i], points[i + 1], layer)
        if closed and len(points) > 2:
            _add_line(msp, points[-1], points[0], layer)


def _add_mtext(msp, text, pos, height=3, layer='MTEXT'):
    if not text:
        return
    text = clean_text_for_dxf(str(text))
    try:
        m = msp.add_mtext(text, dxfattribs={'layer': layer, 'char_height': height})
        m.dxf.insert = pos
    except Exception:
        try:
            t = msp.add_text(text, dxfattribs={'height': height, 'layer': layer})
            t.dxf.insert = pos
        except Exception:
            pass


def _add_text(msp, txt, pt, h=2.5, layer='TEXT'):
    if not txt:
        return
    txt = clean_text_for_dxf(str(txt))
    try:
        e = msp.add_text(txt, dxfattribs={'height': h, 'layer': layer})
        e.dxf.insert = pt
    except Exception:
        pass


def _add_line(msp, a, b, layer='OBJECT'):
    if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-6:
        return
    msp.add_line(a, b, dxfattribs={'layer': layer})


def _add_centerline(msp, p1, p2):
    _add_line(msp, p1, p2, 'CENTER')


def _add_dimension(msp, p1, p2, loc, text=None):
    try:
        override = {'dimtxt': 2.5, 'dimasz': 2.0, 'dimdec': 0}
        d = msp.add_linear_dim(base=loc, p1=p1, p2=p2, override=override)
        if text:
            d.dimension.dxf.text = normalize_dimension_text(text)
        d.render()
    except Exception:
        _add_line(msp, p1, p2, 'DIMENSION')
        if text:
            _add_text(msp, normalize_dimension_text(text), loc, 2.5, 'TEXT')


def _add_diameter_dim(msp, center, radius, text=None):
    """Add diameter dimension with %%c symbol."""
    label = text or f'%%c{radius * 2:g} cm'
    _add_dimension(
        msp,
        (center[0] - radius, center[1]),
        (center[0] + radius, center[1]),
        (center[0], center[1] - radius - 8),
        label
    )


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
    except Exception:
        return None


def _add_leader(msp, text, start_point, end_point, height=3):
    """Add leader line with arrowhead and text on LEADER/MTEXT layers."""
    try:
        msp.add_line(start_point, end_point, dxfattribs={'layer': 'LEADER'})
        angle = math.atan2(end_point[1] - start_point[1], end_point[0] - start_point[0])
        arrow_size = 3
        p1 = (end_point[0] - arrow_size * math.cos(angle - 0.5),
              end_point[1] - arrow_size * math.sin(angle - 0.5))
        p2 = (end_point[0] - arrow_size * math.cos(angle + 0.5),
              end_point[1] - arrow_size * math.sin(angle + 0.5))
        # Single LWPOLYLINE triangle instead of 2 separate LINEs
        _add_polyline(msp, [end_point, p1, p2], closed=True, layer='LEADER')
        _add_mtext(msp, text, start_point, height, 'MTEXT')
    except Exception:
        pass


# ========= TEMPLATES =========

def save_round_pedestal_table(path, top_dia_cm=80, height_cm=70,
                               base_dia_cm=None, neck_dia_cm=None, top_thick_cm=None,
                               _scale_result=None, _validation_result=None):
    """Round pedestal table shop drawing with anti-hallucination rules.
    
    VISIBLE components (conf >= 0.70) → solid OBJECT layer
    ESTIMATED components (0.30 <= conf < 0.70) → dashed HIDDEN linetype, labeled EST.
    UNKNOWN components (conf < 0.30) → SKIPPED entirely
    
    Uses visual_ratio_scaler for proportion estimation.
    """
    # --- Anti-hallucination validation ---
    vr = _validation_result
    if vr is None:
        try:
            from app.backend.anti_hallucination_validator import validate_furniture_drawing
            from app.backend.visual_ratio_scaler import estimate_proportions
            sr = estimate_proportions("round_pedestal_table",
                                       {"top_diameter_cm": top_dia_cm,
                                        "overall_height_cm": height_cm})
            vr = validate_furniture_drawing("round_pedestal_table", sr.confidence)
        except ImportError:
            vr = None
    
    # Helper: determine if a component should be drawn and with what linetype
    def _visible(name): 
        if vr and name in vr.components:
            return vr.components[name].visibility != "UNKNOWN"
        return True
    def _is_estimated(name):
        if vr and name in vr.components:
            return vr.components[name].visibility == "ESTIMATED"
        return False
    
    # --- Proportion estimation ---
    if _scale_result is not None:
        sr = _scale_result
    else:
        try:
            from app.backend.visual_ratio_scaler import estimate_proportions
            sr = estimate_proportions("round_pedestal_table",
                                       {"top_diameter_cm": top_dia_cm,
                                        "overall_height_cm": height_cm})
        except ImportError:
            sr = None

    # Apply estimated dimensions, falling back to template defaults
    if sr and base_dia_cm is None:
        base_dia_cm = sr.get("pedestal_diameter_cm", top_dia_cm * 0.55)
    if sr and neck_dia_cm is None:
        neck_dia_cm = sr.get("neck_diameter_cm", top_dia_cm * 0.28)
    if sr and top_thick_cm is None:
        top_thick_cm = sr.get("top_thickness_cm", 4.0)

    # Final fallback defaults for any unset values
    base_dia_cm = base_dia_cm or top_dia_cm * 0.55
    neck_dia_cm = neck_dia_cm or top_dia_cm * 0.28
    top_thick_cm = top_thick_cm or 4.0
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    r_px = top_dia_cm / 2 * sc
    y_mid = 180
    cx, cy = 100, y_mid

    # ===== TOP VIEW =====
    try:
        msp.add_circle((cx, cy), r_px, dxfattribs={'layer': 'OBJECT'})
    except Exception:
        num_segments = 64
        points = []
        for i in range(num_segments):
            angle = 2 * math.pi * i / num_segments
            px = cx + r_px * math.cos(angle)
            py = cy + r_px * math.sin(angle)
            points.append((px, py))
        _add_polyline(msp, points, closed=True, layer='OBJECT')
    # Radial sunburst veneer lines (8 spokes — enough for visual cue)
    for i in range(8):
        angle = 2 * math.pi * i / 8
        x1 = cx + (r_px * 0.15) * math.cos(angle)
        y1 = cy + (r_px * 0.15) * math.sin(angle)
        x2 = cx + r_px * math.cos(angle)
        y2 = cy + r_px * math.sin(angle)
        _add_line(msp, (x1, y1), (x2, y2), 'HATCH')
    # Top surface wood grain hatch
    _add_hatch_polygon(msp, [(cx + r_px * math.cos(2 * math.pi * i / 64),
                              cy + r_px * math.sin(2 * math.pi * i / 64))
                             for i in range(64)], 'ANSI31', 0.3, 45.0)
    # Centerlines
    ext = max(4, r_px * 0.1)
    _add_centerline(msp, (cx - r_px - ext, cy), (cx + r_px + ext, cy))
    _add_centerline(msp, (cx, cy - r_px - ext), (cx, cy + r_px + ext))
    _add_diameter_dim(msp, (cx, cy), r_px, f'%%c{top_dia_cm:g} cm')
    _add_mtext(msp, 'TOP VIEW', (cx - 15, cy + r_px + ext + 5), 3)

    # ===== FRONT VIEW =====
    fx = 280
    h_px = height_cm * sc
    thick_px = top_thick_cm * sc
    nr_px = neck_dia_cm * 0.5 * sc
    br_px = base_dia_cm * 0.5 * sc
    top_y = y_mid + h_px / 2
    bot_y = y_mid - h_px / 2
    neck_top_y = top_y - thick_px
    neck_bot_y = bot_y + br_px * 0.3
    base_top_y = bot_y + br_px * 0.3
    base_bot_y = bot_y

    # Tabletop
    _add_polyline(msp, [(fx - r_px, top_y), (fx + r_px, top_y),
                        (fx + r_px, neck_top_y), (fx - r_px, neck_top_y)], True)
    # Narrow neck — metal ring, skip if unknown
    if _visible("neck_ring"):
        neck_layer = 'HIDDEN' if _is_estimated("neck_ring") else 'OBJECT'
        _add_polyline(msp, [(fx - nr_px, neck_top_y), (fx + nr_px, neck_top_y),
                            (fx + nr_px, neck_bot_y), (fx - nr_px, neck_bot_y)], True, neck_layer)
    # Textured column
    _add_polyline(msp, [(fx - nr_px, neck_bot_y), (fx + nr_px, neck_bot_y),
                        (fx + br_px, base_top_y), (fx - br_px, base_top_y)], True)
    # Wide base — draw dashed if estimated, skip if unknown
    if _visible("base_foot"):
        base_layer = 'HIDDEN' if _is_estimated("base_foot") else 'OBJECT'
        _add_polyline(msp, [(fx - br_px, base_top_y), (fx + br_px, base_top_y),
                            (fx + br_px, base_bot_y), (fx - br_px, base_bot_y)], True, base_layer)
        if _is_estimated("base_foot"):
            _add_text(msp, "(EST.)", (fx - br_px - 15, (base_top_y + base_bot_y) / 2), 2, 'MTEXT')
    # Hatch column
    _add_hatch_polygon(msp, [(fx - nr_px, neck_bot_y), (fx + nr_px, neck_bot_y),
                             (fx + br_px, base_top_y), (fx - br_px, base_top_y)], 'ANSI37', 0.3)
    # Dimensions
    _add_dimension(msp, (fx - br_px, bot_y - 5), (fx + br_px, bot_y - 5),
                   (fx, bot_y - 12), f'%%c{base_dia_cm:g} cm')
    _add_centerline(msp, (fx, bot_y - 5), (fx, top_y + 5))
    _add_dimension(msp, (fx + r_px + 10, bot_y), (fx + r_px + 10, top_y),
                   (fx + r_px + 20, (bot_y + top_y) / 2), f'H = {height_cm:g} cm')
    # Material leaders
    _add_leader(msp, 'WOOD TOP', (fx + r_px + 15, top_y - thick_px / 2),
                (fx + r_px, top_y - thick_px / 2))
    _add_leader(msp, 'TEXTURED PEDESTAL BASE',
                (fx + br_px + 15, (neck_bot_y + base_top_y) / 2),
                (fx + br_px, (neck_bot_y + base_top_y) / 2))
    _add_mtext(msp, 'FRONT VIEW', (fx - r_px, top_y + 10), 3)
    generate_title_block(msp, f"Round Pedestal Table %%c{top_dia_cm:.0f} x H{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         client="MARCO",
                         scale=f"1:{2 if sc == 0.5 else int(1/sc)}",
                         revision="A",
                         material_notes=[
                             "WOOD TOP — Solid hardwood, stained finish",
                             "PEDESTAL BASE — Textured hammered metal, black powder coat",
                             "NECK RING — Brushed stainless steel",
                         ])
    return _save(doc, path)


def save_rectangular_table(path, width_cm=120, depth_cm=80, height_cm=70, leg_thickness_cm=6):
    """Rectangular table with tabletop, 4 legs, stretchers, and dimensions."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.4
    w = width_cm * sc
    d = depth_cm * sc
    h = height_cm * sc
    w2, d2 = w / 2, d / 2
    ox, y_mid = 100, 180
    lt = leg_thickness_cm * sc  # leg thickness in pixels

    # ===== TOP VIEW =====
    _add_polyline(msp, [(ox - w2, y_mid - d2), (ox + w2, y_mid - d2),
                        (ox + w2, y_mid + d2), (ox - w2, y_mid + d2)], True)
    # Leg footprints (corners)
    for lx, ly in [(ox - w2, y_mid - d2), (ox + w2 - lt, y_mid - d2),
                   (ox - w2, y_mid + d2 - lt), (ox + w2 - lt, y_mid + d2 - lt)]:
        _add_polyline(msp, [(lx, ly), (lx + lt, ly), (lx + lt, ly + lt), (lx, ly + lt)], True, 'HIDDEN')
    _add_centerline(msp, (ox - w2 - 5, y_mid), (ox + w2 + 5, y_mid))
    _add_centerline(msp, (ox, y_mid - d2 - 5), (ox, y_mid + d2 + 5))
    _add_dimension(msp, (ox - w2, y_mid + d2 + 6), (ox + w2, y_mid + d2 + 6),
                   (ox, y_mid + d2 + 12), f'W = {width_cm:g} cm')
    _add_dimension(msp, (ox + w2 + 6, y_mid - d2), (ox + w2 + 6, y_mid + d2),
                   (ox + w2 + 14, y_mid), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'TOP VIEW', (ox - 15, y_mid + d2 + 22), 3)

    # ===== FRONT VIEW =====
    fx = 280
    floor_y = 30
    top_y = floor_y + h
    top_thick = max(lt * 0.8, 2.0)

    # Tabletop rectangle
    _add_polyline(msp, [(fx - w2, top_y - top_thick), (fx + w2, top_y - top_thick),
                        (fx + w2, top_y), (fx - w2, top_y)], True)
    _add_hatch_polygon(msp, [(fx - w2, top_y - top_thick), (fx + w2, top_y - top_thick),
                             (fx + w2, top_y), (fx - w2, top_y)], 'ANSI31', 0.5)
    # Front two legs (visible)
    leg_y_top = top_y - top_thick
    for lx in [fx - w2, fx + w2 - lt]:
        _add_polyline(msp, [(lx, floor_y), (lx + lt, floor_y),
                            (lx + lt, leg_y_top), (lx, leg_y_top)], True)
    # Back two legs (hidden lines)
    for lx in [fx - w2 + lt * 1.5, fx + w2 - lt * 2.5]:
        _add_line(msp, (lx, floor_y), (lx, leg_y_top), 'HIDDEN')
        _add_line(msp, (lx + lt, floor_y), (lx + lt, leg_y_top), 'HIDDEN')

    # Dimensions
    _add_dimension(msp, (fx + w2 + 8, floor_y), (fx + w2 + 8, top_y),
                   (fx + w2 + 16, (floor_y + top_y) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fx - w2, floor_y - 8), (fx + w2, floor_y - 8),
                   (fx, floor_y - 14), f'W = {width_cm:g} cm')
    _add_centerline(msp, (fx, floor_y - 5), (fx, top_y + 5))
    _add_mtext(msp, 'FRONT VIEW', (fx - w2, top_y + 10), 3)

    generate_title_block(msp, f"Rectangular Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    return _save(doc, path)


def save_cabinet(path, width_cm=100, depth_cm=50, height_cm=180):
    """Cabinet with double doors, shelves, handles, and dimensions."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.3
    w = width_cm * sc
    h = height_cm * sc
    fx = (420 - w) / 2
    floor_y = 50
    top_y = floor_y + h
    w2 = w / 2
    margin = w * 0.05

    # Outer body
    _add_polyline(msp, [(fx, floor_y), (fx + w, floor_y),
                        (fx + w, top_y), (fx, top_y)], True)
    # Center divider
    _add_centerline(msp, (fx + w2, floor_y), (fx + w2, top_y))
    # Shelves
    for i in [0.33, 0.55, 0.75]:
        _add_line(msp, (fx + 2, floor_y + h * i), (fx + w - 2, floor_y + h * i), 'HIDDEN')
    # Door panels (left)
    _add_polyline(msp, [(fx + margin, floor_y + margin),
                        (fx + w2 - margin, floor_y + margin),
                        (fx + w2 - margin, top_y - margin),
                        (fx + margin, top_y - margin)], True, 'HIDDEN')
    # Door panels (right)
    _add_polyline(msp, [(fx + w2 + margin, floor_y + margin),
                        (fx + w - margin, floor_y + margin),
                        (fx + w - margin, top_y - margin),
                        (fx + w2 + margin, top_y - margin)], True, 'HIDDEN')
    # Handles
    handle_y = floor_y + h * 0.5
    _add_line(msp, (fx + w2 - margin - 4, handle_y),
              (fx + w2 - margin, handle_y), 'OBJECT')
    _add_line(msp, (fx + w2 + margin, handle_y),
              (fx + w2 + margin + 4, handle_y), 'OBJECT')

    # Dimensions
    _add_dimension(msp, (fx + w + 8, floor_y), (fx + w + 8, top_y),
                   (fx + w + 16, (floor_y + top_y) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fx, floor_y - 8), (fx + w, floor_y - 8),
                   (fx + w2, floor_y - 14), f'W = {width_cm:g} cm')
    _add_mtext(msp, 'FRONT VIEW', (fx, top_y + 8), 3)

    generate_title_block(msp, f"Cabinet {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    return _save(doc, path)


def save_sofa(path, width_cm=200, depth_cm=80, height_cm=85, seat_height_cm=45):
    """Sofa with seat, backrest, armrests, and cushion dividers."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.3
    w = width_cm * sc
    h = height_cm * sc
    sh = seat_height_cm * sc
    fx = (420 - w) / 2
    floor_y = 50
    top_y = floor_y + h
    arm_w = w * 0.08

    # Outer body
    _add_polyline(msp, [(fx, floor_y), (fx + w, floor_y),
                        (fx + w, top_y), (fx, top_y)], True)
    # Seat line
    _add_line(msp, (fx + arm_w, floor_y + sh), (fx + w - arm_w, floor_y + sh), 'HIDDEN')
    # Left armrest
    _add_polyline(msp, [(fx, floor_y + sh), (fx + arm_w, floor_y + sh),
                        (fx + arm_w, floor_y), (fx, floor_y)], True)
    # Right armrest
    _add_polyline(msp, [(fx + w - arm_w, floor_y + sh), (fx + w, floor_y + sh),
                        (fx + w, floor_y), (fx + w - arm_w, floor_y)], True)
    # Back rest vertical lines
    back_x1 = fx + arm_w
    back_x2 = fx + w - arm_w
    _add_line(msp, (back_x1, floor_y + sh), (back_x1, top_y - 2), 'OBJECT')
    _add_line(msp, (back_x2, floor_y + sh), (back_x2, top_y - 2), 'OBJECT')
    # Cushion dividers (3 equal cushions)
    for i in [1, 2]:
        cx = back_x1 + (back_x2 - back_x1) * i / 3
        _add_line(msp, (cx, floor_y + 2), (cx, floor_y + sh - 2), 'HIDDEN')

    # Dimensions
    _add_dimension(msp, (fx + w + 8, floor_y), (fx + w + 8, top_y),
                   (fx + w + 16, (floor_y + top_y) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fx, floor_y - 8), (fx + w, floor_y - 8),
                   (fx + w / 2, floor_y - 14), f'W = {width_cm:g} cm')
    _add_mtext(msp, 'FRONT VIEW', (fx, top_y + 8), 3)

    generate_title_block(msp, f"Sofa {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    return _save(doc, path)


def save_coffee_table(path, width_cm=100, depth_cm=60, height_cm=45):
    """Round coffee table — top view circle with diameter dimension."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.6
    r = min(width_cm, depth_cm) / 2 * sc
    cx, y_mid = 100, 190
    try:
        msp.add_circle((cx, y_mid), r, dxfattribs={'layer': 'OBJECT'})
    except Exception:
        num_segments = 64
        points = [(cx + r * math.cos(2 * math.pi * i / num_segments),
                   y_mid + r * math.sin(2 * math.pi * i / num_segments))
                  for i in range(num_segments)]
        _add_polyline(msp, points, closed=True, layer='OBJECT')
    _add_centerline(msp, (cx - r - 5, y_mid), (cx + r + 5, y_mid))
    _add_centerline(msp, (cx, y_mid - r - 5), (cx, y_mid + r + 5))
    _add_diameter_dim(msp, (cx, y_mid), r, f'%%c{min(width_cm, depth_cm):g} cm')
    _add_mtext(msp, 'TOP VIEW', (cx - 10, y_mid + r + 10), 3)
    generate_title_block(msp, f"Coffee Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    return _save(doc, path)


def save_dining_chair(path, width_cm=45, depth_cm=45, height_cm=90, seat_height_cm=45):
    """Dining chair with seat, backrest, and 4 legs in front view."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    w = width_cm * sc
    sh = seat_height_cm * sc
    bh = (height_cm - seat_height_cm) * sc
    leg_thick = w * 0.1
    fx = 100
    floor_y = 30
    seat_thick = sh * 0.12
    seat_top_y = floor_y + sh
    back_top_y = seat_top_y + bh

    # Seat rectangle
    _add_polyline(msp, [(fx, seat_top_y - seat_thick), (fx + w, seat_top_y - seat_thick),
                        (fx + w, seat_top_y), (fx, seat_top_y)], True)
    _add_hatch_polygon(msp, [(fx, seat_top_y - seat_thick), (fx + w, seat_top_y - seat_thick),
                             (fx + w, seat_top_y), (fx, seat_top_y)], 'ANSI31', 0.4)
    # Backrest
    back_margin = w * 0.05
    _add_polyline(msp, [(fx + back_margin, seat_top_y),
                        (fx + w - back_margin, seat_top_y),
                        (fx + w - back_margin, back_top_y),
                        (fx + back_margin, back_top_y)], True)
    # Front legs
    for lx in [fx, fx + w - leg_thick]:
        _add_polyline(msp, [(lx, floor_y), (lx + leg_thick, floor_y),
                            (lx + leg_thick, seat_top_y - seat_thick),
                            (lx, seat_top_y - seat_thick)], True)
    # Rung
    rung_y = floor_y + sh * 0.35
    _add_line(msp, (fx + leg_thick, rung_y), (fx + w - leg_thick, rung_y), 'HIDDEN')

    # Dimensions
    _add_dimension(msp, (fx + w + 8, floor_y), (fx + w + 8, back_top_y),
                   (fx + w + 16, (floor_y + back_top_y) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fx, floor_y - 8), (fx + w, floor_y - 8),
                   (fx + w / 2, floor_y - 14), f'W = {width_cm:g} cm')
    _add_mtext(msp, 'FRONT VIEW', (fx, back_top_y + 8), 3)

    generate_title_block(msp, f"Dining Chair {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    return _save(doc, path)


def save_wardrobe(path, width_cm=120, depth_cm=60, height_cm=200):
    """Wardrobe with double doors, shelves, hanging rail, and handles."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.25
    w = width_cm * sc
    h = height_cm * sc
    fx = (420 - w) / 2
    floor_y = 50
    top_y = floor_y + h
    w2 = w / 2
    margin = w * 0.04

    # Outer body
    _add_polyline(msp, [(fx, floor_y), (fx + w, floor_y),
                        (fx + w, top_y), (fx, top_y)], True)
    _add_centerline(msp, (fx + w2, floor_y), (fx + w2, top_y))
    # Shelves
    for i in [0.2, 0.45, 0.65, 0.85]:
        _add_line(msp, (fx + 2, floor_y + h * i), (fx + w - 2, floor_y + h * i), 'HIDDEN')
    # Hanging rail
    rail_y = floor_y + h * 0.25
    _add_line(msp, (fx + 5, rail_y), (fx + w2 - 3, rail_y), 'HIDDEN')
    # Door panels
    for side_x, side_w in [(fx + margin, w2 - 2 * margin), (fx + w2 + margin, w2 - 2 * margin)]:
        _add_polyline(msp, [(side_x, floor_y + margin),
                            (side_x + side_w, floor_y + margin),
                            (side_x + side_w, top_y - margin),
                            (side_x, top_y - margin)], True, 'HIDDEN')
    # Handles
    handle_y = floor_y + h * 0.5
    _add_line(msp, (fx + w2 - margin - 4, handle_y),
              (fx + w2 - margin, handle_y), 'OBJECT')
    _add_line(msp, (fx + w2 + margin, handle_y),
              (fx + w2 + margin + 4, handle_y), 'OBJECT')

    # Dimensions
    _add_dimension(msp, (fx + w + 8, floor_y), (fx + w + 8, top_y),
                   (fx + w + 16, (floor_y + top_y) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fx, floor_y - 8), (fx + w, floor_y - 8),
                   (fx + w2, floor_y - 14), f'W = {width_cm:g} cm')
    _add_mtext(msp, 'FRONT VIEW', (fx, top_y + 8), 3)

    generate_title_block(msp, f"Wardrobe {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    return _save(doc, path)


def save_reception_counter(path, width_cm=180, depth_cm=80, height_cm=110, counter_height_cm=75):
    """Reception counter with top view, front view, and transaction height label."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.25
    w = width_cm * sc
    d = depth_cm * sc
    h = height_cm * sc
    ch = counter_height_cm * sc
    fx = (420 - w) / 2
    floor_y = 50
    top_y = floor_y + h

    # ===== TOP VIEW =====
    ty = 200
    _add_polyline(msp, [(fx, ty), (fx + w, ty), (fx + w, ty + d), (fx, ty + d)], True)
    _add_mtext(msp, 'TOP VIEW', (fx, ty + d + 10), 3)

    # ===== FRONT VIEW =====
    _add_polyline(msp, [(fx, floor_y), (fx + w, floor_y),
                        (fx + w, top_y), (fx, top_y)], True)
    # Transaction counter line
    _add_line(msp, (fx, floor_y + ch), (fx + w, floor_y + ch), 'HIDDEN')
    _add_leader(msp, f'COUNTER H={counter_height_cm}cm',
                (fx + w + 20, floor_y + ch), (fx + w, floor_y + ch))

    # Dimensions
    _add_dimension(msp, (fx + w + 8, floor_y), (fx + w + 8, top_y),
                   (fx + w + 16, (floor_y + top_y) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fx, floor_y - 8), (fx + w, floor_y - 8),
                   (fx + w / 2, floor_y - 14), f'W = {width_cm:g} cm')
    _add_mtext(msp, 'FRONT VIEW', (fx, top_y + 8), 3)

    generate_title_block(msp, f"Reception Counter {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}")
    return _save(doc, path)


def save_generic(path, lines, circles, rects=None):
    """Generic fallback — draws raw detected geometry on standard layers."""
    doc = setup_doc()
    msp = doc.modelspace()
    rects = rects or []

    for (x1, y1), (x2, y2) in (lines or []):
        _add_line(msp, (x1, y1), (x2, y2), 'OBJECT')

    for cx, cy, r in (circles or []):
        if r > 0:
            try:
                msp.add_circle((cx, cy), r, dxfattribs={'layer': 'OBJECT'})
            except Exception:
                pass

    for x1, y1, x2, y2 in rects:
        _add_polyline(msp, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], True)

    _add_mtext(msp, 'GENERIC 2D GEOMETRY (unclassified)', (10, 280), 4)
    generate_title_block(msp, "Generic 2D Furniture Drawing")
    return _save(doc, path)
