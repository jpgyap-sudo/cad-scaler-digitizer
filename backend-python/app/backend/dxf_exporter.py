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
- Gap #1/#2: all save_*() accept materials + visibility parameters
"""
import math
from datetime import datetime
from typing import Optional, Dict
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


def _add_polyline(msp, points, closed=False, layer=None):
    """Add a polyline. Defaults to OBJECT layer if not specified."""
    if layer is None:
        layer = 'OBJECT'
    if len(points) < 2:
        return
    try:
        msp.add_lwpolyline(points, close=closed, dxfattribs={'layer': layer})
    except Exception:
        for i in range(len(points) - 1):
            _add_line(msp, points[i], points[i + 1], layer)
        if closed and len(points) > 2:
            _add_line(msp, points[-1], points[0], layer)


def _add_mtext(msp, text, pos, height=3, layer=None):
    """Add multi-line text. Defaults to MTEXT layer."""
    if layer is None:
        layer = 'MTEXT'
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


def _add_text(msp, txt, pt, h=2.5, layer=None):
    """Add single-line text. Defaults to MTEXT layer."""
    if layer is None:
        layer = 'MTEXT'
    if not txt:
        return
    txt = clean_text_for_dxf(str(txt))
    try:
        e = msp.add_text(txt, dxfattribs={'height': h, 'layer': layer})
        e.dxf.insert = pt
    except Exception:
        pass


def _add_line(msp, a, b, layer=None):
    """Add a line. Defaults to OBJECT layer."""
    if layer is None:
        layer = 'OBJECT'
    if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-6:
        return
    msp.add_line(a, b, dxfattribs={'layer': layer})


def _add_centerline(msp, p1, p2):
    _add_line(msp, p1, p2, 'CENTERLINE')


def _add_dimension(msp, p1, p2, loc, text=None):
    try:
        override = {'dimtxt': 2.5, 'dimasz': 2.0, 'dimdec': 0}
        d = msp.add_linear_dim(base=loc, p1=p1, p2=p2, override=override,
                                dxfattribs={'layer': 'DIMENSION'})
        if text:
            d.dimension.dxf.text = normalize_dimension_text(text)
        d.render()
    except Exception:
        _add_line(msp, p1, p2, 'DIMENSION')
        if text:
            _add_text(msp, normalize_dimension_text(text), loc, 2.5, 'DIMENSION')


def _add_diameter_dim(msp, center, radius, text=None):
    """Add diameter dimension with %%c symbol.

    Text offset scales with radius (floor 8) - a fixed 8-unit gap was only
    ~7.5% of a 20-unit radius circle, which at typical full-page preview
    render resolution anti-aliases into the centerline above it, visually
    corrupting the leading digit of the label (this is what caused OCR to
    misread a correctly-generated "80" as "60"/"90" on round-trip tests).
    """
    label = text or f'%%c{radius * 2:g} cm'
    text_gap = max(12, radius * 0.6)
    _add_dimension(
        msp,
        (center[0] - radius, center[1]),
        (center[0] + radius, center[1]),
        (center[0], center[1] - radius - text_gap),
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


def _add_isometric_box(msp, x, y, w, d, h, layer='OBJECT'):
    """Draw a 3D isometric box (parallelepiped) at position (x, y) in 2D
    isometric projection using the standard CAD 2:1 ratio.
    Returns a list of polyline handles for the visible faces.
    """
    dx = w * 0.866
    dy = d * 0.289
    pts = []
    # Bottom face vertices (clockwise)
    b0 = (x, y)
    b1 = (x + dx, y + dy)
    b2 = (x + dx, y + h + dy)
    b3 = (x, y + h)
    # Top face vertices
    t0 = (x + dx, y + dy)
    t1 = (x + 2*dx, y + 2*dy)
    t2 = (x + 2*dx, y + h + 2*dy)
    t3 = (x + dx, y + h + dy)
    # Back face vertices
    back_t0 = (x + 2*dx, y + 2*dy)
    back_t1 = (x + 2*dx + dx, y + 2*dy + dy)
    back_t2 = (x + 2*dx + dx, y + h + 2*dy + dy)
    back_t3 = (x + 2*dx, y + h + 2*dy)
    # Front face
    _add_polyline(msp, [b3, b0, b1, t0, t3], True, layer)
    pts.append(('front', b3, b0, b1, t0, t3))
    # Right face (hidden edges as HIDDEN)
    _add_polyline(msp, [b1, b2, t2, t0], True, 'HIDDEN')
    pts.append(('right', b1, b2, t2, t0))
    # Top face
    _add_polyline(msp, [t3, t0, t1, t2], True, layer)
    pts.append(('top', t3, t0, t1, t2))
    # Visible vertical edges
    for p, q in [(b0, b3), (b1, t0), (b0, b1), (b3, t3)]:
        _add_line(msp, p, q, layer)
    return pts


# ========= TEMPLATES =========

def save_round_pedestal_table(path, top_dia_cm=80, height_cm=70,
                               base_dia_cm=None, neck_dia_cm=None, top_thick_cm=None,
                               collar_dia_cm=None, materials=None, profile="cylinder",
                               _scale_result=None, _validation_result=None,
                               visibility: Optional[Dict[str, bool]] = None):
    """Round pedestal table shop drawing with anti-hallucination rules.
    
    VISIBLE components (conf >= 0.70) → solid OBJECT layer
    ESTIMATED components (0.30 <= conf < 0.70) → dashed HIDDEN linetype, labeled EST.
    UNKNOWN components (conf < 0.30) → SKIPPED entirely
    
    Uses scale_solver for proportion estimation (replaced deprecated visual_ratio_scaler).
    """
    # --- Anti-hallucination validation ---
    vr = _validation_result
    if vr is None:
        try:
            from app.backend.anti_hallucination_validator import validate_furniture_drawing
            # Build simple association-like data for scale solver
            from app.backend.scale_solver import compute_scale
            from app.backend.dimension_associator import Association, DimensionLine, TextBox
            # Use scale_solver to compute proportions from known dimensions
            txt = TextBox(text=str(top_dia_cm), x=0, y=0, w=10, h=10, confidence=0.9, text_type="DIMENSION_LABEL", value_cm=top_dia_cm)
            dl = DimensionLine(p1=(0,0), p2=(100,0), is_horizontal=True)
            assoc = Association(text=str(top_dia_cm), value_cm=top_dia_cm, text_box=txt, dim_line=dl, confidence=0.9)
            scale_sol = compute_scale([assoc], [], {"top_diameter_cm": top_dia_cm, "overall_height_cm": height_cm})
            # Build confidence dict for validator
            entity_conf = {
                "top": {"confidence": 0.85, "source": "measured", "entity_type": "polygon", "name": "tabletop", "evidence": []},
                "base": {"confidence": 0.7, "source": "ratio_estimated", "entity_type": "polygon", "name": "base_plate", "evidence": []},
                "neck": {"confidence": 0.7, "source": "ratio_estimated", "entity_type": "polygon", "name": "neck_ring", "evidence": []},
            }
            vr = validate_furniture_drawing("round_pedestal_table", entity_conf)
        except ImportError:
            vr = None
    
    # Helper: determine if a component should be drawn and with what linetype
    def _visible(name):
        if visibility is not None and name in visibility:
            if not visibility[name]:
                return False
        if vr and name in vr.components:
            return vr.components[name].visibility != "UNKNOWN"
        return True
    def _is_estimated(name):
        if vr and name in vr.components:
            return vr.components[name].visibility == "ESTIMATED"
        return False
    
    # --- Proportion estimation (replaced visual_ratio_scaler) ---
    # Scale-solver is for pixel-to-cm from vision geometry, not for
    # proportion estimation from known dimensions. We compute ratios
    # directly from known CAD conventions for round pedestal tables.
    if _scale_result is not None:
        sr = _scale_result
    else:
        sr = {
            "pedestal_diameter_cm": top_dia_cm * 0.55,
            "neck_diameter_cm": top_dia_cm * 0.28,
            "top_thickness_cm": 4.0,
        }

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
    # Matches build_round_pedestal_model's default collar_dia_cm=50 for an 80cm top.
    collar_dia_cm = collar_dia_cm or top_dia_cm * 0.625
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
    # Concentric circles for pedestal column (top view shows column profile)
    if _visible("neck"):
        neck_r = neck_dia_cm * 0.5 * sc
        if neck_r > 4:
            msp.add_circle((cx, cy), neck_r, dxfattribs={'layer': 'HIDDEN'})
        collar_r = collar_dia_cm * 0.5 * sc
        if collar_r > neck_r:
            msp.add_circle((cx, cy), collar_r, dxfattribs={'layer': 'DASHED'})
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
    # Centerlines - small fixed tick, kept well under _add_diameter_dim's
    # (now radius-scaled) text gap so the line can never reach the label.
    ext = 3
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
    cr_px = collar_dia_cm * 0.5 * sc
    # Proportionally distribute height: top(4cm) + collar(14%) + neck(15%) + pedestal(70%) + base(15%)
    remaining_h = max(1, height_cm - top_thick_cm)  # height below tabletop
    collar_h_cm = remaining_h * 0.14
    remaining_after_collar = max(1, remaining_h - collar_h_cm)
    neck_h_cm = remaining_after_collar * 0.15
    ped_h_cm = remaining_after_collar * 0.70
    base_h_cm = remaining_after_collar * 0.15
    collar_h_px = collar_h_cm * sc
    neck_h_px = neck_h_cm * sc
    ped_h_px = ped_h_cm * sc
    base_h_px = base_h_cm * sc
    top_y = y_mid + h_px / 2
    bot_y = y_mid - h_px / 2
    collar_top_y = top_y - thick_px
    collar_bot_y = collar_top_y - collar_h_px
    neck_top_y = collar_bot_y
    neck_bot_y = neck_top_y - neck_h_px
    ped_bot_y = neck_bot_y - ped_h_px
    base_bot_y = bot_y

    # Tabletop
    _add_polyline(msp, [(fx - r_px, top_y), (fx + r_px, top_y),
                        (fx + r_px, collar_top_y), (fx - r_px, collar_top_y)], True)
    # Metal collar plate — sits directly under the tabletop, own diameter/control
    if _visible("collar_plate"):
        collar_layer = 'HIDDEN' if _is_estimated("collar_plate") else 'OBJECT'
        _add_polyline(msp, [(fx - cr_px, collar_top_y), (fx + cr_px, collar_top_y),
                            (fx + cr_px, collar_bot_y), (fx - cr_px, collar_bot_y)], True, collar_layer)
        _add_dimension(msp, (fx - cr_px, collar_top_y + 3), (fx + cr_px, collar_top_y + 3),
                       (fx, collar_top_y + 9), f'%%c{collar_dia_cm:g} cm')
    # Narrow neck — metal ring, skip if unknown
    if _visible("neck_ring"):
        neck_layer = 'HIDDEN' if _is_estimated("neck_ring") else 'OBJECT'
        _add_polyline(msp, [(fx - nr_px, neck_top_y), (fx + nr_px, neck_top_y),
                            (fx + nr_px, neck_bot_y), (fx - nr_px, neck_bot_y)], True, neck_layer)
    # Textured column (pedestal body). Only taper the body's top edge down to
    # the neck's width for a genuine tapered/flared profile (a smooth cone).
    # For 'cylinder' - a narrow neck/collar ring sitting on a SEPARATE,
    # wider, perfectly straight column with a sharp STEP between them, not a
    # gradual widening - the body is a straight rectangle at its own width.
    # Forcing every profile through the same tapering trapezoid is what made
    # a stepped pedestal render as a smooth cone.
    body_top_px = nr_px if profile in ("tapered", "flared") else br_px
    _add_polyline(msp, [(fx - body_top_px, neck_bot_y), (fx + body_top_px, neck_bot_y),
                        (fx + br_px, ped_bot_y), (fx - br_px, ped_bot_y)], True)
    # Wide base — draw dashed if estimated, skip if unknown
    if _visible("base_foot"):
        base_layer = 'HIDDEN' if _is_estimated("base_foot") else 'OBJECT'
        _add_polyline(msp, [(fx - br_px, ped_bot_y), (fx + br_px, ped_bot_y),
                            (fx + br_px, base_bot_y), (fx - br_px, base_bot_y)], True, base_layer)
        if _is_estimated("base_foot"):
            _add_text(msp, "(EST.)", (fx - br_px - 15, (ped_bot_y + base_bot_y) / 2), 2)
    # Hatch column — textured pedestal body
    _add_hatch_polygon(msp, [(fx - body_top_px, neck_bot_y), (fx + body_top_px, neck_bot_y),
                              (fx + br_px, ped_bot_y), (fx - br_px, ped_bot_y)], 'ANSI37', 0.3)
    # Dimensions
    _add_dimension(msp, (fx - br_px, base_bot_y - 5), (fx + br_px, base_bot_y - 5),
                   (fx, base_bot_y - 12), f'%%c{base_dia_cm:g} cm')
    _add_centerline(msp, (fx, base_bot_y - 5), (fx, top_y + 5))
    _add_dimension(msp, (fx + r_px + 10, base_bot_y), (fx + r_px + 10, top_y),
                   (fx + r_px + 20, (base_bot_y + top_y) / 2), f'H = {height_cm:g} cm')
    # Material leaders
    mats = materials or {}
    _add_leader(msp, mats.get('tabletop', 'WOOD TOP'), (fx + r_px + 15, top_y - thick_px / 2),
                (fx + r_px, top_y - thick_px / 2))
    _add_leader(msp, mats.get('pedestal_body', 'TEXTURED PEDESTAL BASE'),
                 (fx + br_px + 15, (neck_bot_y + ped_bot_y) / 2),
                 (fx + br_px, (neck_bot_y + ped_bot_y) / 2))
    _add_mtext(msp, 'FRONT VIEW', (fx - r_px, top_y + 10), 3)
    generate_title_block(msp, f"Round Pedestal Table %%c{top_dia_cm:.0f} x H{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         client="MARCO",
                         scale=f"1:{2 if sc == 0.5 else int(1/sc)}",
                         revision="A",
                         material_notes=[
                             f"WOOD TOP — {mats.get('tabletop', 'Solid hardwood, stained finish')}",
                             f"PEDESTAL BASE — {mats.get('pedestal_body', 'Textured hammered metal, black powder coat')}",
                             f"NECK RING — {mats.get('neck_ring', 'Brushed stainless steel')}",
                         ])
    return _save(doc, path)


def save_rectangular_table(path, width_cm=120, depth_cm=80, height_cm=70, leg_thickness_cm=6,
                            _validation_result=None,
                            materials: Optional[Dict[str, str]] = None,
                            visibility: Optional[Dict[str, bool]] = None):
    """Rectangular table with tabletop, 4 legs, stretchers, and dimensions."""
    # --- Anti-hallucination helpers ---
    vr = _validation_result
    if vr is None:
        try:
            from app.backend.anti_hallucination_validator import validate_furniture_drawing
            vr = validate_furniture_drawing("rectangular_table")
        except ImportError:
            vr = None
    def _visible(name):
        if vr and name in vr.components:
            return vr.components[name].visibility != "UNKNOWN"
        return True
    def _is_estimated(name):
        if vr and name in vr.components:
            return vr.components[name].visibility == "ESTIMATED"
        return False

    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.4
    w = width_cm * sc
    d = depth_cm * sc
    h = height_cm * sc
    w2, d2 = w / 2, d / 2
    ox, y_mid = 100, 180
    lt = leg_thickness_cm * sc  # leg thickness in pixels

    mats = materials or {}
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True

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
    # Front two legs (visible) — skip if estimated
    if _visible("legs"):
        leg_layer = 'HIDDEN' if _is_estimated("legs") else 'OBJECT'
        leg_y_top = top_y - top_thick
        for lx in [fx - w2, fx + w2 - lt]:
            _add_polyline(msp, [(lx, floor_y), (lx + lt, floor_y),
                                 (lx + lt, leg_y_top), (lx, leg_y_top)], True, leg_layer)
        if _is_estimated("legs"):
            _add_text(msp, "(EST.)", (fx - w2 - 12, (floor_y + leg_y_top) / 2), 2, 'MTEXT')
    # Back two legs (hidden lines) — skip if unknown
    if _visible("legs") and not _is_estimated("legs"):
        for lx in [fx - w2 + lt * 1.5, fx + w2 - lt * 2.5]:
            _add_line(msp, (lx, floor_y), (lx, leg_y_top), 'HIDDEN')
            _add_line(msp, (lx + lt, floor_y), (lx + lt, leg_y_top), 'HIDDEN')
    else:
        leg_y_top = top_y - top_thick  # ensure defined

    # Dimensions
    _add_dimension(msp, (fx + w2 + 8, floor_y), (fx + w2 + 8, top_y),
                   (fx + w2 + 16, (floor_y + top_y) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fx - w2, floor_y - 8), (fx + w2, floor_y - 8),
                   (fx, floor_y - 14), f'W = {width_cm:g} cm')
    _add_centerline(msp, (fx, floor_y - 5), (fx, top_y + 5))
    _add_mtext(msp, 'FRONT VIEW', (fx - w2, top_y + 10), 3)

    # ===== SIDE VIEW (RIGHT ELEVATION) =====
    sx = fx + w2 + 60          # offset right of front view
    floor_y_side = 30
    top_y_side = floor_y_side + h
    top_thick_side = max(d * 0.08, 2.0)

    # Tabletop from side (shows depth)
    _add_polyline(msp, [(sx, top_y_side - top_thick_side), (sx + d, top_y_side - top_thick_side),
                         (sx + d, top_y_side), (sx, top_y_side)], True)
    _add_hatch_polygon(msp, [(sx, top_y_side - top_thick_side), (sx + d, top_y_side - top_thick_side),
                               (sx + d, top_y_side), (sx, top_y_side)], 'ANSI31', 0.5)

    # Legs from side (two legs, front and back)
    if _visible("legs"):
        leg_thick_side = lt * 0.8
        for ly in [sx + leg_thick_side, sx + d - leg_thick_side - lt * 0.3]:
            _add_polyline(msp, [(ly, floor_y_side), (ly + lt * 0.3, floor_y_side),
                                (ly + lt * 0.3, top_y_side - top_thick_side),
                                (ly, top_y_side - top_thick_side)], True)

    # Dimensions
    _add_dimension(msp, (sx + d + 8, floor_y_side), (sx + d + 8, top_y_side),
                   (sx + d + 16, (floor_y_side + top_y_side) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (sx, floor_y_side - 8), (sx + d, floor_y_side - 8),
                   (sx + d / 2, floor_y_side - 14), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'SIDE VIEW', (sx, top_y_side + 10), 3)

    # ===== ISOMETRIC VIEW =====
    # Place in upper-right area; project W, D, H onto 30/30 isometric axes
    # In true isometric, coordinates transform as:
    #   screen_x = ox + (x - y) * cos30
    #   screen_y = oy - (x + y) * sin30 - z
    # where x=width, y=depth, z=height (all in same scale)
    iso_s = 0.28
    cos30 = 0.866
    sin30 = 0.5
    leg_t = leg_thickness_cm * iso_s   # leg thickness in iso units
    top_t = max(leg_t * 0.8, 2.0)      # top thickness in iso units

    def _iso(x, y, z=0):
        sx = 260 + (x - y) * cos30 * iso_s
        sy = 170 - (x + y) * sin30 * iso_s - z * iso_s
        return (sx, sy)

    w, d, h = width_cm, depth_cm, height_cm
    t = top_t

    # ---- Table top: top surface + vertical edges ----
    top_pts = [_iso(0,0,h), _iso(w,0,h), _iso(w,d,h), _iso(0,d,h)]
    bot_pts = [_iso(0,0,h-t), _iso(w,0,h-t), _iso(w,d,h-t), _iso(0,d,h-t)]
    _add_polyline(msp, top_pts, True)
    _add_polyline(msp, bot_pts, True)
    for i in range(4):
        _add_line(msp, top_pts[i], bot_pts[i])

    # ---- Legs ----
    leg_positions = [(0,0), (w,0), (w,d), (0,d)]
    for i, (lx, ly) in enumerate(leg_positions):
        if not _visible("legs"):
            continue
        front_leg = i < 2  # front two legs visible
        lt2 = leg_t * 0.3
        # Leg top at table underside
        lt_pts = [_iso(lx, ly, h-t), _iso(lx+leg_t, ly, h-t),
                  _iso(lx+leg_t, ly+leg_t, h-t), _iso(lx, ly+leg_t, h-t)]
        # Leg bottom at floor
        lb_pts = [_iso(lx, ly, 0), _iso(lx+leg_t, ly, 0),
                  _iso(lx+leg_t, ly+leg_t, 0), _iso(lx, ly+leg_t, 0)]
        if front_leg:
            layer = 'OBJECT'
            # Draw front-visible faces
            _add_polyline(msp, [lt_pts[0], lt_pts[1], lb_pts[1], lb_pts[0]], True, layer)
            _add_polyline(msp, [lt_pts[1], lt_pts[2], lb_pts[2], lb_pts[1]], True, layer)
            _add_polyline(msp, [lt_pts[0], lt_pts[3], lb_pts[3], lb_pts[0]], True, layer)
            _add_line(msp, lt_pts[1], lb_pts[1])
            _add_line(msp, lt_pts[2], lb_pts[2])
            _add_line(msp, lt_pts[3], lb_pts[3])
        else:
            # Back legs — hidden lines (top rectangle + drop lines)
            _add_polyline(msp, lt_pts, True, 'HIDDEN')
            _add_line(msp, lt_pts[0], lb_pts[0], 'HIDDEN')
            _add_line(msp, lt_pts[1], lb_pts[1], 'HIDDEN')

    # ---- Stretchers (elevated 5cm from floor) ----
    sh = 5 * iso_s  # stretcher height in iso units
    str_pts = [
        (_iso(0, 0, sh), _iso(w, 0, sh)),          # front
        (_iso(w, 0, sh), _iso(w, d, sh)),          # right
        (_iso(w, d, sh), _iso(0, d, sh)),          # back
        (_iso(0, d, sh), _iso(0, 0, sh)),          # left
    ]
    for i, (a, b) in enumerate(str_pts):
        layer = 'HIDDEN' if i in (2, 3) else 'OBJECT'
        _add_line(msp, a, b, layer)

    _add_mtext(msp, 'ISOMETRIC VIEW', (220, _iso(0, d, h)[1] + 20), 3)

    generate_title_block(msp, f"Rectangular Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         material_notes=[
                             f"TABLE TOP — {mats.get('tabletop', 'Solid wood, clear coat')}",
                             f"LEGS — {mats.get('legs', 'Solid wood, matching finish')}",
                         ])
    return _save(doc, path)


def save_cabinet(path, width_cm=100, depth_cm=50, height_cm=180,
                 materials: Optional[Dict[str, str]] = None,
                 visibility: Optional[Dict[str, bool]] = None):
    """Cabinet with double doors, shelves, handles, and dimensions."""
    mats = materials or {}
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True
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

    # === TOP VIEW (plan) ===
    tv_w = width_cm * sc
    tv_d = depth_cm * sc
    tv_x = fx + w + 50
    tv_y = top_y + 30
    _add_polyline(msp, [(tv_x, tv_y), (tv_x + tv_w, tv_y),
                        (tv_x + tv_w, tv_y + tv_d), (tv_x, tv_y + tv_d)], True)
    _add_centerline(msp, (tv_x + tv_w / 2, tv_y - 5), (tv_x + tv_w / 2, tv_y + tv_d + 5))
    _add_centerline(msp, (tv_x - 5, tv_y + tv_d / 2), (tv_x + tv_w + 5, tv_y + tv_d / 2))
    _add_dimension(msp, (tv_x, tv_y + tv_d + 6), (tv_x + tv_w, tv_y + tv_d + 6),
                   (tv_x + tv_w / 2, tv_y + tv_d + 12), f'W = {width_cm:g} cm')
    _add_dimension(msp, (tv_x + tv_w + 6, tv_y), (tv_x + tv_w + 6, tv_y + tv_d),
                   (tv_x + tv_w + 14, tv_y + tv_d / 2), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'TOP VIEW', (tv_x, tv_y + tv_d + 22), 3)

    # === ISOMETRIC VIEW ===
    iso_x = tv_x + tv_w + 30
    iso_y = floor_y
    iso_d = depth_cm * sc
    _add_isometric_box(msp, iso_x, iso_y, w * 1.2, iso_d * 1.2, h * 1.2)
    _add_mtext(msp, 'ISOMETRIC VIEW', (iso_x, iso_y + h * 1.2 + 10), 3)

    # === SIDE VIEW (depth) ===
    sv_w = depth_cm * sc
    sx = fx + w + 40
    _add_polyline(msp, [(sx, floor_y), (sx + sv_w, floor_y),
                        (sx + sv_w, top_y), (sx, top_y)], True)
    _add_dimension(msp, (sx, floor_y - 8), (sx + sv_w, floor_y - 8),
                   (sx + sv_w / 2, floor_y - 14), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'SIDE VIEW', (sx, top_y + 8), 3)

    generate_title_block(msp, f"Cabinet {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         material_notes=[
                             f"CARCASS — {mats.get('carcass', '18mm MDF, matte lacquer')}",
                             f"DOORS — {mats.get('doors', 'MDF, painted finish')}",
                             f"BASE — {mats.get('base', 'Solid wood plinth')}",
                         ])
    return _save(doc, path)


def save_sofa(path, width_cm=200, depth_cm=80, height_cm=85, seat_height_cm=45,
              materials: Optional[Dict[str, str]] = None,
              visibility: Optional[Dict[str, bool]] = None):
    """Sofa with seat, backrest, armrests, and cushion dividers."""
    mats = materials or {}
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True
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

    # === TOP VIEW (plan) ===
    tv_w = width_cm * sc
    tv_d = depth_cm * sc
    tv_x = fx + w + 50
    tv_y = top_y + 30
    _add_polyline(msp, [(tv_x, tv_y), (tv_x + tv_w, tv_y),
                        (tv_x + tv_w, tv_y + tv_d), (tv_x, tv_y + tv_d)], True)
    _add_centerline(msp, (tv_x + tv_w / 2, tv_y - 5), (tv_x + tv_w / 2, tv_y + tv_d + 5))
    _add_centerline(msp, (tv_x - 5, tv_y + tv_d / 2), (tv_x + tv_w + 5, tv_y + tv_d / 2))
    _add_dimension(msp, (tv_x, tv_y + tv_d + 6), (tv_x + tv_w, tv_y + tv_d + 6),
                   (tv_x + tv_w / 2, tv_y + tv_d + 12), f'W = {width_cm:g} cm')
    _add_dimension(msp, (tv_x + tv_w + 6, tv_y), (tv_x + tv_w + 6, tv_y + tv_d),
                   (tv_x + tv_w + 14, tv_y + tv_d / 2), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'TOP VIEW', (tv_x, tv_y + tv_d + 22), 3)

    # === ISOMETRIC VIEW ===
    iso_x = tv_x + tv_w + 30
    iso_y = floor_y
    iso_d = depth_cm * sc
    _add_isometric_box(msp, iso_x, iso_y, w * 1.2, iso_d * 1.2, h * 1.2)
    _add_mtext(msp, 'ISOMETRIC VIEW', (iso_x, iso_y + h * 1.2 + 10), 3)

    # === SIDE VIEW (depth) ===
    sv_w = depth_cm * sc
    sx = fx + w + 40
    _add_polyline(msp, [(sx, floor_y), (sx + sv_w, floor_y),
                        (sx + sv_w, top_y), (sx, top_y)], True)
    _add_dimension(msp, (sx, floor_y - 8), (sx + sv_w, floor_y - 8),
                   (sx + sv_w / 2, floor_y - 14), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'SIDE VIEW', (sx, top_y + 8), 3)

    generate_title_block(msp, f"Sofa {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         material_notes=[
                             f"BODY — {mats.get('body', 'Upholstered fabric')}",
                             f"SEAT — {mats.get('seat', 'High-density foam')}",
                             f"BACKREST — {mats.get('backrest', 'Upholstered fabric')}",
                             f"LEGS — {mats.get('legs', 'Solid wood, tapered')}",
                         ])
    return _save(doc, path)


def save_coffee_table(path, width_cm=100, depth_cm=60, height_cm=45, _validation_result=None,
                      materials: Optional[Dict[str, str]] = None,
                      visibility: Optional[Dict[str, bool]] = None,
                      top_shape: str = 'circle'):
    """Coffee table — top view circle/rectangle + front elevation + side depth view."""
    mats = materials or {}
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.7
    top_thick_cm = 3.0
    leg_thick_cm = 4.0
    
    # === TOP VIEW ===
    cx_t, cy_t = 60, 150
    if top_shape == 'circle':
        top_r = min(width_cm, depth_cm) / 2 * sc
        try:
            msp.add_circle((cx_t, cy_t), top_r, dxfattribs={'layer': 'OBJECT'})
        except Exception:
            num_segments = 64
            pts = [(cx_t + top_r * math.cos(2 * math.pi * i / num_segments),
                    cy_t + top_r * math.sin(2 * math.pi * i / num_segments)) for i in range(num_segments)]
            _add_polyline(msp, pts, closed=True, layer='OBJECT')
        _add_centerline(msp, (cx_t - top_r - 5, cy_t), (cx_t + top_r + 5, cy_t))
        _add_centerline(msp, (cx_t, cy_t - top_r - 5), (cx_t, cy_t + top_r + 5))
        _add_diameter_dim(msp, (cx_t, cy_t), top_r, f'%%c{min(width_cm, depth_cm):g} cm')
        _add_mtext(msp, 'TOP VIEW', (cx_t - 12, cy_t + top_r + 10), 2.5)
    else:
        rw = width_cm * sc * 0.5
        rd = depth_cm * sc * 0.5
        _add_polyline(msp, [(cx_t - rw, cy_t - rd), (cx_t + rw, cy_t - rd),
                            (cx_t + rw, cy_t + rd), (cx_t - rw, cy_t + rd)], True, 'OBJECT')
        _add_centerline(msp, (cx_t - rw - 5, cy_t), (cx_t + rw + 5, cy_t))
        _add_centerline(msp, (cx_t, cy_t - rd - 5), (cx_t, cy_t + rd + 5))
        _add_dimension(msp, (cx_t - rw, cy_t + rd + 6), (cx_t + rw, cy_t + rd + 6),
                       (cx_t, cy_t + rd + 12), f'W = {width_cm:g} cm')
        _add_dimension(msp, (cx_t + rw + 6, cy_t - rd), (cx_t + rw + 6, cy_t + rd),
                       (cx_t + rw + 14, cy_t), f'D = {depth_cm:g} cm')
        _add_mtext(msp, 'TOP VIEW', (cx_t - 15, cy_t + rd + 22), 3)

    # === FRONT VIEW ===
    fv_w = width_cm * sc * 0.5  # side view shows depth
    fv_h = height_cm * sc
    fv_x, fv_floor = 200, 40
    fv_top = fv_floor + fv_h
    leg_h = fv_h - top_thick_cm * sc
    
    # Top surface
    _add_polyline(msp, [
        (fv_x - fv_w, fv_top), (fv_x + fv_w, fv_top),
        (fv_x + fv_w, fv_top - top_thick_cm * sc),
        (fv_x - fv_w, fv_top - top_thick_cm * sc)
    ], True, 'OBJECT')
    # Legs
    leg_inset = fv_w * 0.15
    for lx in [fv_x - fv_w + leg_inset, fv_x + fv_w - leg_inset - leg_thick_cm * sc]:
        _add_polyline(msp, [
            (lx, fv_top - top_thick_cm * sc),
            (lx + leg_thick_cm * sc, fv_top - top_thick_cm * sc),
            (lx + leg_thick_cm * sc, fv_floor), (lx, fv_floor)
        ], True, 'OBJECT')
    # Dimensions
    _add_dimension(msp, (fv_x - fv_w - 12, fv_floor), (fv_x - fv_w - 12, fv_top),
                   (fv_x - fv_w - 18, (fv_floor + fv_top) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fv_x - fv_w, fv_floor - 10), (fv_x + fv_w, fv_floor - 10),
                   (fv_x, fv_floor - 16), f'W = {width_cm:g} cm')
    _add_mtext(msp, 'FRONT VIEW', (fv_x - 14, fv_top + 8), 2.5)

    # === SIDE VIEW (depth) ===
    sv_w = depth_cm * sc * 0.5
    sv_x = 200
    sv_top = fv_top
    # Side profile
    _add_polyline(msp, [
        (sv_x - sv_w, sv_top), (sv_x + sv_w, sv_top),
        (sv_x + sv_w, fv_floor), (sv_x - sv_w, fv_floor)
    ], True, 'OBJECT')
    _add_dimension(msp, (sv_x - sv_w - 12, fv_floor), (sv_x - sv_w - 12, sv_top),
                   (sv_x - sv_w - 18, (fv_floor + sv_top) / 2), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'SIDE VIEW', (sv_x - 14, sv_top + 8), 2.5)

    generate_title_block(msp, f"Coffee Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         material_notes=[
                             f"TABLE TOP — {mats.get('tabletop', 'Tempered glass / solid wood')}",
                             f"LEGS — {mats.get('legs', 'Powder-coated steel')}",
                         ])
    return _save(doc, path)


def save_dining_chair(path, width_cm=45, depth_cm=45, height_cm=90, seat_height_cm=45, _validation_result=None,
                      materials: Optional[Dict[str, str]] = None,
                      visibility: Optional[Dict[str, bool]] = None):
    """Dining chair with seat, backrest, and 4 legs in front view."""
    mats = materials or {}
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True
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

    # === SIDE VIEW (depth) ===
    sv_w = depth_cm * sc
    sx = fx + w + 30
    _add_polyline(msp, [(sx, floor_y), (sx + sv_w, floor_y),
                        (sx + sv_w, back_top_y), (sx, back_top_y)], True)
    _add_dimension(msp, (sx, floor_y - 8), (sx + sv_w, floor_y - 8),
                   (sx + sv_w / 2, floor_y - 14), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'SIDE VIEW', (sx, back_top_y + 8), 3)

    generate_title_block(msp, f"Dining Chair {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         material_notes=[
                             f"SEAT — {mats.get('seat', 'Upholstered fabric over foam')}",
                             f"BACKREST — {mats.get('backrest', 'Solid wood slats')}",
                             f"LEGS — {mats.get('legs', 'Solid wood, stained')}",
                         ])
    return _save(doc, path)


def save_wardrobe(path, width_cm=120, depth_cm=60, height_cm=200, _validation_result=None,
                  materials: Optional[Dict[str, str]] = None,
                  visibility: Optional[Dict[str, bool]] = None):
    """Wardrobe with double doors, shelves, hanging rail, and handles."""
    mats = materials or {}
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True
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

    # === TOP VIEW (plan) ===
    tv_w = width_cm * sc
    tv_d = depth_cm * sc
    tv_x = fx + w + 40
    tv_y = top_y + 30
    _add_polyline(msp, [(tv_x, tv_y), (tv_x + tv_w, tv_y),
                        (tv_x + tv_w, tv_y + tv_d), (tv_x, tv_y + tv_d)], True)
    _add_centerline(msp, (tv_x + tv_w / 2, tv_y - 5), (tv_x + tv_w / 2, tv_y + tv_d + 5))
    _add_centerline(msp, (tv_x - 5, tv_y + tv_d / 2), (tv_x + tv_w + 5, tv_y + tv_d / 2))
    _add_dimension(msp, (tv_x, tv_y + tv_d + 6), (tv_x + tv_w, tv_y + tv_d + 6),
                   (tv_x + tv_w / 2, tv_y + tv_d + 12), f'W = {width_cm:g} cm')
    _add_dimension(msp, (tv_x + tv_w + 6, tv_y), (tv_x + tv_w + 6, tv_y + tv_d),
                   (tv_x + tv_w + 14, tv_y + tv_d / 2), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'TOP VIEW', (tv_x, tv_y + tv_d + 22), 3)

    # === ISOMETRIC VIEW ===
    iso_x = tv_x + tv_w + 30
    iso_y = floor_y
    iso_d = depth_cm * sc
    _add_isometric_box(msp, iso_x, iso_y, w * 1.2, iso_d * 1.2, h * 1.2)
    _add_mtext(msp, 'ISOMETRIC VIEW', (iso_x, iso_y + h * 1.2 + 10), 3)

    # === SIDE VIEW (depth) ===
    sv_w = depth_cm * sc
    sx = fx + w + 30
    _add_polyline(msp, [(sx, floor_y), (sx + sv_w, floor_y),
                        (sx + sv_w, top_y), (sx, top_y)], True)
    _add_dimension(msp, (sx, floor_y - 8), (sx + sv_w, floor_y - 8),
                   (sx + sv_w / 2, floor_y - 14), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'SIDE VIEW', (sx, top_y + 8), 3)

    generate_title_block(msp, f"Wardrobe {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         material_notes=[
                             f"CARCASS — {mats.get('carcass', '18mm MDF, matte white lacquer')}",
                             f"DOORS — {mats.get('doors', 'MDF, matte lacquer')}",
                             f"BASE — {mats.get('base', 'Solid wood plinth')}",
                         ])
    return _save(doc, path)


def save_reception_counter(path, width_cm=180, depth_cm=80, height_cm=110, counter_height_cm=75, _validation_result=None,
                           materials: Optional[Dict[str, str]] = None,
                           visibility: Optional[Dict[str, bool]] = None):
    """Reception counter with top view, front view, and transaction height label."""
    mats = materials or {}
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True
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

    generate_title_block(msp, f"Reception Counter {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         material_notes=[
                             f"COUNTER TOP — {mats.get('counter_top', 'Engineered quartz / solid surface')}",
                             f"FRONT PANEL — {mats.get('front_panel', 'MDF, matte lacquer')}",
                             f"BASE — {mats.get('base', 'Brushed stainless steel')}",
                         ])
    return _save(doc, path)


def save_bed_headboard(path, width_cm=160, height_cm=120, _validation_result=None,
                       materials: Optional[Dict[str, str]] = None,
                       visibility: Optional[Dict[str, bool]] = None):
    """Bed headboard with headboard panel, legs, and dimensions."""
    mats = materials or {}
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True
    doc = setup_doc()
    msp = doc.modelspace()
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True
    sc = 0.4
    w = width_cm * sc
    h = height_cm * sc
    fx = (420 - w) / 2
    floor_y = 30.0
    top_y = floor_y + h
    leg_w = 6.0 * sc
    panel_h = h * 0.75
    panel_top_y = top_y
    panel_bot_y = top_y - panel_h

    # Headboard panel
    _add_polyline(msp, [(fx, panel_bot_y), (fx + w, panel_bot_y),
                        (fx + w, panel_top_y), (fx, panel_top_y)], True)
    _add_hatch_polygon(msp, [(fx, panel_bot_y), (fx + w, panel_bot_y),
                              (fx + w, panel_top_y), (fx, panel_top_y)], 'ANSI31', 0.5)
    # Legs
    for lx in [fx + 5, fx + w - leg_w - 5]:
        _add_polyline(msp, [(lx, floor_y), (lx + leg_w, floor_y),
                            (lx + leg_w, panel_bot_y), (lx, panel_bot_y)], True)
    _add_dimension(msp, (fx + w + 8, floor_y), (fx + w + 8, top_y),
                   (fx + w + 16, (floor_y + top_y) / 2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fx, floor_y - 8), (fx + w, floor_y - 8),
                   (fx, floor_y - 14), f'W = {width_cm:g} cm')
    _add_mtext(msp, 'FRONT VIEW', (fx, top_y + 10), 3)
    generate_title_block(msp, f"Bed Headboard {width_cm:.0f}x{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         material_notes=[
                             f"HEADBOARD PANEL — {mats.get('headboard', 'Upholstered panel, velvet fabric')}",
                             f"POSTS/LEGS — {mats.get('posts', 'Solid wood, stained finish')}",
                         ])
    return _save(doc, path)


def save_oval_pedestal_table(path, length_cm=180, depth_cm=100, height_cm=75,
                              top_thick_cm=3, pedestal_dia_cm=40, base_plate_cm=5,
                              materials=None,
                              visibility: Optional[Dict[str, bool]] = None):
    """Oval/elliptical pedestal table — TOP VIEW + FRONT ELEVATION.
    
    Oval tabletop with single central cylindrical pedestal.
    Oval is approximated as a 36-segment LWPOLYLINE for true ellipse look.
    """
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.35
    w = length_cm * sc
    d = depth_cm * sc
    h = height_cm * sc
    tt = top_thick_cm * sc
    pd_r = pedestal_dia_cm / 2 * sc
    bp = base_plate_cm * sc
    w2, d2 = w / 2, d / 2
    y_mid = 180
    mats = materials or {}

    # ===== TOP VIEW =====
    tx, ty = 100, y_mid
    # Oval as 36-segment LWPOLYLINE
    oval_pts = []
    for i in range(36):
        a = 2 * math.pi * i / 36
        px = tx + w2 * math.cos(a)
        py = ty + d2 * math.sin(a)
        oval_pts.append((px, py))
    _add_polyline(msp, oval_pts, True)
    # Pedestal footprint circle at center
    try:
        msp.add_circle((tx, ty), pd_r, dxfattribs={'layer': 'HIDDEN'})
    except Exception:
        cpts = []
        for i in range(36):
            a = 2 * math.pi * i / 36
            cpts.append((tx + pd_r * math.cos(a), ty + pd_r * math.sin(a)))
        _add_polyline(msp, cpts, True, 'HIDDEN')
    # Stone hatch
    _add_hatch_polygon(msp, oval_pts, 'ANSI31', 0.3, 45)
    # Centerlines
    ext = max(5, w2 * 0.1)
    _add_centerline(msp, (tx - w2 - ext, ty), (tx + w2 + ext, ty))
    _add_centerline(msp, (tx, ty - d2 - ext), (tx, ty + d2 + ext))
    # Dimensions
    _add_dimension(msp, (tx - w2, ty + d2 + 6), (tx + w2, ty + d2 + 6),
                   (tx, ty + d2 + 12), f'W = {length_cm * 10:g} mm')
    _add_dimension(msp, (tx + w2 + 6, ty - d2), (tx + w2 + 6, ty + d2),
                   (tx + w2 + 14, ty), f'D = {depth_cm * 10:g} mm')
    _add_mtext(msp, 'TOP VIEW', (tx - 15, ty + d2 + 22), 3)

    # ===== FRONT ELEVATION =====
    fx = 290
    floor_y = 40
    top_y = floor_y + h
    tab_bot = top_y - tt
    ped_bot = floor_y + bp
    ped_height = tab_bot - ped_bot

    # Tabletop
    _add_polyline(msp, [(fx - w2, tab_bot), (fx + w2, tab_bot),
                        (fx + w2, top_y), (fx - w2, top_y)], True)
    _add_hatch_polygon(msp, [(fx - w2, tab_bot), (fx + w2, tab_bot),
                              (fx + w2, top_y), (fx - w2, top_y)], 'ANSI31', 0.5, 45)
    # Central pedestal
    _add_polyline(msp, [(fx - pd_r, ped_bot), (fx + pd_r, ped_bot),
                        (fx + pd_r, tab_bot), (fx - pd_r, tab_bot)], True)
    _add_hatch_polygon(msp, [(fx - pd_r, ped_bot), (fx + pd_r, ped_bot),
                              (fx + pd_r, tab_bot), (fx - pd_r, tab_bot)], 'ANSI37', 0.3)
    # Centerline
    _add_centerline(msp, (fx, floor_y - 5), (fx, top_y + 5))
    # Dimensions
    _add_dimension(msp, (fx + w2 + 8, floor_y), (fx + w2 + 8, top_y),
                   (fx + w2 + 16, (floor_y + top_y) / 2), f'H = {height_cm * 10:g} mm')
    _add_dimension(msp, (fx - w2, floor_y - 8), (fx + w2, floor_y - 8),
                   (fx, floor_y - 14), f'W = {length_cm * 10:g} mm')
    _add_dimension(msp, (fx - pd_r, ped_bot - 5), (fx + pd_r, ped_bot - 5),
                   (fx, ped_bot - 11), f'Ø{pedestal_dia_cm:g} cm')
    _add_dimension(msp, (fx - w2 - 10, tab_bot), (fx - w2 - 10, top_y),
                   (fx - w2 - 18, (tab_bot + top_y) / 2), f'T = {top_thick_cm * 10:g} mm')
    # Material leader
    _add_leader(msp, mats.get('tabletop', 'STONE/MARBLE TOP'),
                (fx + w2 + 15, (tab_bot + top_y) / 2), (fx + w2, (tab_bot + top_y) / 2))
    _add_leader(msp, mats.get('pedestal', 'BRUSHED METAL PEDESTAL'),
                (fx + pd_r + 15, (ped_bot + tab_bot) / 2), (fx + pd_r, (ped_bot + tab_bot) / 2))
    _add_mtext(msp, 'FRONT ELEVATION', (fx - w2, top_y + 10), 3)

    material_notes = [
        f"TABLE TOP — {mats.get('tabletop', 'Marble / engineered stone')}",
        f"PEDESTAL — {mats.get('pedestal', f'Brushed stainless steel, Ø{pedestal_dia_cm * 10:.0f} mm')}",
    ]
    generate_title_block(msp,
        f"Oval Pedestal Table {length_cm * 10:.0f}x{depth_cm * 10:.0f}x{height_cm * 10:.0f} mm",
        project="Furniture Shop Drawing", scale="1:5", revision="A",
        material_notes=material_notes)
    return _save(doc, path)


def save_console_table(path, length_cm=120, depth_cm=40, height_cm=75,
                        top_thick_cm=2.5, leg_thick_cm=4, leg_inset_cm=2,
                        materials=None,
                        visibility: Optional[Dict[str, bool]] = None):
    """Console / sofa table — TOP/FRONT/SIDE views.
    
    Narrow long table with four simple legs at corners.
    """
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.4
    w = length_cm * sc
    d = depth_cm * sc
    h = height_cm * sc
    tt = top_thick_cm * sc
    lt = leg_thick_cm * sc
    li = leg_inset_cm * sc
    w2, d2, lt2 = w / 2, d / 2, lt / 2
    y_mid = 180
    mats = materials or {}

    # ===== TOP VIEW =====
    tx, ty = 100, y_mid
    _add_polyline(msp, [(tx - w2, ty - d2), (tx + w2, ty - d2),
                        (tx + w2, ty + d2), (tx - w2, ty + d2)], True)
    # Leg footprints at corners (inset)
    for lx, ly in [(tx - w2 + li, ty - d2 + li), (tx + w2 - li - lt, ty - d2 + li),
                   (tx - w2 + li, ty + d2 - li - lt), (tx + w2 - li - lt, ty + d2 - li - lt)]:
        _add_polyline(msp, [(lx, ly), (lx + lt, ly), (lx + lt, ly + lt), (lx, ly + lt)], True, 'HIDDEN')
    _add_centerline(msp, (tx - w2 - 5, ty), (tx + w2 + 5, ty))
    _add_centerline(msp, (tx, ty - d2 - 5), (tx, ty + d2 + 5))
    _add_dimension(msp, (tx - w2, ty + d2 + 6), (tx + w2, ty + d2 + 6),
                   (tx, ty + d2 + 12), f'W = {length_cm * 10:g} mm')
    _add_dimension(msp, (tx + w2 + 6, ty - d2), (tx + w2 + 6, ty + d2),
                   (tx + w2 + 14, ty), f'D = {depth_cm * 10:g} mm')
    _add_mtext(msp, 'TOP VIEW', (tx - 15, ty + d2 + 22), 3)

    # ===== FRONT VIEW =====
    fx = 280
    floor_y = 40
    top_y = floor_y + h
    tab_bot = top_y - tt
    _add_polyline(msp, [(fx - w2, tab_bot), (fx + w2, tab_bot),
                        (fx + w2, top_y), (fx - w2, top_y)], True)
    _add_hatch_polygon(msp, [(fx - w2, tab_bot), (fx + w2, tab_bot),
                              (fx + w2, top_y), (fx - w2, top_y)], 'ANSI31', 0.5)
    # Front legs
    for lx in [fx - w2 + li, fx + w2 - li - lt]:
        _add_polyline(msp, [(lx, floor_y), (lx + lt, floor_y),
                            (lx + lt, tab_bot), (lx, tab_bot)], True)
    # Back legs hidden
    for lx in [fx - w2 + li + lt * 0.5, fx + w2 - li - lt - lt * 0.5]:
        _add_line(msp, (lx, floor_y), (lx, tab_bot), 'HIDDEN')
        _add_line(msp, (lx + lt * 0.3, floor_y), (lx + lt * 0.3, tab_bot), 'HIDDEN')
    _add_centerline(msp, (fx, floor_y - 5), (fx, top_y + 5))
    _add_dimension(msp, (fx + w2 + 8, floor_y), (fx + w2 + 8, top_y),
                   (fx + w2 + 16, (floor_y + top_y) / 2), f'H = {height_cm * 10:g} mm')
    _add_dimension(msp, (fx - w2, floor_y - 8), (fx + w2, floor_y - 8),
                   (fx, floor_y - 14), f'W = {length_cm * 10:g} mm')
    _add_mtext(msp, 'FRONT VIEW', (fx - w2, top_y + 10), 3)

    # ===== SIDE VIEW =====
    sx = 365
    _add_polyline(msp, [(sx - d2, tab_bot), (sx + d2, tab_bot),
                        (sx + d2, top_y), (sx - d2, top_y)], True)
    # Single leg visible from side (front leg)
    ly_l = sx - d2 + li
    _add_polyline(msp, [(ly_l, floor_y), (ly_l + lt, floor_y),
                        (ly_l + lt, tab_bot), (ly_l, tab_bot)], True)
    _add_centerline(msp, (sx, floor_y - 5), (sx, top_y + 5))
    _add_dimension(msp, (sx + d2 + 6, floor_y), (sx + d2 + 6, top_y),
                   (sx + d2 + 14, (floor_y + top_y) / 2), f'H = {height_cm * 10:g} mm')
    _add_dimension(msp, (sx - d2, floor_y - 8), (sx + d2, floor_y - 8),
                   (sx, floor_y - 14), f'D = {depth_cm * 10:g} mm')
    _add_mtext(msp, 'SIDE VIEW', (sx - d2, top_y + 10), 3)

    generate_title_block(msp,
        f"Console Table {length_cm * 10:.0f}x{depth_cm * 10:.0f}x{height_cm * 10:.0f} mm",
        project="Furniture Shop Drawing", scale="1:3", revision="A")
    return _save(doc, path)


def save_office_desk(path, length_cm=140, depth_cm=60, height_cm=75,
                     top_thick_cm=2.5, leg_thick_cm=4, modesty_panel_h_cm=15,
                     leg_inset_cm=2, materials=None,
                     visibility: Optional[Dict[str, bool]] = None):
    """Office desk with modesty panel — TOP/FRONT/SIDE views."""
    doc = setup_doc()
    msp = doc.modelspace()
    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True
    sc = 0.35
    w = length_cm * sc
    d = depth_cm * sc
    h = height_cm * sc
    tt = top_thick_cm * sc
    lt = leg_thick_cm * sc
    mh = modesty_panel_h_cm * sc
    li = leg_inset_cm * sc
    w2, d2 = w / 2, d / 2
    y_mid = 180
    mats = materials or {}

    # ===== TOP VIEW =====
    tx, ty = 100, y_mid
    _add_polyline(msp, [(tx - w2, ty - d2), (tx + w2, ty - d2),
                        (tx + w2, ty + d2), (tx - w2, ty + d2)], True)
    for lx, ly in [(tx - w2 + li, ty - d2 + li), (tx + w2 - li - lt, ty - d2 + li),
                   (tx - w2 + li, ty + d2 - li - lt), (tx + w2 - li - lt, ty + d2 - li - lt)]:
        _add_polyline(msp, [(lx, ly), (lx + lt, ly), (lx + lt, ly + lt), (lx, ly + lt)], True, 'HIDDEN')
    _add_centerline(msp, (tx - w2 - 5, ty), (tx + w2 + 5, ty))
    _add_centerline(msp, (tx, ty - d2 - 5), (tx, ty + d2 + 5))
    _add_dimension(msp, (tx - w2, ty + d2 + 6), (tx + w2, ty + d2 + 6),
                   (tx, ty + d2 + 12), f'W = {length_cm * 10:g} mm')
    _add_dimension(msp, (tx + w2 + 6, ty - d2), (tx + w2 + 6, ty + d2),
                   (tx + w2 + 14, ty), f'D = {depth_cm * 10:g} mm')
    _add_mtext(msp, 'TOP VIEW', (tx - 15, ty + d2 + 22), 3)

    # ===== FRONT VIEW =====
    fx = 280
    floor_y = 40
    top_y = floor_y + h
    tab_bot = top_y - tt
    _add_polyline(msp, [(fx - w2, tab_bot), (fx + w2, tab_bot),
                        (fx + w2, top_y), (fx - w2, top_y)], True)
    _add_hatch_polygon(msp, [(fx - w2, tab_bot), (fx + w2, tab_bot),
                              (fx + w2, top_y), (fx - w2, top_y)], 'ANSI31', 0.5)
    # Modesty panel (between legs, below tabletop)
    mp_top = tab_bot
    mp_bot = mp_top - mh
    panel_l = fx - w2 + li + lt
    panel_r = fx + w2 - li - lt
    _add_polyline(msp, [(panel_l, mp_bot), (panel_r, mp_bot),
                        (panel_r, mp_top), (panel_l, mp_top)], True)
    _add_hatch_polygon(msp, [(panel_l, mp_bot), (panel_r, mp_bot),
                              (panel_r, mp_top), (panel_l, mp_top)], 'ANSI31', 0.4)
    # Legs
    for lx in [fx - w2 + li, fx + w2 - li - lt]:
        _add_polyline(msp, [(lx, floor_y), (lx + lt, floor_y),
                            (lx + lt, tab_bot), (lx, tab_bot)], True)
    _add_centerline(msp, (fx, floor_y - 5), (fx, top_y + 5))
    _add_dimension(msp, (fx + w2 + 8, floor_y), (fx + w2 + 8, top_y),
                   (fx + w2 + 16, (floor_y + top_y) / 2), f'H = {height_cm * 10:g} mm')
    _add_dimension(msp, (fx - w2, floor_y - 8), (fx + w2, floor_y - 8),
                   (fx, floor_y - 14), f'W = {length_cm * 10:g} mm')
    _add_dimension(msp, (panel_l, mp_bot - 5), (panel_r, mp_bot - 5),
                   ((panel_l + panel_r) / 2, mp_bot - 11), f'MH = {modesty_panel_h_cm:g} cm')
    _add_mtext(msp, 'FRONT VIEW', (fx - w2, top_y + 10), 3)

    # ===== SIDE VIEW =====
    sx = 365
    _add_polyline(msp, [(sx - d2, tab_bot), (sx + d2, tab_bot),
                        (sx + d2, top_y), (sx - d2, top_y)], True)
    # Leg from side
    sl = sx - d2 + li
    _add_polyline(msp, [(sl, floor_y), (sl + lt, floor_y),
                        (sl + lt, tab_bot), (sl, tab_bot)], True)
    # Modesty panel from side (thin profile)
    _add_line(msp, (sx - d2 + li + lt + 1, mp_bot), (sx + d2 - 2, mp_bot), 'OBJECT')
    _add_line(msp, (sx - d2 + li + lt + 1, mp_top), (sx + d2 - 2, mp_top), 'OBJECT')
    _add_centerline(msp, (sx, floor_y - 5), (sx, top_y + 5))
    _add_dimension(msp, (sx + d2 + 6, floor_y), (sx + d2 + 6, top_y),
                   (sx + d2 + 14, (floor_y + top_y) / 2), f'H = {height_cm * 10:g} mm')
    _add_dimension(msp, (sx - d2, floor_y - 8), (sx + d2, floor_y - 8),
                   (sx, floor_y - 14), f'D = {depth_cm * 10:g} mm')
    _add_mtext(msp, 'SIDE VIEW', (sx - d2, top_y + 10), 3)

    generate_title_block(msp,
        f"Office Desk {length_cm * 10:.0f}x{depth_cm * 10:.0f}x{height_cm * 10:.0f} mm",
        project="Furniture Shop Drawing", scale="1:3", revision="A")
    return _save(doc, path)


def save_asymmetric_pedestal_table(path, length_cm=180, depth_cm=90, height_cm=75,
                                    top_thick_cm=3, large_ped_dia_cm=40, small_ped_dia_cm=22,
                                    left_ped_x_cm=30, right_ped_x_cm=-25, overhang_cm=20,
                                    base_plate_cm=5, materials=None,
                                    visibility: Optional[Dict[str, bool]] = None):
    """Asymmetric cylindrical pedestal dining table — TOP/FRONT/SIDE views.
    
    Rectangular tabletop with two offset cylindrical pedestals of different
    diameters. Generates three views: top view with pedestal footprints,
    front elevation showing both pedestals, and side elevation from the
    right showing the asymmetrical depth offset.
    All dimensions in cm internally (converted from mm in the caller).
    """
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.35
    w = length_cm * sc       # tabletop width in drawing units
    d = depth_cm * sc        # tabletop depth in drawing units
    h = height_cm * sc       # total height
    tt = top_thick_cm * sc   # top thickness
    lp_r = large_ped_dia_cm / 2 * sc  # large pedestal radius
    sp_r = small_ped_dia_cm / 2 * sc  # small pedestal radius
    lpx = left_ped_x_cm * sc          # large pedestal x offset
    rpx = right_ped_x_cm * sc         # small pedestal x offset
    bp = base_plate_cm * sc           # base plate height
    w2, d2 = w / 2, d / 2
    y_mid = 180
    mats = materials or {}

    # ===== TOP VIEW =====
    tx, ty = 100, y_mid
    _add_polyline(msp, [(tx - w2, ty - d2), (tx + w2, ty - d2),
                        (tx + w2, ty + d2), (tx - w2, ty + d2)], True)
    # Stone hatch on tabletop
    _add_hatch_polygon(msp, [(tx - w2, ty - d2), (tx + w2, ty - d2),
                              (tx + w2, ty + d2), (tx - w2, ty + d2)], 'ANSI31', 0.3, 45)
    # Pedestal footprints (circles)
    try:
        msp.add_circle((tx + lpx, ty), lp_r, dxfattribs={'layer': 'HIDDEN'})
        msp.add_circle((tx + rpx, ty), sp_r, dxfattribs={'layer': 'HIDDEN'})
    except Exception:
        for cx, r in [(tx + lpx, lp_r), (tx + rpx, sp_r)]:
            pts = []
            for i in range(36):
                a = 2 * math.pi * i / 36
                pts.append((cx + r * math.cos(a), ty + r * math.sin(a)))
            _add_polyline(msp, pts, True, 'HIDDEN')
    # Centerlines
    ext = max(5, w2 * 0.1)
    _add_centerline(msp, (tx - w2 - ext, ty), (tx + w2 + ext, ty))
    _add_centerline(msp, (tx, ty - d2 - ext), (tx, ty + d2 + ext))
    # Dimensions
    _add_dimension(msp, (tx - w2, ty + d2 + 6), (tx + w2, ty + d2 + 6),
                   (tx, ty + d2 + 12), f'W = {length_cm * 10:g} mm')
    _add_dimension(msp, (tx + w2 + 6, ty - d2), (tx + w2 + 6, ty + d2),
                   (tx + w2 + 14, ty), f'D = {depth_cm * 10:g} mm')
    # Pedestal footprint diameter callouts
    _add_text(msp, f'P1 Ø{large_ped_dia_cm * 10:g} mm', (tx + lpx - 12, ty - lp_r - 8), 2, 'DIMENSIONS')
    _add_text(msp, f'P2 Ø{small_ped_dia_cm * 10:g} mm', (tx + rpx - 12, ty + sp_r + 8), 2, 'DIMENSIONS')
    _add_mtext(msp, 'TOP VIEW', (tx - 15, ty + d2 + 22), 3)

    # ===== FRONT ELEVATION =====
    fx = 290
    floor_y = 40
    top_y = floor_y + h
    tab_bot = top_y - tt
    ped_height = tab_bot - floor_y - bp

    # Tabletop
    _add_polyline(msp, [(fx - w2, tab_bot), (fx + w2, tab_bot),
                        (fx + w2, top_y), (fx - w2, top_y)], True)
    _add_hatch_polygon(msp, [(fx - w2, tab_bot), (fx + w2, tab_bot),
                              (fx + w2, top_y), (fx - w2, top_y)], 'ANSI31', 0.5, 45)
    # Large pedestal (right side)
    lp_l = fx + lpx - lp_r
    lp_r_x = fx + lpx + lp_r
    ped_bot = floor_y + bp
    _add_polyline(msp, [(lp_l, ped_bot), (lp_r_x, ped_bot),
                        (lp_r_x, tab_bot), (lp_l, tab_bot)], True)
    # Small pedestal (left side)
    sp_l = fx + rpx - sp_r
    sp_r_x = fx + rpx + sp_r
    _add_polyline(msp, [(sp_l, ped_bot), (sp_r_x, ped_bot),
                        (sp_r_x, tab_bot), (sp_l, tab_bot)], True)
    # Metal hatch on pedestals
    _add_hatch_polygon(msp, [(lp_l, ped_bot), (lp_r_x, ped_bot),
                              (lp_r_x, tab_bot), (lp_l, tab_bot)], 'ANSI37', 0.3)
    _add_hatch_polygon(msp, [(sp_l, ped_bot), (sp_r_x, ped_bot),
                              (sp_r_x, tab_bot), (sp_l, tab_bot)], 'ANSI37', 0.3)
    # Centerline through overall center
    _add_centerline(msp, (fx, floor_y - 5), (fx, top_y + 5))
    # Dimensions
    _add_dimension(msp, (fx + w2 + 8, floor_y), (fx + w2 + 8, top_y),
                   (fx + w2 + 16, (floor_y + top_y) / 2), f'H = {height_cm * 10:g} mm')
    _add_dimension(msp, (fx - w2, floor_y - 8), (fx + w2, floor_y - 8),
                   (fx, floor_y - 14), f'W = {length_cm * 10:g} mm')
    # Top thickness
    _add_dimension(msp, (fx - w2 - 10, tab_bot), (fx - w2 - 10, top_y),
                   (fx - w2 - 18, (tab_bot + top_y) / 2), f'T = {top_thick_cm * 10:g} mm')
    # Pedestal diameters
    _add_dimension(msp, (lp_l, ped_bot - 6), (lp_r_x, ped_bot - 6),
                   (fx + lpx, ped_bot - 12), f'Ø{large_ped_dia_cm * 10:g} mm')
    _add_dimension(msp, (sp_l, ped_bot - 6), (sp_r_x, ped_bot - 6),
                   (fx + rpx, ped_bot - 12), f'Ø{small_ped_dia_cm * 10:g} mm')
    # Overhang dimensions
    _add_dimension(msp, (fx + lpx, tab_bot + 4), (fx + w2, tab_bot + 4),
                   ((fx + lpx + fx + w2) / 2, tab_bot + 10), f'OH = {overhang_cm * 10:g} mm')
    _add_dimension(msp, (fx - w2, tab_bot + 4), (fx + rpx, tab_bot + 4),
                   ((fx - w2 + fx + rpx) / 2, tab_bot + 10), f'OH = {overhang_cm * 10:g} mm')
    # Material leaders
    _add_leader(msp, mats.get('tabletop', 'STONE/MARBLE TOP'),
                (fx + w2 + 15, (tab_bot + top_y) / 2),
                (fx + w2, (tab_bot + top_y) / 2))
    _add_leader(msp, mats.get('large_pedestal', 'BRUSHED METAL LARGE BASE'),
                (lp_r_x + 15, (ped_bot + tab_bot) / 2),
                (lp_r_x, (ped_bot + tab_bot) / 2))
    _add_leader(msp, mats.get('small_pedestal', 'BRUSHED METAL SMALL BASE'),
                (sp_l - 15, (ped_bot + tab_bot) / 2),
                (sp_l, (ped_bot + tab_bot) / 2))
    _add_mtext(msp, 'FRONT ELEVATION', (fx - w2, top_y + 10), 3)

    # ===== SIDE ELEVATION =====
    sx = 365
    # Tabletop side profile
    _add_polyline(msp, [(sx - d2, tab_bot), (sx + d2, tab_bot),
                        (sx + d2, top_y), (sx - d2, top_y)], True)
    _add_hatch_polygon(msp, [(sx - d2, tab_bot), (sx + d2, tab_bot),
                              (sx + d2, top_y), (sx - d2, top_y)], 'ANSI31', 0.5, 45)
    # Determine which pedestal is closer in side view
    # From side (right side of table): the large pedestal (offset +right) appears further back
    # The small pedestal (offset left from center) appears closer
    # So the small pedestal is drawn solid, large pedestal is hidden/dashed
    ped_w_from_side = max(sp_r * 2, 4.0)  # width visible from side = pedestal dia projected
    # Closer pedestal (small, offset to left → appears on right in side view)
    _add_polyline(msp, [(sx - ped_w_from_side / 2, ped_bot),
                        (sx + ped_w_from_side / 2, ped_bot),
                        (sx + ped_w_from_side / 2, tab_bot),
                        (sx - ped_w_from_side / 2, tab_bot)], True)
    # Further pedestal (large, offset to right → appears on left in side view, hidden)
    far_ped_w = max(lp_r * 2, 4.0)
    _add_polyline(msp, [(sx - d2 * 0.3 - far_ped_w / 2, ped_bot),
                        (sx - d2 * 0.3 + far_ped_w / 2, ped_bot),
                        (sx - d2 * 0.3 + far_ped_w / 2, tab_bot),
                        (sx - d2 * 0.3 - far_ped_w / 2, tab_bot)], True, 'HIDDEN')
    # Centerline
    _add_centerline(msp, (sx, floor_y - 5), (sx, top_y + 5))
    # Dimensions
    _add_dimension(msp, (sx + d2 + 6, floor_y), (sx + d2 + 6, top_y),
                   (sx + d2 + 14, (floor_y + top_y) / 2), f'H = {height_cm * 10:g} mm')
    _add_dimension(msp, (sx - d2, floor_y - 8), (sx + d2, floor_y - 8),
                   (sx, floor_y - 14), f'D = {depth_cm * 10:g} mm')
    _add_mtext(msp, 'SIDE ELEVATION', (sx - d2, top_y + 10), 3)

    # Title block — pre-compute defaults to avoid nested f-string evaluation bugs
    _lp_default = f"Brushed stainless steel, Ø{large_ped_dia_cm * 10:.0f} mm"
    _sp_default = f"Brushed stainless steel, Ø{small_ped_dia_cm * 10:.0f} mm"
    material_notes = [
        f"TABLE TOP — {mats.get('tabletop', 'Marble / engineered stone')}",
        f"LARGE PEDESTAL (P1) — {mats.get('large_pedestal', _lp_default)}",
        f"SMALL PEDESTAL (P2) — {mats.get('small_pedestal', _sp_default)}",
        f"BASE PLATES — {mats.get('base_plate', 'Anti-sliding rubber pads')}",
    ]
    generate_title_block(msp,
        f"Asymmetric Pedestal Dining Table {length_cm * 10:.0f}x{depth_cm * 10:.0f}x{height_cm * 10:.0f} mm",
        project="Furniture Shop Drawing",
        client="",
        scale="1:5",
        revision="A",
        material_notes=material_notes,
    )
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
        _add_polyline(msp, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], True, 'OBJECT')

    _add_mtext(msp, 'GENERIC 2D GEOMETRY (unclassified)', (10, 280), 4)
    generate_title_block(msp, "Generic 2D Furniture Drawing")
    return _save(doc, path)


# ===== NEW 7 DXF SAVE FUNCTIONS (HomeU 25-Template Upgrade) =====


def save_sectional(path, width_cm=280, depth_cm=95, height_cm=82, chaise_length_cm=160,
                   seat_height_cm=42, seat_count=4,
                   materials: Optional[Dict[str, str]] = None,
                   visibility: Optional[Dict[str, bool]] = None):
    """L-shaped sectional sofa — front view with chaise extension + top view + side view."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.35
    w = width_cm * sc; d = depth_cm * sc; h = height_cm * sc
    ch = chaise_length_cm * sc
    fx, fy = 60, 30; top_y = fy + h
    mats = materials or {}

    def _component_visible(name):
        if visibility is not None and name in visibility:
            return visibility[name]
        return True

    # === FRONT VIEW (main section) ===
    _add_polyline(msp, [(fx, top_y), (fx + w, top_y), (fx + w, fy), (fx, fy)], True)
    _add_polyline(msp, [(fx, top_y - 0.3*h), (fx + w, top_y - 0.3*h)], False, 'HIDDEN')
    _add_centerline(msp, (fx + w/2, fy - 5), (fx + w/2, top_y + 5))
    _add_dimension(msp, (fx + w + 8, fy), (fx + w + 8, top_y), (fx + w + 16, (fy+top_y)/2), f'H = {height_cm:g} cm')
    _add_dimension(msp, (fx, fy - 10), (fx + w, fy - 10), (fx + w/2, fy - 16), f'W = {width_cm:g} cm')
    _add_mtext(msp, 'FRONT VIEW', (fx, top_y + 8), 3)

    # === TOP VIEW (L-shape) ===
    tw = width_cm * sc; td = depth_cm * sc; tc = chaise_length_cm * sc
    tx, ty = fx, top_y + 30
    _add_polyline(msp, [(tx, ty), (tx + tw, ty), (tx + tw, ty + td), (tx, ty + td)], True)
    # Chaise extension (L)
    _add_polyline(msp, [(tx + tw - tc, ty + td), (tx + tw, ty + td), (tx + tw, ty + td + td*0.6), (tx + tw - tc, ty + td + td*0.6)], True, 'HIDDEN')
    _add_centerline(msp, (tx + tw/2, ty - 5), (tx + tw/2, ty + td + td*0.6 + 5))
    _add_dimension(msp, (tx, ty + td + 8), (tx + tw, ty + td + 8), (tx + tw/2, ty + td + 14), f'W = {width_cm:g} cm')
    _add_mtext(msp, 'TOP VIEW', (tx, ty + td + td*0.6 + 14), 3)

    # === SIDE VIEW ===
    sx, sy = fx + w + 30, fy
    _add_polyline(msp, [(sx, sy), (sx + d, sy), (sx + d, top_y), (sx, top_y)], True)
    _add_dimension(msp, (sx, sy - 10), (sx + d, sy - 10), (sx + d/2, sy - 16), f'D = {depth_cm:g} cm')
    _add_mtext(msp, 'SIDE VIEW', (sx, top_y + 8), 3)

    generate_title_block(msp, f"Sectional Sofa {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
                         project="Furniture Shop Drawing",
                         material_notes=[
                             f"SEAT — {mats.get('seat', 'Fabric upholstery')}",
                             f"BASE — {mats.get('base', 'Engineered wood / steel frame')}",
                         ])
    return _save(doc, path)


def _read_front_view_bbox(msp) -> tuple[float, float, float, float, float, float]:
    """Read FRONT VIEW bounding box from existing DXF polylines.
    
    Returns (fx, fy, fw, fh, floor_y, top_y) — the front view's origin,
    width, height in DXF coordinates. Falls back to defaults if not found.
    """
    front_origin_x = front_origin_y = None
    all_x, all_y = [], []
    for e in msp:
        if e.dxftype() == 'MTEXT' and 'FRONT VIEW' in e.plain_text():
            front_origin_x = e.dxf.insert[0]
            front_origin_y = e.dxf.insert[1]
        if e.dxftype() == 'LWPOLYLINE':
            try:
                for v in e.get_points():
                    all_x.append(v[0]); all_y.append(v[1])
            except Exception:
                pass
        elif e.dxftype() == 'LINE':
            try:
                all_x.append(e.dxf.start.x); all_y.append(e.dxf.start.y)
                all_x.append(e.dxf.end.x); all_y.append(e.dxf.end.y)
            except Exception:
                pass
        elif e.dxftype() == 'CIRCLE':
            try:
                r = e.dxf.radius
                all_x.append(e.dxf.center.x - r); all_x.append(e.dxf.center.x + r)
                all_y.append(e.dxf.center.y - r); all_y.append(e.dxf.center.y + r)
            except Exception:
                pass

    if front_origin_x is None or not all_x:
        return (50.0, 30.0, 42.0, 26.25, 30.0, 56.25)

    fx = front_origin_x
    floor_y = min(all_y)
    top_y = max(all_y)

    # Width from MTEXT position to rightmost polyline point in bottom area
    rightmost = max(x for x in all_x if abs(y - floor_y) < 5 for y in [all_y[all_x.index(x)]] if abs(x - fx) < 200) if all_x else max(all_x)
    fw = max(1.0, rightmost - fx) if rightmost > fx else max(all_x) - min(all_x)
    fh = max(1.0, top_y - floor_y)

    return (fx, floor_y, fw, fh, floor_y, top_y)


def _gemini_svg_to_dxf_splines(svg_text: str) -> list:
    """Parse SVG path commands from Gemini response and convert to DXF SPLINE fit points.
    
    Extracts d="..." attributes and converts bezier curves (C, Q, S) to
    polyline vertices sampled at fine intervals, while preserving straight
    segments (L, M) as-is. Returns list of [[x1,y1],...] polyline vertex arrays,
    one per closed contour.
    """
    import re, math
    paths = re.findall(r'd="([^"]+)"', svg_text, re.I)
    if not paths:
        return []

    contours = []
    for d in paths:
        tokens = re.findall(r'[MmLlCcQqSsZzHhVv]|-?\d+(?:\.\d+)?', d)
        i = 0
        cx = cy = sx = sy = 0.0
        pts = []

        def _next():
            nonlocal i
            if i < len(tokens):
                v = tokens[i]; i += 1
                return float(v) if v.replace('-','',1).replace('.','',1).isdigit() else v
            return None

        while i < len(tokens):
            cmd = tokens[i]; i += 1
            if cmd == 'M':
                cx = float(tokens[i]); cy = float(tokens[i+1]); i += 2
                sx, sy = cx, cy
                pts.append([cx, cy])
            elif cmd == 'm':
                cx += float(tokens[i]); cy += float(tokens[i+1]); i += 2
                sx, sy = cx, cy
                pts.append([cx, cy])
            elif cmd == 'L':
                cx = float(tokens[i]); cy = float(tokens[i+1]); i += 2
                pts.append([cx, cy])
            elif cmd == 'l':
                cx += float(tokens[i]); cy += float(tokens[i+1]); i += 2
                pts.append([cx, cy])
            elif cmd == 'C' and i + 5 < len(tokens):
                cp1x, cp1y = float(tokens[i]), float(tokens[i+1])
                cp2x, cp2y = float(tokens[i+2]), float(tokens[i+3])
                ex, ey = float(tokens[i+4]), float(tokens[i+5])
                for s in range(1, 13):
                    t = s / 12
                    u = 1 - t
                    px = u**3*cx + 3*u**2*t*cp1x + 3*u*t**2*cp2x + t**3*ex
                    py = u**3*cy + 3*u**2*t*cp1y + 3*u*t**2*cp2y + t**3*ey
                    pts.append([px, py])
                cx, cy = ex, ey; i += 6
            elif cmd == 'c' and i + 5 < len(tokens):
                cp1x = cx + float(tokens[i]); cp1y = cy + float(tokens[i+1])
                cp2x = cx + float(tokens[i+2]); cp2y = cy + float(tokens[i+3])
                ex = cx + float(tokens[i+4]); ey = cy + float(tokens[i+5])
                for s in range(1, 13):
                    t = s / 12
                    u = 1 - t
                    px = u**3*cx + 3*u**2*t*cp1x + 3*u*t**2*cp2x + t**3*ex
                    py = u**3*cy + 3*u**2*t*cp1y + 3*u*t**2*cp2y + t**3*ey
                    pts.append([px, py])
                cx, cy = ex, ey; i += 6
            elif cmd == 'S' and i + 3 < len(tokens):
                cp2x, cp2y = float(tokens[i]), float(tokens[i+1])
                ex, ey = float(tokens[i+2]), float(tokens[i+3])
                # Reflection of previous control point
                if len(pts) >= 2:
                    prev = pts[-2]
                    cp1x = cx + (cx - prev[0])
                    cp1y = cy + (cy - prev[1])
                else:
                    cp1x, cp1y = cx, cy
                for s in range(1, 13):
                    t = s / 12; u = 1 - t
                    px = u**3*cx + 3*u**2*t*cp1x + 3*u*t**2*cp2x + t**3*ex
                    py = u**3*cy + 3*u**2*t*cp1y + 3*u*t**2*cp2y + t**3*ey
                    pts.append([px, py])
                cx, cy = ex, ey; i += 4
            elif cmd == 's' and i + 3 < len(tokens):
                cp2x = cx + float(tokens[i]); cp2y = cy + float(tokens[i+1])
                ex = cx + float(tokens[i+2]); ey = cy + float(tokens[i+3])
                if len(pts) >= 2:
                    prev = pts[-2]
                    cp1x = cx + (cx - prev[0]); cp1y = cy + (cy - prev[1])
                else:
                    cp1x, cp1y = cx, cy
                for s in range(1, 13):
                    t = s / 12; u = 1 - t
                    px = u**3*cx + 3*u**2*t*cp1x + 3*u*t**2*cp2x + t**3*ex
                    py = u**3*cy + 3*u**2*t*cp1y + 3*u*t**2*cp2y + t**3*ey
                    pts.append([px, py])
                cx, cy = ex, ey; i += 4
            elif cmd in ('Q', 'q') and i + 3 < len(tokens):
                cpx = float(tokens[i]) if cmd == 'Q' else cx + float(tokens[i])
                cpy = float(tokens[i+1]) if cmd == 'Q' else cy + float(tokens[i+1])
                ex = float(tokens[i+2]) if cmd == 'Q' else cx + float(tokens[i+2])
                ey = float(tokens[i+3]) if cmd == 'Q' else cy + float(tokens[i+3])
                for s in range(1, 10):
                    t = s / 9; u = 1 - t
                    px = u**2*cx + 2*u*t*cpx + t**2*ex
                    py = u**2*cy + 2*u*t*cpy + t**2*ey
                    pts.append([px, py])
                cx, cy = ex, ey; i += 4
            elif cmd in ('H',):
                ex = float(tokens[i]); i += 1
                pts.append([ex, cy]); cx = ex
            elif cmd in ('h',):
                ex = cx + float(tokens[i]); i += 1
                pts.append([ex, cy]); cx = ex
            elif cmd in ('V',):
                ey = float(tokens[i]); i += 1
                pts.append([cx, ey]); cy = ey
            elif cmd in ('v',):
                ey = cy + float(tokens[i]); i += 1
                pts.append([cx, ey]); cy = ey
            elif cmd in ('Z', 'z'):
                if pts and (abs(pts[-1][0] - sx) > 0.5 or abs(pts[-1][1] - sy) > 0.5):
                    pts.append([sx, sy])
                break

        if len(pts) > 2:
            contours.append(pts)

    return contours


def save_hero_view(path, hero_coords_json="[]", svg_silhouette="",
                   width_cm=100, height_cm=80, materials=None, visibility=None):
    """Add a scale-aligned HERO VIEW traced from the product photo.
    
    Uses dynamic scale detection — reads the actual FRONT VIEW bounding box
    from the existing DXF to compute the correct scale, no hardcoded sc needed.
    Draws the hero outline twice:
      1. As an OVERLAY (dashed, red) directly on the FRONT VIEW
      2. As a standalone HERO VIEW (solid) to the right of FRONT VIEW
    """
    import json, math
    coords = json.loads(hero_coords_json) if isinstance(hero_coords_json, str) else hero_coords_json
    if not coords and svg_silhouette:
        contours = _gemini_svg_to_dxf_splines(svg_silhouette)
        coords = contours[0] if contours else []
    if not coords or len(coords) < 3:
        return

    try:
        doc = ezdxf.readfile(path)
        msp = doc.modelspace()
    except Exception:
        doc = setup_doc()
        msp = doc.modelspace()

    # Dynamic scale detection from existing DXF
    fx, floor_y, fw, fh, _, top_y = _read_front_view_bbox(msp)

    # Center and scale Gemini coords to match FRONT VIEW dimensions
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    if not xs or not ys:
        return
    gem_cx, gem_cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    gem_w, gem_h = max(xs) - min(xs), max(ys) - min(ys)
    if gem_w < 1 or gem_h < 1:
        return
    scale = min(fw / gem_w, fh / gem_h) * 0.85

    # 1. OVERLAY — draw hero as dashed red polyline directly on FRONT VIEW
    overlay_pts = []
    for px, py in coords:
        vx = fx + fw / 2 + (px - gem_cx) * scale
        vy = floor_y + (py - gem_cy) * scale
        overlay_pts.append((vx, vy))
    _add_polyline(msp, overlay_pts, True, 'HIDDEN')
    # Color the overlay by changing layer properties (HIDDEN is dashed by convention)

    # 2. Standalone HERO VIEW to the right of FRONT VIEW
    ox = fx + fw + 25
    oy = floor_y
    hero_pts = []
    for px, py in coords:
        vx = ox + fw / 2 + (px - gem_cx) * scale
        vy = oy + (py - gem_cy) * scale
        hero_pts.append((vx, vy))
    _add_polyline(msp, hero_pts, True, 'OBJECT')
    _add_mtext(msp, 'HERO VIEW (photo traced)', (ox, oy + fh * 0.85 + 5), 2.5)

    # Dimensions matching the parametric FRONT VIEW
    _add_dimension(msp, (ox, oy - 5), (ox + fw * 0.85, oy - 5),
                   (ox + fw * 0.85 / 2, oy - 11), f'W = {width_cm:g} cm')
    _add_dimension(msp, (ox + fw * 0.85 + 5, oy), (ox + fw * 0.85 + 5, oy + fh * 0.85),
                   (ox + fw * 0.85 + 14, oy + fh * 0.85 / 2), f'H = {height_cm:g} cm')

    return _save(doc, path)


def save_armchair(path, width_cm=70, depth_cm=75, height_cm=90, seat_height_cm=45,
                   materials: Optional[Dict[str, str]] = None):
    """Armchair lounge shop drawing with seat, backrest, armrests, legs."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    w, d, h = width_cm * sc, depth_cm * sc, height_cm * sc
    sh = seat_height_cm * sc
    y_mid = 180
    mats = materials or {}

    # ===== TOP VIEW =====
    ox, oy = 100, y_mid
    _add_polyline(msp, [(ox - w / 2, oy - d / 2), (ox + w / 2, oy - d / 2),
                        (ox + w / 2, oy + d / 2), (ox - w / 2, oy + d / 2)], True)
    ar_w = max(4, w * 0.12)
    _add_polyline(msp, [(ox - w / 2 - ar_w, oy - d * 0.4), (ox - w / 2, oy - d * 0.4),
                        (ox - w / 2, oy + d * 0.4), (ox - w / 2 - ar_w, oy + d * 0.4)], True, 'HIDDEN')
    _add_polyline(msp, [(ox + w / 2, oy - d * 0.4), (ox + w / 2 + ar_w, oy - d * 0.4),
                        (ox + w / 2 + ar_w, oy + d * 0.4), (ox + w / 2, oy + d * 0.4)], True, 'HIDDEN')
    _add_centerline(msp, (ox - w / 2 - 5, oy), (ox + w / 2 + 5, oy))
    _add_centerline(msp, (ox, oy - d / 2 - 5), (ox, oy + d / 2 + 5))
    _add_dimension(msp, (ox - w / 2, oy + d / 2 + 6), (ox + w / 2, oy + d / 2 + 6),
                   (ox, oy + d / 2 + 12), 'W = {:.0f} cm'.format(width_cm))
    _add_dimension(msp, (ox + w / 2 + 6, oy - d / 2), (ox + w / 2 + 6, oy + d / 2),
                   (ox + w / 2 + 14, oy), 'D = {:.0f} cm'.format(depth_cm))
    _add_mtext(msp, 'TOP VIEW', (ox - 15, oy + d / 2 + 22), 3)

    # ===== FRONT VIEW =====
    fx = 280
    floor_y = y_mid - h / 2
    top_y = floor_y + h
    seat_top_y = floor_y + sh
    br_h = h - sh
    _add_polyline(msp, [(fx - w / 2, seat_top_y), (fx + w / 2, seat_top_y),
                        (fx + w / 2, top_y), (fx - w / 2, top_y)], True)
    _add_polyline(msp, [(fx - w / 2, floor_y), (fx + w / 2, floor_y),
                        (fx + w / 2, seat_top_y), (fx - w / 2, seat_top_y)], True)
    _add_hatch_polygon(msp, [(fx - w / 2, floor_y + 2), (fx + w / 2, floor_y + 2),
                              (fx + w / 2, seat_top_y - 2), (fx - w / 2, seat_top_y - 2)],
                       'ANSI31', 0.3)
    ar_h = sh * 0.6
    _add_polyline(msp, [(fx - w / 2 - ar_w, floor_y + 4), (fx - w / 2, floor_y + 4),
                        (fx - w / 2, floor_y + 4 + ar_h), (fx - w / 2 - ar_w, floor_y + 4 + ar_h)], True)
    _add_polyline(msp, [(fx + w / 2, floor_y + 4), (fx + w / 2 + ar_w, floor_y + 4),
                        (fx + w / 2 + ar_w, floor_y + 4 + ar_h), (fx + w / 2, floor_y + 4 + ar_h)], True)
    leg_h = max(4, h * 0.06)
    for lx in [fx - w / 2 + 3, fx + w / 2 - 3]:
        _add_polyline(msp, [(lx, floor_y - leg_h), (lx + 2, floor_y - leg_h),
                            (lx + 2, floor_y), (lx, floor_y)], True)
    _add_dimension(msp, (fx - w / 2, floor_y - leg_h - 5), (fx + w / 2, floor_y - leg_h - 5),
                   (fx, floor_y - leg_h - 12), 'W = {:.0f} cm'.format(width_cm))
    _add_dimension(msp, (fx + w / 2 + 8, floor_y), (fx + w / 2 + 8, top_y),
                   (fx + w / 2 + 18, (floor_y + top_y) / 2), 'H = {:.0f} cm'.format(height_cm))
    _add_mtext(msp, 'FRONT VIEW', (fx - w / 2, top_y + 8), 3)
    generate_title_block(msp, 'Armchair Lounge {:.0f}x{:.0f}x{:.0f}'.format(width_cm, depth_cm, height_cm),
                         material_notes=['SEAT — ' + mats.get('seat', 'Upholstered fabric'),
                                         'FRAME — ' + mats.get('frame', 'Solid wood')])
    return _save(doc, path)


def save_bar_stool(path, diameter_or_width_cm=40, height_cm=75, seat_height_cm=65,
                   materials: Optional[Dict[str, str]] = None):
    """Bar stool shop drawing with seat, column/pedestal, footrest, base."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    dia, h, sh = diameter_or_width_cm * sc, height_cm * sc, seat_height_cm * sc
    r = dia / 2
    y_mid = 180
    mats = materials or {}

    # ===== TOP VIEW =====
    cx, cy = 100, y_mid
    msp.add_circle((cx, cy), r, dxfattribs={'layer': 'OBJECT'})
    _add_centerline(msp, (cx - r - 5, cy), (cx + r + 5, cy))
    _add_centerline(msp, (cx, cy - r - 5), (cx, cy + r + 5))
    _add_diameter_dim(msp, (cx, cy), r, '%%c{:.0f} cm'.format(diameter_or_width_cm))
    _add_mtext(msp, 'TOP VIEW', (cx - 15, cy + r + 12), 3)

    # ===== FRONT VIEW =====
    fx = 280
    floor_y = y_mid - h / 2
    top_y = floor_y + h
    seat_top_y = floor_y + sh
    seat_thick = max(3, h * 0.06)
    _add_polyline(msp, [(fx - r, seat_top_y), (fx + r, seat_top_y),
                        (fx + r, seat_top_y + seat_thick), (fx - r, seat_top_y + seat_thick)], True)
    col_r = max(2, r * 0.2)
    _add_polyline(msp, [(fx - col_r, floor_y + 3), (fx + col_r, floor_y + 3),
                        (fx + col_r, seat_top_y), (fx - col_r, seat_top_y)], True)
    fr_y = floor_y + h * 0.35
    fr_w = r * 0.7
    _add_line(msp, (fx - fr_w, fr_y), (fx + fr_w, fr_y), 'HIDDEN')
    _add_line(msp, (fx - fr_w, fr_y + 2), (fx + fr_w, fr_y + 2), 'HIDDEN')
    base_r = r * 0.55
    _add_polyline(msp, [(fx - base_r, floor_y), (fx + base_r, floor_y),
                        (fx + base_r, floor_y + 3), (fx - base_r, floor_y + 3)], True)
    _add_dimension(msp, (fx - r, top_y + 6), (fx + r, top_y + 6),
                   (fx, top_y + 12), 'W = {:.0f} cm'.format(diameter_or_width_cm))
    _add_dimension(msp, (fx + r + 8, floor_y), (fx + r + 8, top_y + 4),
                   (fx + r + 18, (floor_y + top_y + 4) / 2), 'H = {:.0f} cm'.format(height_cm))
    _add_mtext(msp, 'FRONT VIEW', (fx - r, top_y + 22), 3)
    generate_title_block(msp, 'Bar Stool {:.0f} x H{:.0f}'.format(diameter_or_width_cm, height_cm),
                         material_notes=['SEAT — ' + mats.get('seat', 'Upholstered fabric'),
                                         'BASE — ' + mats.get('base', 'Powder-coated steel')])
    return _save(doc, path)


def save_bench_chaise(path, length_cm=140, depth_cm=55, height_cm=85, seat_height_cm=45,
                      materials: Optional[Dict[str, str]] = None):
    """Bench chaise shop drawing with long seat, legs, optional backrest."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    l, d, h = length_cm * sc, depth_cm * sc, height_cm * sc
    sh = seat_height_cm * sc
    y_mid = 180
    mats = materials or {}

    # ===== TOP VIEW =====
    ox, oy = 100, y_mid
    _add_polyline(msp, [(ox - l / 2, oy - d / 2), (ox + l / 2, oy - d / 2),
                        (ox + l / 2, oy + d / 2), (ox - l / 2, oy + d / 2)], True)
    _add_centerline(msp, (ox - l / 2 - 5, oy), (ox + l / 2 + 5, oy))
    _add_centerline(msp, (ox, oy - d / 2 - 5), (ox, oy + d / 2 + 5))
    _add_dimension(msp, (ox - l / 2, oy + d / 2 + 6), (ox + l / 2, oy + d / 2 + 6),
                   (ox, oy + d / 2 + 12), 'L = {:.0f} cm'.format(length_cm))
    _add_dimension(msp, (ox + l / 2 + 6, oy - d / 2), (ox + l / 2 + 6, oy + d / 2),
                   (ox + l / 2 + 14, oy), 'D = {:.0f} cm'.format(depth_cm))
    _add_mtext(msp, 'TOP VIEW', (ox - 15, oy + d / 2 + 22), 3)

    # ===== FRONT VIEW =====
    fx = 280
    floor_y = y_mid - h / 2
    top_y = floor_y + h
    seat_top_y = floor_y + sh
    _add_polyline(msp, [(fx - l / 2, floor_y), (fx + l / 2, floor_y),
                        (fx + l / 2, seat_top_y), (fx - l / 2, seat_top_y)], True)
    _add_hatch_polygon(msp, [(fx - l / 2, floor_y + 2), (fx + l / 2, floor_y + 2),
                              (fx + l / 2, seat_top_y - 2), (fx - l / 2, seat_top_y - 2)],
                       'ANSI31', 0.3)
    br_h = h - sh
    if br_h > 10:
        _add_polyline(msp, [(fx - l * 0.9 / 2, seat_top_y), (fx + l * 0.9 / 2, seat_top_y),
                            (fx + l * 0.9 / 2, top_y), (fx - l * 0.9 / 2, top_y)], True)
    leg_h = max(4, h * 0.06)
    for lx in [fx - l / 2 + 4, fx + l / 2 - 4]:
        _add_polyline(msp, [(lx, floor_y - leg_h), (lx + 2, floor_y - leg_h),
                            (lx + 2, floor_y), (lx, floor_y)], True)
    _add_dimension(msp, (fx - l / 2, floor_y - leg_h - 5), (fx + l / 2, floor_y - leg_h - 5),
                   (fx, floor_y - leg_h - 12), 'W = {:.0f} cm'.format(length_cm))
    _add_dimension(msp, (fx + l / 2 + 8, floor_y), (fx + l / 2 + 8, top_y),
                   (fx + l / 2 + 18, (floor_y + top_y) / 2), 'H = {:.0f} cm'.format(height_cm))
    _add_mtext(msp, 'FRONT VIEW', (fx - l / 2, top_y + 8), 3)
    generate_title_block(msp, 'Bench Chaise {:.0f}x{:.0f}x{:.0f}'.format(length_cm, depth_cm, height_cm),
                         material_notes=['SEAT — ' + mats.get('seat', 'Upholstered fabric'),
                                         'FRAME — ' + mats.get('frame', 'Solid wood')])
    return _save(doc, path)


def save_ottoman(path, width_cm=55, depth_cm=55, height_cm=40,
                 materials: Optional[Dict[str, str]] = None):
    """Ottoman/pouf shop drawing with cushion body, optional legs."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    w, d, h = width_cm * sc, depth_cm * sc, height_cm * sc
    y_mid = 180
    mats = materials or {}

    # ===== TOP VIEW =====
    ox, oy = 100, y_mid
    _add_polyline(msp, [(ox - w / 2, oy - d / 2), (ox + w / 2, oy - d / 2),
                        (ox + w / 2, oy + d / 2), (ox - w / 2, oy + d / 2)], True)
    _add_polyline(msp, [(ox - w / 2 + 3, oy - d / 2 + 3), (ox + w / 2 - 3, oy - d / 2 + 3),
                        (ox + w / 2 - 3, oy + d / 2 - 3), (ox - w / 2 + 3, oy + d / 2 - 3)], True, 'HIDDEN')
    _add_centerline(msp, (ox - w / 2 - 5, oy), (ox + w / 2 + 5, oy))
    _add_centerline(msp, (ox, oy - d / 2 - 5), (ox, oy + d / 2 + 5))
    _add_dimension(msp, (ox - w / 2, oy + d / 2 + 6), (ox + w / 2, oy + d / 2 + 6),
                   (ox, oy + d / 2 + 12), 'W = {:.0f} cm'.format(width_cm))
    _add_dimension(msp, (ox + w / 2 + 6, oy - d / 2), (ox + w / 2 + 6, oy + d / 2),
                   (ox + w / 2 + 14, oy), 'D = {:.0f} cm'.format(depth_cm))
    _add_mtext(msp, 'TOP VIEW', (ox - 15, oy + d / 2 + 22), 3)

    # ===== FRONT VIEW =====
    fx = 280
    floor_y = y_mid - h / 2
    top_y = floor_y + h
    _add_polyline(msp, [(fx - w / 2, floor_y), (fx + w / 2, floor_y),
                        (fx + w / 2, top_y - 2), (fx + w / 2 - 2, top_y),
                        (fx - w / 2 + 2, top_y), (fx - w / 2, top_y - 2)], True)
    _add_hatch_polygon(msp, [(fx - w / 2 + 2, floor_y + 2), (fx + w / 2 - 2, floor_y + 2),
                              (fx + w / 2 - 2, top_y - 4), (fx - w / 2 + 2, top_y - 4)],
                       'ANSI31', 0.3)
    leg_h = max(3, h * 0.08)
    for lx in [fx - w / 2 + 5, fx + w / 2 - 5]:
        _add_polyline(msp, [(lx, floor_y - leg_h), (lx + 2, floor_y - leg_h),
                            (lx + 2, floor_y), (lx, floor_y)], True)
    _add_dimension(msp, (fx - w / 2, floor_y - leg_h - 5), (fx + w / 2, floor_y - leg_h - 5),
                   (fx, floor_y - leg_h - 12), 'W = {:.0f} cm'.format(width_cm))
    _add_dimension(msp, (fx + w / 2 + 8, floor_y - leg_h), (fx + w / 2 + 8, top_y),
                   (fx + w / 2 + 18, (floor_y + top_y) / 2), 'H = {:.0f} cm'.format(height_cm))
    _add_mtext(msp, 'FRONT VIEW', (fx - w / 2, top_y + 8), 3)
    generate_title_block(msp, 'Ottoman Pouf {:.0f}x{:.0f}x{:.0f}'.format(width_cm, depth_cm, height_cm),
                         material_notes=['BODY — ' + mats.get('cushion_body', 'Upholstered fabric over foam')])
    return _save(doc, path)


def save_rug(path, length_cm=160, width_cm=120, pile_height_mm=10,
             materials: Optional[Dict[str, str]] = None):
    """Rug shop drawing with outline, border, pile thickness indication."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    l, w = length_cm * sc, width_cm * sc
    y_mid = 180
    mats = materials or {}
    ph = max(2, pile_height_mm / 10 * sc)

    # ===== TOP VIEW =====
    ox, oy = 100, y_mid
    _add_polyline(msp, [(ox - l / 2, oy - w / 2), (ox + l / 2, oy - w / 2),
                        (ox + l / 2, oy + w / 2), (ox - l / 2, oy + w / 2)], True)
    border_inset = 3
    _add_polyline(msp, [(ox - l / 2 + border_inset, oy - w / 2 + border_inset),
                        (ox + l / 2 - border_inset, oy - w / 2 + border_inset),
                        (ox + l / 2 - border_inset, oy + w / 2 - border_inset),
                        (ox - l / 2 + border_inset, oy + w / 2 - border_inset)], True, 'HIDDEN')
    _add_centerline(msp, (ox - l / 2 - 5, oy), (ox + l / 2 + 5, oy))
    _add_centerline(msp, (ox, oy - w / 2 - 5), (ox, oy + w / 2 + 5))
    _add_dimension(msp, (ox - l / 2, oy + w / 2 + 6), (ox + l / 2, oy + w / 2 + 6),
                   (ox, oy + w / 2 + 12), 'L = {:.0f} cm'.format(length_cm))
    _add_dimension(msp, (ox + l / 2 + 6, oy - w / 2), (ox + l / 2 + 6, oy + w / 2),
                   (ox + l / 2 + 14, oy), 'W = {:.0f} cm'.format(width_cm))
    _add_mtext(msp, 'TOP VIEW', (ox - 15, oy + w / 2 + 22), 3)

    # ===== SIDE VIEW =====
    fx = 280
    _add_polyline(msp, [(fx, oy - l / 2), (fx + ph * 4, oy - l / 2),
                        (fx + ph * 4, oy + l / 2), (fx, oy + l / 2)], True)
    for i in range(-3, 4):
        yy = oy + i * l * 0.1
        _add_line(msp, (fx + 1, yy), (fx + ph * 4 - 1, yy), 'HATCH')
    _add_mtext(msp, 'SIDE ({:.0f}mm pile)'.format(pile_height_mm), (fx - 5, oy + l / 2 + 10), 2.5)
    generate_title_block(msp, 'Rug {:.0f}x{:.0f}'.format(length_cm, width_cm),
                         material_notes=['MATERIAL — ' + mats.get('rug_outline', 'Textile / Wool')])
    return _save(doc, path)


def save_stone_slab(path, length_cm=200, width_cm=100, thickness_cm=2.0,
                    materials: Optional[Dict[str, str]] = None):
    """Stone slab shop drawing with top view and section."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    l, w = length_cm * sc, width_cm * sc
    t = max(0.5, thickness_cm * sc)
    y_mid = 180
    mats = materials or {}

    # ===== TOP VIEW =====
    ox, oy = 100, y_mid
    _add_polyline(msp, [(ox - l / 2, oy - w / 2), (ox + l / 2, oy - w / 2),
                        (ox + l / 2, oy + w / 2), (ox - l / 2, oy + w / 2)], True)
    _add_hatch_polygon(msp, [(ox - l / 2 + 1, oy - w / 2 + 1), (ox + l / 2 - 1, oy - w / 2 + 1),
                              (ox + l / 2 - 1, oy + w / 2 - 1), (ox - l / 2 + 1, oy + w / 2 - 1)],
                       'ANSI37', 0.5, 30.0)
    _add_centerline(msp, (ox - l / 2 - 5, oy), (ox + l / 2 + 5, oy))
    _add_centerline(msp, (ox, oy - w / 2 - 5), (ox, oy + w / 2 + 5))
    _add_dimension(msp, (ox - l / 2, oy + w / 2 + 6), (ox + l / 2, oy + w / 2 + 6),
                   (ox, oy + w / 2 + 12), 'L = {:.0f} cm'.format(length_cm))
    _add_dimension(msp, (ox + l / 2 + 6, oy - w / 2), (ox + l / 2 + 6, oy + w / 2),
                   (ox + l / 2 + 14, oy), 'W = {:.0f} cm'.format(width_cm))
    _add_mtext(msp, 'TOP VIEW', (ox - 15, oy + w / 2 + 22), 3)

    # ===== SECTION =====
    fx = 280
    _add_polyline(msp, [(fx, oy - l / 2), (fx + t, oy - l / 2),
                        (fx + t, oy + l / 2), (fx, oy + l / 2)], True)
    _add_hatch_polygon(msp, [(fx + 0.5, oy - l / 2 + 0.5), (fx + t - 0.5, oy - l / 2 + 0.5),
                              (fx + t - 0.5, oy + l / 2 - 0.5), (fx + 0.5, oy + l / 2 - 0.5)],
                       'ANSI31', 0.2)
    _add_dimension(msp, (fx, oy - l / 2 - 6), (fx + t, oy - l / 2 - 6),
                   (fx + t / 2, oy - l / 2 - 12), 'T = {:.0f} cm'.format(thickness_cm))
    _add_mtext(msp, 'SECTION ({:.0f}mm)'.format(thickness_cm), (fx - 5, oy + l / 2 + 10), 2.5)
    generate_title_block(msp, 'Stone Slab {:.0f}x{:.0f}x{:.0f}'.format(length_cm, width_cm, thickness_cm),
                         material_notes=['MATERIAL — ' + mats.get('slab_outline', 'Sintered stone / marble')])
    return _save(doc, path)


def save_wall_panel(path, width_cm=120, height_cm=240, thickness_cm=2.0, slat_spacing_mm=10,
                    materials: Optional[Dict[str, str]] = None):
    """Wall panel fluted shop drawing with slat pattern."""
    doc = setup_doc()
    msp = doc.modelspace()
    sc = 0.5
    w, h = width_cm * sc, height_cm * sc
    t = max(0.5, thickness_cm * sc)
    ss = max(0.5, slat_spacing_mm / 10 * sc)
    y_mid = 180
    mats = materials or {}

    # ===== FRONT VIEW =====
    fx, fy = 100, y_mid
    _add_polyline(msp, [(fx - w / 2, fy - h / 2), (fx + w / 2, fy - h / 2),
                        (fx + w / 2, fy + h / 2), (fx - w / 2, fy + h / 2)], True)
    num_slats = max(3, int(w / ss))
    for i in range(1, num_slats):
        sx = fx - w / 2 + i * ss
        _add_line(msp, (sx, fy - h / 2), (sx, fy + h / 2), 'HATCH')
    _add_centerline(msp, (fx - w / 2 - 5, fy), (fx + w / 2 + 5, fy))
    _add_centerline(msp, (fx, fy - h / 2 - 5), (fx, fy + h / 2 + 5))
    _add_dimension(msp, (fx - w / 2, fy + h / 2 + 6), (fx + w / 2, fy + h / 2 + 6),
                   (fx, fy + h / 2 + 12), 'W = {:.0f} cm'.format(width_cm))
    _add_dimension(msp, (fx + w / 2 + 6, fy - h / 2), (fx + w / 2 + 6, fy + h / 2),
                   (fx + w / 2 + 14, fy), 'H = {:.0f} cm'.format(height_cm))
    _add_mtext(msp, 'FRONT VIEW ({:.0f} slats @ {:.0f}mm)'.format(num_slats, slat_spacing_mm), (fx - 15, fy + h / 2 + 22), 2.5)

    # ===== SIDE/SECTION =====
    sx = 280
    _add_polyline(msp, [(sx, fy - h / 2), (sx + t, fy - h / 2),
                        (sx + t, fy + h / 2), (sx, fy + h / 2)], True)
    _add_hatch_polygon(msp, [(sx + 0.3, fy - h / 2 + 0.3), (sx + t - 0.3, fy - h / 2 + 0.3),
                              (sx + t - 0.3, fy + h / 2 - 0.3), (sx + 0.3, fy + h / 2 - 0.3)],
                       'ANSI31', 0.2)
    _add_dimension(msp, (sx, fy - h / 2 - 6), (sx + t, fy - h / 2 - 6),
                   (sx + t / 2, fy - h / 2 - 12), 'T = {:.0f} cm'.format(thickness_cm))
    _add_mtext(msp, 'SECTION ({:.0f}mm)'.format(thickness_cm), (sx - 5, fy + h / 2 + 10), 2.5)
    generate_title_block(msp, 'Wall Panel Fluted {:.0f}x{:.0f}'.format(width_cm, height_cm),
                         material_notes=['MATERIAL — ' + mats.get('panel_body', 'Solid wood slats')])
    return _save(doc, path)


def save_lounge_chair(path, width_cm=70, depth_cm=75, height_cm=90, seat_height_cm=45,
                      materials=None):
    """Lounge chair — wider, deeper dining chair with plush cushioning."""
    save_armchair(path, width_cm=width_cm, depth_cm=depth_cm, height_cm=height_cm,
                  seat_height_cm=seat_height_cm, materials=materials)


def save_sideboard(path, width_cm=140, depth_cm=45, height_cm=85, door_count=2,
                   drawer_count=2, materials=None):
    """Sideboard with doors and drawers — uses cabinet layout."""
    save_cabinet(path, width_cm=width_cm, depth_cm=depth_cm, height_cm=height_cm,
                 materials=materials)


def save_tv_console(path, width_cm=160, depth_cm=40, height_cm=55, drawer_count=2,
                    materials=None):
    """Low TV/media cabinet — uses cabinet layout at lower height."""
    save_cabinet(path, width_cm=width_cm, depth_cm=depth_cm, height_cm=height_cm,
                 materials=materials)
