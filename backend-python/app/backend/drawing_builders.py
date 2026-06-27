"""
Drawing Builders — convenience functions to build DrawingModel for each furniture type.
These were previously in drawing_model.py but were extracted to their own module
during the accuracy upgrade to keep the model clean. Re-exported for backward compat.

All builder functions accept optional EntityMetadata for confidence tracking.
"""

import math
from datetime import datetime
from typing import List, Optional, Dict

from app.backend.drawing_model import (
    DrawingModel, View, TitleBlockData, Point,
    CircleComponent, PolygonComponent, LineComponent,
    TextComponent, DimensionComponent, LeaderComponent,
    HatchComponent, EntityMetadata,
)


def build_round_pedestal_model(
    top_dia_cm: float = 80.0,
    height_cm: float = 70.0,
    base_dia_cm: float = 44.0,
    neck_dia_cm: float = 30.0,
    top_thick_cm: float = 4.0,
    collar_dia_cm: float = 50.0,
    base_thick_cm: float = 1.0,
    client: str = "",
    project: str = "Furniture Shop Drawing",
    material_notes: Optional[List[str]] = None,
    materials: Optional[Dict[str, str]] = None,
    profile: str = "cylinder",
) -> DrawingModel:
    """Build a complete DrawingModel for a round pedestal table."""
    now = datetime.now().strftime('%Y-%m-%d')
    sc = 2.0
    r_top = top_dia_cm / 2 * sc
    r_collar = collar_dia_cm / 2 * sc
    r_neck = neck_dia_cm / 2 * sc
    r_base = base_dia_cm / 2 * sc
    thick_top = top_thick_cm * sc
    thick_base = base_thick_cm * sc
    remaining_h = max(1.0, height_cm - top_thick_cm - base_thick_cm)
    collar_h_cm = remaining_h * 0.14
    ped_h_cm = remaining_h * 0.86
    collar_h = collar_h_cm * sc
    ped_h = ped_h_cm * sc
    h_total = height_cm * sc
    floor_y = 30.0
    top_y = floor_y + h_total
    tab_bot = top_y - thick_top
    col_top = tab_bot
    col_bot = col_top - collar_h
    ped_bot = col_bot - ped_h
    base_bot = floor_y
    # fx (FRONT VIEW's horizontal center) used to be a fixed 160 regardless of
    # top_dia_cm. The TOP VIEW circle (radius tv_r, below) sits to its left;
    # for any top_dia_cm bigger than the value this constant was tuned for,
    # FRONT VIEW's own left edge AND its left dimension column (which extends
    # further left still) collide with the TOP VIEW circle, its centerlines,
    # and its "TOP VIEW" label - visibly overlapping in the rendered drawing.
    # 80cm (the most common top diameter, and the schema's lower-middle
    # default) was exactly the case that triggered this. Compute fx from the
    # TOP VIEW's actual rightmost extent instead of a guessed constant, so
    # the two views never overlap regardless of furniture size.
    tv_cx_planned = 55.0
    tv_r_planned = top_dia_cm / 2 * 0.6
    top_view_right_edge = tv_cx_planned + tv_r_planned + max(4.0, tv_r_planned * 0.12) + 15.0
    # FRONT VIEW's own leftmost extent is its left dimension column, at
    # fx - r_top - 18 (see dim_x_left below) - solve for fx so that sits
    # clear of the TOP VIEW's right edge with a margin.
    fx = max(160.0, top_view_right_edge + r_top + 30.0)
    lx_start = fx + r_top + 12
    lx_text = lx_start + 5

    # TOP VIEW
    top_view = View(name="TOP VIEW")
    tv_cx, tv_cy = tv_cx_planned, top_y - r_top * 0.5
    tv_r = tv_r_planned
    top_view.circles.append(CircleComponent(center=Point(tv_cx, tv_cy), radius=tv_r, layer="OBJECT"))
    for i in range(8):
        angle = 2 * math.pi * i / 8
        x1 = tv_cx + tv_r * 0.15 * math.cos(angle)
        y1 = tv_cy + tv_r * 0.15 * math.sin(angle)
        x2 = tv_cx + tv_r * math.cos(angle)
        y2 = tv_cy + tv_r * math.sin(angle)
        top_view.lines.append(LineComponent(start=Point(x1, y1), end=Point(x2, y2), layer="HATCH"))
    ext = max(4.0, tv_r * 0.12)
    top_view.lines.append(LineComponent(start=Point(tv_cx - tv_r - ext, tv_cy), end=Point(tv_cx + tv_r + ext, tv_cy), layer="CENTER"))
    top_view.lines.append(LineComponent(start=Point(tv_cx, tv_cy - tv_r - ext), end=Point(tv_cx, tv_cy + tv_r + ext), layer="CENTER"))
    top_view.dimensions.append(DimensionComponent(p1=Point(tv_cx - tv_r, tv_cy + tv_r + ext), p2=Point(tv_cx + tv_r, tv_cy + tv_r + ext), label=f"\u00d8{top_dia_cm:g}", layer="DIMENSION"))
    top_view.texts.append(TextComponent(content="TOP VIEW", position=Point(tv_cx - 12, tv_cy - tv_r - ext - 3), height=2.5, layer="MTEXT"))

    # FRONT VIEW
    front_view = View(name="FRONT VIEW")
    front_view.polygons.append(PolygonComponent(points=[Point(fx - r_top, top_y), Point(fx + r_top, top_y), Point(fx + r_top, tab_bot), Point(fx - r_top, tab_bot)], layer="OBJECT", name="tabletop"))
    front_view.hatches.append(HatchComponent(points=[Point(fx - r_top, top_y), Point(fx + r_top, top_y), Point(fx + r_top, tab_bot), Point(fx - r_top, tab_bot)], pattern="ANSI31", scale=0.8, angle_deg=45, layer="HATCH"))
    front_view.polygons.append(PolygonComponent(points=[Point(fx - r_collar, col_top), Point(fx + r_collar, col_top), Point(fx + r_collar, col_bot), Point(fx - r_collar, col_bot)], layer="OBJECT", name="collar_plate"))
    neck_h_px = collar_h * 0.3
    neck_top_y = col_bot
    neck_bot_y = col_bot - neck_h_px
    front_view.polygons.append(PolygonComponent(points=[Point(fx - r_neck, neck_top_y), Point(fx + r_neck, neck_top_y), Point(fx + r_neck, neck_bot_y), Point(fx - r_neck, neck_bot_y)], layer="OBJECT", name="neck_ring"))
    # The body's TOP edge only tapers down to the neck's width for a genuine
    # tapered/flared profile (a smooth cone). For 'cylinder' (the common
    # case - a narrow neck/collar ring sitting on top of a SEPARATE, wider,
    # perfectly straight column with a sharp STEP between them, not a
    # gradual widening) the body is a straight rectangle at its own width
    # the whole way down. Forcing every profile through the same tapering
    # trapezoid is what made a stepped pedestal render as a smooth cone.
    body_top_r = r_neck if profile in ("tapered", "flared") else r_base
    front_view.polygons.append(PolygonComponent(points=[Point(fx - body_top_r, neck_bot_y), Point(fx + body_top_r, neck_bot_y), Point(fx + r_base, ped_bot), Point(fx - r_base, ped_bot)], layer="OBJECT", name="pedestal_body"))
    front_view.hatches.append(HatchComponent(points=[Point(fx - body_top_r, neck_bot_y), Point(fx + body_top_r, neck_bot_y), Point(fx + r_base, ped_bot), Point(fx - r_base, ped_bot)], pattern="ANSI37", scale=0.5, angle_deg=45, layer="HATCH"))
    front_view.polygons.append(PolygonComponent(points=[Point(fx - r_base, ped_bot), Point(fx + r_base, ped_bot), Point(fx + r_base, base_bot), Point(fx - r_base, base_bot)], layer="OBJECT", name="base_plate"))
    front_view.lines.append(LineComponent(start=Point(fx, base_bot - 6), end=Point(fx, top_y + 6), layer="CENTER"))

    dim_x_left = fx - r_top - 8
    front_view.dimensions.append(DimensionComponent(p1=Point(dim_x_left - 10, base_bot), p2=Point(dim_x_left - 10, top_y), label=f"{height_cm:g}", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(p1=Point(dim_x_left, tab_bot), p2=Point(dim_x_left, top_y), label=f"{top_thick_cm:g}", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(p1=Point(dim_x_left, neck_bot_y), p2=Point(dim_x_left, tab_bot), label=f"{collar_h_cm:.0f}", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(p1=Point(dim_x_left, base_bot), p2=Point(dim_x_left, neck_bot_y), label=f"{ped_h_cm:.0f}", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(p1=Point(fx - r_top, top_y + 6), p2=Point(fx + r_top, top_y + 6), label=f"{top_dia_cm:g}", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(p1=Point(fx - r_collar, col_top - 4), p2=Point(fx + r_collar, col_top - 4), label=f"{collar_dia_cm:g}", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(p1=Point(fx - r_neck, neck_bot_y - 4), p2=Point(fx + r_neck, neck_bot_y - 4), label=f"{neck_dia_cm:g}", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(p1=Point(fx - r_base, ped_bot - 4), p2=Point(fx + r_base, ped_bot - 4), label=f"{base_dia_cm:g}", layer="DIMENSION"))

    ped_mid_y = (neck_bot_y + ped_bot) / 2
    base_mid_y = (ped_bot + base_bot) / 2
    mats = materials or {}
    raw_callouts = [
        ((col_top + col_bot) / 2, fx + r_collar,
         mats.get('collar_plate', f"Dia {collar_dia_cm:.0f}cm Metal base plate")),
        (neck_top_y, fx + r_neck, mats.get('neck_ring', "Matte hairline black steel")),
        (neck_bot_y, fx + r_neck, mats.get('base_plate', f"Dia {base_dia_cm:.0f}cm Metal base plate")),
        (ped_mid_y, fx + (r_neck + r_base) / 2, mats.get('pedestal_body', "Black hammered textured PU coating")),
        (base_mid_y, fx + r_base, mats.get('base_foot', "Black table base with anti-sliding glides")),
    ]
    min_label_gap = 9.0
    prev_text_y = None
    for target_y, target_x, text in raw_callouts:
        text_y = target_y if prev_text_y is None else min(target_y, prev_text_y - min_label_gap)
        front_view.leaders.append(LeaderComponent(start=Point(lx_text, text_y), end=Point(target_x, target_y), text=text, layer="LEADER"))
        prev_text_y = text_y
    front_view.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx - r_top, base_bot - 12), height=3, layer="MTEXT"))

    title = TitleBlockData(
        drawing_title=f"Round Pedestal Table \u00d8{top_dia_cm:.0f} x H{height_cm:.0f}",
        project=project, client=client, scale="1:2", revision="A",
        designer="AI CAD Drafter", date=now,
        material_notes=material_notes or [
            f"WOOD TOP — {mats.get('tabletop', 'Solid hardwood, stained finish')}",
            f"PEDESTAL BASE — {mats.get('pedestal_body', 'Black hammered textured metal, PU coat')}",
            f"COLLAR PLATE — {mats.get('collar_plate', 'Matte hairline black steel')}",
            f"BASE GLIDES — {mats.get('base_foot', 'Anti-sliding rubber feet')}",
        ],
        general_notes=["ALL DIMENSIONS IN CENTIMETERS (CM) UNLESS NOTED", "TOLERANCES: +/- 2mm UNLESS OTHERWISE SPECIFIED"],
    )

    return DrawingModel(
        furniture_type="round_pedestal_table", views=[top_view, front_view], title_block=title,
        known_dimensions={"top_diameter_cm": top_dia_cm, "overall_height_cm": height_cm},
        estimated_components={"pedestal_diameter_cm": base_dia_cm, "neck_diameter_cm": neck_dia_cm, "top_thickness_cm": top_thick_cm},
    )


def build_rectangular_table_model(
    width_cm: float = 120.0, depth_cm: float = 80.0, height_cm: float = 70.0,
    leg_thickness_cm: float = 6.0, client: str = "", project: str = "Furniture Shop Drawing",
) -> DrawingModel:
    """Build DrawingModel for a rectangular table."""
    sc = 0.4; w = width_cm * sc; d = depth_cm * sc; h = height_cm * sc
    w2, d2 = w / 2, d / 2; ox, y_mid = 100.0, 180.0; lt = leg_thickness_cm * sc
    fx = 280.0; floor_y = 30.0; top_y = floor_y + h; top_thick = max(lt * 0.8, 2.0)
    now = datetime.now().strftime('%Y-%m-%d')
    tv = View(name="TOP VIEW")
    tv.polygons.append(PolygonComponent(points=[Point(ox - w2, y_mid - d2), Point(ox + w2, y_mid - d2), Point(ox + w2, y_mid + d2), Point(ox - w2, y_mid + d2)], layer="OBJECT", name="tabletop"))
    for lx, ly in [(ox - w2, y_mid - d2), (ox + w2 - lt, y_mid - d2), (ox - w2, y_mid + d2 - lt), (ox + w2 - lt, y_mid + d2 - lt)]:
        tv.polygons.append(PolygonComponent(points=[Point(lx, ly), Point(lx + lt, ly), Point(lx + lt, ly + lt), Point(lx, ly + lt)], layer="HIDDEN", linetype="HIDDEN", name="leg_footprint"))
    tv.lines.append(LineComponent(start=Point(ox - w2 - 5, y_mid), end=Point(ox + w2 + 5, y_mid), layer="CENTER"))
    tv.lines.append(LineComponent(start=Point(ox, y_mid - d2 - 5), end=Point(ox, y_mid + d2 + 5), layer="CENTER"))
    tv.dimensions.append(DimensionComponent(p1=Point(ox - w2, y_mid + d2 + 6), p2=Point(ox + w2, y_mid + d2 + 6), label=f"W = {width_cm:g} cm", layer="DIMENSION"))
    tv.dimensions.append(DimensionComponent(p1=Point(ox + w2 + 6, y_mid - d2), p2=Point(ox + w2 + 6, y_mid + d2), label=f"D = {depth_cm:g} cm", layer="DIMENSION"))
    tv.texts.append(TextComponent(content="TOP VIEW", position=Point(ox - 15, y_mid + d2 + 22), height=3, layer="MTEXT"))
    fv = View(name="FRONT VIEW")
    fv.polygons.append(PolygonComponent(points=[Point(fx - w2, top_y - top_thick), Point(fx + w2, top_y - top_thick), Point(fx + w2, top_y), Point(fx - w2, top_y)], layer="OBJECT", name="tabletop"))
    fv.hatches.append(HatchComponent(points=[Point(fx - w2, top_y - top_thick), Point(fx + w2, top_y - top_thick), Point(fx + w2, top_y), Point(fx - w2, top_y)], pattern="ANSI31", scale=0.5, layer="HATCH"))
    leg_y_top = top_y - top_thick
    for lx in [fx - w2, fx + w2 - lt]:
        fv.polygons.append(PolygonComponent(points=[Point(lx, floor_y), Point(lx + lt, floor_y), Point(lx + lt, leg_y_top), Point(lx, leg_y_top)], layer="OBJECT", name="leg"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + w2 + 8, floor_y), p2=Point(fx + w2 + 8, top_y), label=f"H = {height_cm:g} cm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx - w2, floor_y - 8), p2=Point(fx + w2, floor_y - 8), label=f"W = {width_cm:g} cm", layer="DIMENSION"))
    fv.lines.append(LineComponent(start=Point(fx, floor_y - 5), end=Point(fx, top_y + 5), layer="CENTER"))
    fv.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx - w2, top_y + 10), height=3, layer="MTEXT"))
    tb = TitleBlockData(drawing_title=f"Rectangular Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}", project=project, client=client, scale="1:2.5", revision="A", date=now)
    return DrawingModel(furniture_type="rectangular_table", views=[tv, fv], title_block=tb,
        known_dimensions={"width_cm": width_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm},
        estimated_components={"leg_thickness_cm": leg_thickness_cm})


def build_cabinet_model(width_cm=100, depth_cm=50, height_cm=180, client="", project="Furniture Shop Drawing"):
    sc = 0.3; w = width_cm * sc; h = height_cm * sc; fx = (420 - w) / 2; floor_y = 50.0; top_y = floor_y + h; w2 = w / 2; margin = w * 0.05
    now = datetime.now().strftime('%Y-%m-%d')
    fv = View(name="FRONT VIEW")
    fv.polygons.append(PolygonComponent(points=[Point(fx, floor_y), Point(fx + w, floor_y), Point(fx + w, top_y), Point(fx, top_y)], layer="OBJECT", name="cabinet_body"))
    fv.polygons.append(PolygonComponent(points=[Point(fx + margin, floor_y + margin), Point(fx + w2 - 2, floor_y + margin), Point(fx + w2 - 2, top_y - margin), Point(fx + margin, top_y - margin)], layer="OBJECT", name="door_left"))
    fv.polygons.append(PolygonComponent(points=[Point(fx + w2 + 2, floor_y + margin), Point(fx + w - margin, floor_y + margin), Point(fx + w - margin, top_y - margin), Point(fx + w2 + 2, top_y - margin)], layer="OBJECT", name="door_right"))
    mid_y = (top_y + floor_y) / 2
    fv.lines.append(LineComponent(start=Point(fx + w2 - 6, mid_y - 5), end=Point(fx + w2 - 6, mid_y + 5), layer="OBJECT"))
    fv.lines.append(LineComponent(start=Point(fx + w2 + 6, mid_y - 5), end=Point(fx + w2 + 6, mid_y + 5), layer="OBJECT"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + w + 8, floor_y), p2=Point(fx + w + 8, top_y), label=f"H = {height_cm:g} cm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx, floor_y - 8), p2=Point(fx + w, floor_y - 8), label=f"W = {width_cm:g} cm", layer="DIMENSION"))
    fv.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx, top_y + 10), height=3, layer="MTEXT"))
    tb = TitleBlockData(drawing_title=f"Cabinet {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}", project=project, client=client, scale="1:3.3", revision="A", date=now)
    return DrawingModel(furniture_type="cabinet", views=[fv], title_block=tb,
        known_dimensions={"width_cm": width_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm})


def build_sofa_model(width_cm=200, depth_cm=80, height_cm=85, client="", project="Furniture Shop Drawing"):
    sc = 0.3; w = width_cm * sc; h = height_cm * sc; fx = (420 - w) / 2; floor_y = 50.0; top_y = floor_y + h; seat_y = floor_y + h * 0.55; arm_h = h * 0.4
    now = datetime.now().strftime('%Y-%m-%d')
    fv = View(name="FRONT VIEW")
    fv.polygons.append(PolygonComponent(points=[Point(fx, floor_y), Point(fx + w, floor_y), Point(fx + w, seat_y), Point(fx, seat_y)], layer="OBJECT", name="seat_base"))
    fv.polygons.append(PolygonComponent(points=[Point(fx, seat_y), Point(fx + w, seat_y), Point(fx + w, top_y - arm_h), Point(fx, top_y - arm_h)], layer="OBJECT", name="backrest"))
    fv.polygons.append(PolygonComponent(points=[Point(fx - 5, seat_y - 5), Point(fx + 10, seat_y - 5), Point(fx + 10, top_y), Point(fx - 5, top_y)], layer="OBJECT", name="arm_left"))
    fv.polygons.append(PolygonComponent(points=[Point(fx + w - 10, seat_y - 5), Point(fx + w + 5, seat_y - 5), Point(fx + w + 5, top_y), Point(fx + w - 10, top_y)], layer="OBJECT", name="arm_right"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + w + 8, floor_y), p2=Point(fx + w + 8, top_y), label=f"H = {height_cm:g} cm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx, floor_y - 8), p2=Point(fx + w, floor_y - 8), label=f"W = {width_cm:g} cm", layer="DIMENSION"))
    fv.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx, top_y + 10), height=3, layer="MTEXT"))
    tb = TitleBlockData(drawing_title=f"Sofa {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}", project=project, client=client, scale="1:3.3", revision="A", date=now)
    return DrawingModel(furniture_type="sofa", views=[fv], title_block=tb,
        known_dimensions={"width_cm": width_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm})


def build_coffee_table_model(w=100.0, d=60.0, h=45.0):
    sc, cx, ym = 0.6, 100.0, 190.0; r = min(w, d) / 2 * sc; n = datetime.now().strftime('%Y-%m-%d')
    tv = View(name="TOP VIEW")
    tv.circles.append(CircleComponent(center=Point(cx, ym), radius=r, layer="OBJECT"))
    tv.lines.append(LineComponent(start=Point(cx-r-5, ym), end=Point(cx+r+5, ym), layer="CENTER"))
    tv.lines.append(LineComponent(start=Point(cx, ym-r-5), end=Point(cx, ym+r+5), layer="CENTER"))
    tv.dimensions.append(DimensionComponent(p1=Point(cx-r, ym), p2=Point(cx+r, ym), label=f"%%c{min(w,d):g} cm", layer="DIMENSION"))
    tv.texts.append(TextComponent(content="TOP VIEW", position=Point(cx-10, ym+r+10), height=3, layer="MTEXT"))
    tb = TitleBlockData(f"Coffee Table {w:.0f}x{d:.0f}x{h:.0f}", project="Furniture Shop Drawing", scale="1:2", revision="A", date=n)
    return DrawingModel(furniture_type="coffee_table", views=[tv], title_block=tb,
        known_dimensions={"width_cm": w, "depth_cm": d, "overall_height_cm": h})


def build_dining_chair_model(w=45.0, h=90.0):
    sc, w2 = 0.5, w * 0.5 * 0.5; fx = (420 - w * 0.5) / 2; fy, ty = 50.0, 50.0 + h * 0.5; sy = fy + h * 0.5 * 0.5
    n = datetime.now().strftime('%Y-%m-%d')
    fv = View(name="FRONT VIEW")
    fv.polygons.append(PolygonComponent(points=[Point(fx, sy), Point(fx+w*0.5, sy), Point(fx+w*0.5, ty), Point(fx, ty)], layer="OBJECT", name="backrest"))
    fv.polygons.append(PolygonComponent(points=[Point(fx, fy), Point(fx+w*0.5, fy), Point(fx+w*0.5, sy), Point(fx, sy)], layer="OBJECT", name="seat"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx+w*0.5+8, fy), p2=Point(fx+w*0.5+8, ty), label=f"H = {h:g} cm", layer="DIMENSION"))
    fv.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx, ty+10), height=3, layer="MTEXT"))
    tb = TitleBlockData(f"Dining Chair {w:.0f}x{h:.0f}", project="Furniture Shop Drawing", scale="1:2", revision="A", date=n)
    return DrawingModel(furniture_type="dining_chair", views=[fv], title_block=tb,
        known_dimensions={"width_cm": w, "overall_height_cm": h})


def build_wardrobe_model(w=120.0, d=60.0, h=200.0):
    return build_cabinet_model(w, d, h)


def build_oval_pedestal_model(
    length_cm: float = 180.0, depth_cm: float = 100.0, height_cm: float = 75.0,
    top_thick_cm: float = 3.0, pedestal_dia_cm: float = 40.0,
    client: str = "", project: str = "Furniture Shop Drawing",
    materials: Optional[Dict[str, str]] = None,
) -> DrawingModel:
    """Build DrawingModel for an oval/elliptical pedestal table."""
    import math
    now = datetime.now().strftime('%Y-%m-%d')
    sc = 0.35; w = length_cm * sc; d = depth_cm * sc; h = height_cm * sc
    tt = top_thick_cm * sc; pd_r = pedestal_dia_cm / 2 * sc
    w2, d2 = w / 2, d / 2; y_mid = 180.0
    mats = materials or {}
    tx, ty = 100.0, y_mid
    # TOP VIEW
    tv = View(name="TOP VIEW")
    oval_pts = []
    for i in range(36):
        a = 2 * math.pi * i / 36
        oval_pts.append(Point(tx + w2 * math.cos(a), ty + d2 * math.sin(a)))
    tv.polygons.append(PolygonComponent(points=oval_pts, layer="OBJECT", name="tabletop"))
    tv.circles.append(CircleComponent(center=Point(tx, ty), radius=pd_r, layer="HIDDEN"))
    ext = max(5.0, w2 * 0.1)
    tv.lines.append(LineComponent(start=Point(tx - w2 - ext, ty), end=Point(tx + w2 + ext, ty), layer="CENTER"))
    tv.lines.append(LineComponent(start=Point(tx, ty - d2 - ext), end=Point(tx, ty + d2 + ext), layer="CENTER"))
    tv.dimensions.append(DimensionComponent(p1=Point(tx - w2, ty + d2 + 6), p2=Point(tx + w2, ty + d2 + 6),
                                             label=f"W = {length_cm * 10:.0f} mm", layer="DIMENSION"))
    tv.dimensions.append(DimensionComponent(p1=Point(tx + w2 + 6, ty - d2), p2=Point(tx + w2 + 6, ty + d2),
                                             label=f"D = {depth_cm * 10:.0f} mm", layer="DIMENSION"))
    tv.texts.append(TextComponent(content="TOP VIEW", position=Point(tx - 15, ty + d2 + 22), height=3, layer="MTEXT"))
    # FRONT VIEW
    fv = View(name="FRONT ELEVATION")
    fx, floor_y = 290.0, 40.0; top_y = floor_y + h; tab_bot = top_y - tt; ped_bot = floor_y + 5.0
    fv.polygons.append(PolygonComponent(points=[Point(fx - w2, tab_bot), Point(fx + w2, tab_bot), Point(fx + w2, top_y), Point(fx - w2, top_y)], layer="OBJECT", name="tabletop"))
    fv.hatches.append(HatchComponent(points=[Point(fx - w2, tab_bot), Point(fx + w2, tab_bot), Point(fx + w2, top_y), Point(fx - w2, top_y)], pattern="ANSI31", scale=0.5, angle_deg=45, layer="HATCH"))
    fv.polygons.append(PolygonComponent(points=[Point(fx - pd_r, ped_bot), Point(fx + pd_r, ped_bot), Point(fx + pd_r, tab_bot), Point(fx - pd_r, tab_bot)], layer="OBJECT", name="pedestal"))
    fv.hatches.append(HatchComponent(points=[Point(fx - pd_r, ped_bot), Point(fx + pd_r, ped_bot), Point(fx + pd_r, tab_bot), Point(fx - pd_r, tab_bot)], pattern="ANSI37", scale=0.3, layer="HATCH"))
    fv.lines.append(LineComponent(start=Point(fx, floor_y - 5), end=Point(fx, top_y + 5), layer="CENTER"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + w2 + 8, floor_y), p2=Point(fx + w2 + 8, top_y), label=f"H = {height_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx - w2, floor_y - 8), p2=Point(fx + w2, floor_y - 8), label=f"W = {length_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx - pd_r, ped_bot - 5), p2=Point(fx + pd_r, ped_bot - 5), label=f"Ø{pedestal_dia_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.texts.append(TextComponent(content="FRONT ELEVATION", position=Point(fx - w2, top_y + 10), height=3, layer="MTEXT"))
    title = TitleBlockData(drawing_title=f"Oval Pedestal Table {length_cm * 10:.0f}x{depth_cm * 10:.0f}x{height_cm * 10:.0f} mm",
        project=project, client=client, scale="1:5", revision="A", date=now,
        material_notes=[f"TABLE TOP — {mats.get('tabletop', 'Marble / engineered stone')}",
                        f"PEDESTAL — {mats.get('pedestal', 'Brushed stainless steel')}"])
    return DrawingModel(furniture_type="oval_pedestal_table", views=[tv, fv], title_block=title,
        known_dimensions={"length_cm": length_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm},
        estimated_components={"pedestal_diameter_cm": pedestal_dia_cm, "top_thickness_cm": top_thick_cm})


def build_console_table_model(
    length_cm: float = 120.0, depth_cm: float = 40.0, height_cm: float = 75.0,
    top_thick_cm: float = 2.5, leg_thick_cm: float = 4.0, leg_inset_cm: float = 2.0,
    client: str = "", project: str = "Furniture Shop Drawing",
) -> DrawingModel:
    """Build DrawingModel for a console/sofa table — 3 views."""
    now = datetime.now().strftime('%Y-%m-%d')
    sc = 0.4; w = length_cm * sc; d = depth_cm * sc; h = height_cm * sc
    tt = top_thick_cm * sc; lt = leg_thick_cm * sc; li = leg_inset_cm * sc
    w2, d2 = w / 2, d / 2; y_mid = 180.0; mats = {}
    tx, ty = 100.0, y_mid
    tv = View(name="TOP VIEW")
    tv.polygons.append(PolygonComponent(points=[Point(tx - w2, ty - d2), Point(tx + w2, ty - d2), Point(tx + w2, ty + d2), Point(tx - w2, ty + d2)], layer="OBJECT", name="tabletop"))
    for lx, ly in [(tx - w2 + li, ty - d2 + li), (tx + w2 - li - lt, ty - d2 + li), (tx - w2 + li, ty + d2 - li - lt), (tx + w2 - li - lt, ty + d2 - li - lt)]:
        tv.polygons.append(PolygonComponent(points=[Point(lx, ly), Point(lx + lt, ly), Point(lx + lt, ly + lt), Point(lx, ly + lt)], layer="HIDDEN", linetype="HIDDEN", name="leg"))
    tv.lines.append(LineComponent(start=Point(tx - w2 - 5, ty), end=Point(tx + w2 + 5, ty), layer="CENTER"))
    tv.lines.append(LineComponent(start=Point(tx, ty - d2 - 5), end=Point(tx, ty + d2 + 5), layer="CENTER"))
    tv.dimensions.append(DimensionComponent(p1=Point(tx - w2, ty + d2 + 6), p2=Point(tx + w2, ty + d2 + 6), label=f"W = {length_cm * 10:.0f} mm", layer="DIMENSION"))
    tv.dimensions.append(DimensionComponent(p1=Point(tx + w2 + 6, ty - d2), p2=Point(tx + w2 + 6, ty + d2), label=f"D = {depth_cm * 10:.0f} mm", layer="DIMENSION"))
    tv.texts.append(TextComponent(content="TOP VIEW", position=Point(tx - 15, ty + d2 + 22), height=3, layer="MTEXT"))
    fv = View(name="FRONT VIEW")
    fx, floor_y = 280.0, 40.0; top_y = floor_y + h; tab_bot = top_y - tt
    fv.polygons.append(PolygonComponent(points=[Point(fx - w2, tab_bot), Point(fx + w2, tab_bot), Point(fx + w2, top_y), Point(fx - w2, top_y)], layer="OBJECT", name="tabletop"))
    for lx in [fx - w2 + li, fx + w2 - li - lt]:
        fv.polygons.append(PolygonComponent(points=[Point(lx, floor_y), Point(lx + lt, floor_y), Point(lx + lt, tab_bot), Point(lx, tab_bot)], layer="OBJECT", name="leg"))
    fv.lines.append(LineComponent(start=Point(fx, floor_y - 5), end=Point(fx, top_y + 5), layer="CENTER"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + w2 + 8, floor_y), p2=Point(fx + w2 + 8, top_y), label=f"H = {height_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx - w2, floor_y - 8), p2=Point(fx + w2, floor_y - 8), label=f"W = {length_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx - w2, top_y + 10), height=3, layer="MTEXT"))
    sv = View(name="SIDE VIEW")
    sx = 365.0
    sv.polygons.append(PolygonComponent(points=[Point(sx - d2, tab_bot), Point(sx + d2, tab_bot), Point(sx + d2, top_y), Point(sx - d2, top_y)], layer="OBJECT", name="tabletop"))
    ly_l = sx - d2 + li
    sv.polygons.append(PolygonComponent(points=[Point(ly_l, floor_y), Point(ly_l + lt, floor_y), Point(ly_l + lt, tab_bot), Point(ly_l, tab_bot)], layer="OBJECT", name="leg"))
    sv.lines.append(LineComponent(start=Point(sx, floor_y - 5), end=Point(sx, top_y + 5), layer="CENTER"))
    sv.dimensions.append(DimensionComponent(p1=Point(sx + d2 + 6, floor_y), p2=Point(sx + d2 + 6, top_y), label=f"H = {height_cm * 10:.0f} mm", layer="DIMENSION"))
    sv.dimensions.append(DimensionComponent(p1=Point(sx - d2, floor_y - 8), p2=Point(sx + d2, floor_y - 8), label=f"D = {depth_cm * 10:.0f} mm", layer="DIMENSION"))
    sv.texts.append(TextComponent(content="SIDE VIEW", position=Point(sx - d2, top_y + 10), height=3, layer="MTEXT"))
    tb = TitleBlockData(drawing_title=f"Console Table {length_cm * 10:.0f}x{depth_cm * 10:.0f}x{height_cm * 10:.0f} mm",
        project=project, client=client, scale="1:2.5", revision="A", date=now)
    return DrawingModel(furniture_type="console_table", views=[tv, fv, sv], title_block=tb,
        known_dimensions={"length_cm": length_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm},
        estimated_components={"leg_thickness_cm": leg_thick_cm, "top_thickness_cm": top_thick_cm})


def build_office_desk_model(
    length_cm: float = 140.0, depth_cm: float = 60.0, height_cm: float = 75.0,
    top_thick_cm: float = 2.5, leg_thick_cm: float = 4.0, modesty_panel_h_cm: float = 15.0,
    leg_inset_cm: float = 2.0, client: str = "", project: str = "Furniture Shop Drawing",
) -> DrawingModel:
    """Build DrawingModel for an office desk with modesty panel — 3 views."""
    now = datetime.now().strftime('%Y-%m-%d')
    sc = 0.35; w = length_cm * sc; d = depth_cm * sc; h = height_cm * sc
    tt = top_thick_cm * sc; lt = leg_thick_cm * sc; mh = modesty_panel_h_cm * sc; li = leg_inset_cm * sc
    w2, d2 = w / 2, d / 2; y_mid = 180.0
    tx, ty = 100.0, y_mid
    tv = View(name="TOP VIEW")
    tv.polygons.append(PolygonComponent(points=[Point(tx - w2, ty - d2), Point(tx + w2, ty - d2), Point(tx + w2, ty + d2), Point(tx - w2, ty + d2)], layer="OBJECT", name="tabletop"))
    for lx, ly in [(tx - w2 + li, ty - d2 + li), (tx + w2 - li - lt, ty - d2 + li), (tx - w2 + li, ty + d2 - li - lt), (tx + w2 - li - lt, ty + d2 - li - lt)]:
        tv.polygons.append(PolygonComponent(points=[Point(lx, ly), Point(lx + lt, ly), Point(lx + lt, ly + lt), Point(lx, ly + lt)], layer="HIDDEN", name="leg"))
    tv.lines.append(LineComponent(start=Point(tx - w2 - 5, ty), end=Point(tx + w2 + 5, ty), layer="CENTER"))
    tv.lines.append(LineComponent(start=Point(tx, ty - d2 - 5), end=Point(tx, ty + d2 + 5), layer="CENTER"))
    tv.dimensions.append(DimensionComponent(p1=Point(tx - w2, ty + d2 + 6), p2=Point(tx + w2, ty + d2 + 6), label=f"W = {length_cm * 10:.0f} mm", layer="DIMENSION"))
    tv.dimensions.append(DimensionComponent(p1=Point(tx + w2 + 6, ty - d2), p2=Point(tx + w2 + 6, ty + d2), label=f"D = {depth_cm * 10:.0f} mm", layer="DIMENSION"))
    tv.texts.append(TextComponent(content="TOP VIEW", position=Point(tx - 15, ty + d2 + 22), height=3, layer="MTEXT"))
    fv = View(name="FRONT VIEW")
    fx, floor_y = 280.0, 40.0; top_y = floor_y + h; tab_bot = top_y - tt
    mp_top = tab_bot; mp_bot = mp_top - mh; panel_l = fx - w2 + li + lt; panel_r = fx + w2 - li - lt
    fv.polygons.append(PolygonComponent(points=[Point(fx - w2, tab_bot), Point(fx + w2, tab_bot), Point(fx + w2, top_y), Point(fx - w2, top_y)], layer="OBJECT", name="tabletop"))
    fv.hatches.append(HatchComponent(points=[Point(fx - w2, tab_bot), Point(fx + w2, tab_bot), Point(fx + w2, top_y), Point(fx - w2, top_y)], pattern="ANSI31", scale=0.5, layer="HATCH"))
    fv.polygons.append(PolygonComponent(points=[Point(panel_l, mp_bot), Point(panel_r, mp_bot), Point(panel_r, mp_top), Point(panel_l, mp_top)], layer="OBJECT", name="modesty_panel"))
    fv.hatches.append(HatchComponent(points=[Point(panel_l, mp_bot), Point(panel_r, mp_bot), Point(panel_r, mp_top), Point(panel_l, mp_top)], pattern="ANSI31", scale=0.4, layer="HATCH"))
    for lx in [fx - w2 + li, fx + w2 - li - lt]:
        fv.polygons.append(PolygonComponent(points=[Point(lx, floor_y), Point(lx + lt, floor_y), Point(lx + lt, tab_bot), Point(lx, tab_bot)], layer="OBJECT", name="leg"))
    fv.lines.append(LineComponent(start=Point(fx, floor_y - 5), end=Point(fx, top_y + 5), layer="CENTER"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + w2 + 8, floor_y), p2=Point(fx + w2 + 8, top_y), label=f"H = {height_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx - w2, floor_y - 8), p2=Point(fx + w2, floor_y - 8), label=f"W = {length_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(panel_l, mp_bot - 5), p2=Point(panel_r, mp_bot - 5), label=f"MH = {modesty_panel_h_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx - w2, top_y + 10), height=3, layer="MTEXT"))
    sv = View(name="SIDE VIEW")
    sx = 365.0
    sv.polygons.append(PolygonComponent(points=[Point(sx - d2, tab_bot), Point(sx + d2, tab_bot), Point(sx + d2, top_y), Point(sx - d2, top_y)], layer="OBJECT", name="tabletop"))
    sl = sx - d2 + li
    sv.polygons.append(PolygonComponent(points=[Point(sl, floor_y), Point(sl + lt, floor_y), Point(sl + lt, tab_bot), Point(sl, tab_bot)], layer="OBJECT", name="leg"))
    sv.lines.append(LineComponent(start=Point(sx - d2 + li + lt + 1, mp_bot), end=Point(sx + d2 - 2, mp_bot), layer="OBJECT"))
    sv.lines.append(LineComponent(start=Point(sx - d2 + li + lt + 1, mp_top), end=Point(sx + d2 - 2, mp_top), layer="OBJECT"))
    sv.lines.append(LineComponent(start=Point(sx, floor_y - 5), end=Point(sx, top_y + 5), layer="CENTER"))
    sv.dimensions.append(DimensionComponent(p1=Point(sx + d2 + 6, floor_y), p2=Point(sx + d2 + 6, top_y), label=f"H = {height_cm * 10:.0f} mm", layer="DIMENSION"))
    sv.dimensions.append(DimensionComponent(p1=Point(sx - d2, floor_y - 8), p2=Point(sx + d2, floor_y - 8), label=f"D = {depth_cm * 10:.0f} mm", layer="DIMENSION"))
    sv.texts.append(TextComponent(content="SIDE VIEW", position=Point(sx - d2, top_y + 10), height=3, layer="MTEXT"))
    tb = TitleBlockData(drawing_title=f"Office Desk {length_cm * 10:.0f}x{depth_cm * 10:.0f}x{height_cm * 10:.0f} mm",
        project=project, client=client, scale="1:3", revision="A", date=now)
    return DrawingModel(furniture_type="office_desk", views=[tv, fv, sv], title_block=tb,
        known_dimensions={"length_cm": length_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm},
        estimated_components={"leg_thickness_cm": leg_thick_cm, "modesty_panel_h_cm": modesty_panel_h_cm})


def build_asymmetric_pedestal_model(
    length_cm: float = 180.0, depth_cm: float = 90.0, height_cm: float = 75.0,
    top_thick_cm: float = 3.0, large_ped_dia_cm: float = 40.0, small_ped_dia_cm: float = 22.0,
    left_ped_x_cm: float = 30.0, right_ped_x_cm: float = -25.0, overhang_cm: float = 20.0,
    base_plate_cm: float = 5.0, client: str = "", project: str = "Furniture Shop Drawing",
    materials: Optional[Dict[str, str]] = None,
) -> DrawingModel:
    """Build DrawingModel for an asymmetric cylindrical pedestal dining table.
    
    Rectangular tabletop with two offset cylindrical pedestals of different
    diameters. Generates TOP VIEW, FRONT ELEVATION, and SIDE ELEVATION.
    All dimensions in cm.
    """
    now = datetime.now().strftime('%Y-%m-%d')
    sc = 0.35
    w = length_cm * sc
    d = depth_cm * sc
    h = height_cm * sc
    tt = top_thick_cm * sc
    lp_r = large_ped_dia_cm / 2 * sc
    sp_r = small_ped_dia_cm / 2 * sc
    lpx = left_ped_x_cm * sc
    rpx = right_ped_x_cm * sc
    bp = base_plate_cm * sc
    w2, d2 = w / 2, d / 2
    y_mid = 180.0
    mats = materials or {}

    # TOP VIEW
    tv = View(name="TOP VIEW")
    tv_cx, tv_cy = 100.0, y_mid
    tv.polygons.append(PolygonComponent(
        points=[Point(tv_cx - w2, tv_cy - d2), Point(tv_cx + w2, tv_cy - d2),
                Point(tv_cx + w2, tv_cy + d2), Point(tv_cx - w2, tv_cy + d2)],
        layer="OBJECT", name="tabletop"))
    tv.circles.append(CircleComponent(center=Point(tv_cx + lpx, tv_cy), radius=lp_r, layer="HIDDEN"))
    tv.circles.append(CircleComponent(center=Point(tv_cx + rpx, tv_cy), radius=sp_r, layer="HIDDEN"))
    ext = max(5.0, w2 * 0.1)
    tv.lines.append(LineComponent(start=Point(tv_cx - w2 - ext, tv_cy), end=Point(tv_cx + w2 + ext, tv_cy), layer="CENTER"))
    tv.lines.append(LineComponent(start=Point(tv_cx, tv_cy - d2 - ext), end=Point(tv_cx, tv_cy + d2 + ext), layer="CENTER"))
    tv.dimensions.append(DimensionComponent(p1=Point(tv_cx - w2, tv_cy + d2 + 6), p2=Point(tv_cx + w2, tv_cy + d2 + 6),
                                             label=f"W = {length_cm * 10:.0f} mm", layer="DIMENSION"))
    tv.dimensions.append(DimensionComponent(p1=Point(tv_cx + w2 + 6, tv_cy - d2), p2=Point(tv_cx + w2 + 6, tv_cy + d2),
                                             label=f"D = {depth_cm * 10:.0f} mm", layer="DIMENSION"))
    tv.texts.append(TextComponent(content=f"P1 Ø{large_ped_dia_cm * 10:.0f}", position=Point(tv_cx + lpx - 10, tv_cy - lp_r - 6), height=2, layer="DIMENSION"))
    tv.texts.append(TextComponent(content=f"P2 Ø{small_ped_dia_cm * 10:.0f}", position=Point(tv_cx + rpx - 10, tv_cy + sp_r + 8), height=2, layer="DIMENSION"))
    tv.texts.append(TextComponent(content="TOP VIEW", position=Point(tv_cx - 15, tv_cy + d2 + 22), height=3, layer="MTEXT"))

    # FRONT ELEVATION
    fv = View(name="FRONT ELEVATION")
    fx = 290.0
    floor_y = 40.0
    top_y = floor_y + h
    tab_bot = top_y - tt
    ped_height = tab_bot - floor_y - bp
    ped_bot = floor_y + bp

    fv.polygons.append(PolygonComponent(
        points=[Point(fx - w2, tab_bot), Point(fx + w2, tab_bot),
                Point(fx + w2, top_y), Point(fx - w2, top_y)],
        layer="OBJECT", name="tabletop"))
    fv.hatches.append(HatchComponent(
        points=[Point(fx - w2, tab_bot), Point(fx + w2, tab_bot),
                Point(fx + w2, top_y), Point(fx - w2, top_y)],
        pattern="ANSI31", scale=0.5, angle_deg=45, layer="HATCH"))
    # Large pedestal
    fv.polygons.append(PolygonComponent(
        points=[Point(fx + lpx - lp_r, ped_bot), Point(fx + lpx + lp_r, ped_bot),
                Point(fx + lpx + lp_r, tab_bot), Point(fx + lpx - lp_r, tab_bot)],
        layer="OBJECT", name="large_pedestal"))
    # Small pedestal
    fv.polygons.append(PolygonComponent(
        points=[Point(fx + rpx - sp_r, ped_bot), Point(fx + rpx + sp_r, ped_bot),
                Point(fx + rpx + sp_r, tab_bot), Point(fx + rpx - sp_r, tab_bot)],
        layer="OBJECT", name="small_pedestal"))
    # Hatches
    fv.hatches.append(HatchComponent(
        points=[Point(fx + lpx - lp_r, ped_bot), Point(fx + lpx + lp_r, ped_bot),
                Point(fx + lpx + lp_r, tab_bot), Point(fx + lpx - lp_r, tab_bot)],
        pattern="ANSI37", scale=0.3, layer="HATCH"))
    fv.hatches.append(HatchComponent(
        points=[Point(fx + rpx - sp_r, ped_bot), Point(fx + rpx + sp_r, ped_bot),
                Point(fx + rpx + sp_r, tab_bot), Point(fx + rpx - sp_r, tab_bot)],
        pattern="ANSI37", scale=0.3, layer="HATCH"))
    fv.lines.append(LineComponent(start=Point(fx, floor_y - 5), end=Point(fx, top_y + 5), layer="CENTER"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + w2 + 8, floor_y), p2=Point(fx + w2 + 8, top_y),
                                             label=f"H = {height_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx - w2, floor_y - 8), p2=Point(fx + w2, floor_y - 8),
                                             label=f"W = {length_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + lpx - lp_r, ped_bot - 6), p2=Point(fx + lpx + lp_r, ped_bot - 6),
                                             label=f"Ø{large_ped_dia_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + rpx - sp_r, ped_bot - 6), p2=Point(fx + rpx + sp_r, ped_bot - 6),
                                             label=f"Ø{small_ped_dia_cm * 10:.0f} mm", layer="DIMENSION"))
    fv.texts.append(TextComponent(content="FRONT ELEVATION", position=Point(fx - w2, top_y + 10), height=3, layer="MTEXT"))

    # SIDE ELEVATION
    sv = View(name="SIDE ELEVATION")
    sx = 365.0
    sv.polygons.append(PolygonComponent(
        points=[Point(sx - d2, tab_bot), Point(sx + d2, tab_bot),
                Point(sx + d2, top_y), Point(sx - d2, top_y)],
        layer="OBJECT", name="tabletop"))
    sv.hatches.append(HatchComponent(
        points=[Point(sx - d2, tab_bot), Point(sx + d2, tab_bot),
                Point(sx + d2, top_y), Point(sx - d2, top_y)],
        pattern="ANSI31", scale=0.5, angle_deg=45, layer="HATCH"))
    # Closer pedestal (small, solid)
    ped_w = max(sp_r * 2, 4.0)
    sv.polygons.append(PolygonComponent(
        points=[Point(sx - ped_w / 2, ped_bot), Point(sx + ped_w / 2, ped_bot),
                Point(sx + ped_w / 2, tab_bot), Point(sx - ped_w / 2, tab_bot)],
        layer="OBJECT", name="pedestal_closer"))
    # Further pedestal (large, hidden)
    far_w = max(lp_r * 2, 4.0)
    sv.polygons.append(PolygonComponent(
        points=[Point(sx - d2 * 0.3 - far_w / 2, ped_bot), Point(sx - d2 * 0.3 + far_w / 2, ped_bot),
                Point(sx - d2 * 0.3 + far_w / 2, tab_bot), Point(sx - d2 * 0.3 - far_w / 2, tab_bot)],
        layer="HIDDEN", linetype="HIDDEN", name="pedestal_further"))
    sv.lines.append(LineComponent(start=Point(sx, floor_y - 5), end=Point(sx, top_y + 5), layer="CENTER"))
    sv.dimensions.append(DimensionComponent(p1=Point(sx + d2 + 6, floor_y), p2=Point(sx + d2 + 6, top_y),
                                             label=f"H = {height_cm * 10:.0f} mm", layer="DIMENSION"))
    sv.dimensions.append(DimensionComponent(p1=Point(sx - d2, floor_y - 8), p2=Point(sx + d2, floor_y - 8),
                                             label=f"D = {depth_cm * 10:.0f} mm", layer="DIMENSION"))
    sv.texts.append(TextComponent(content="SIDE ELEVATION", position=Point(sx - d2, top_y + 10), height=3, layer="MTEXT"))

    title = TitleBlockData(
        drawing_title=f"Asymmetric Pedestal Dining Table {length_cm * 10:.0f}x{depth_cm * 10:.0f}x{height_cm * 10:.0f} mm",
        project=project, client=client, scale="1:5", revision="A",
        designer="AI CAD Drafter", date=now,
        material_notes=[
            f"TABLE TOP — {mats.get('tabletop', 'Marble / engineered stone')}",
            f"LARGE PEDESTAL (P1) — {mats.get('large_pedestal', 'Brushed stainless steel')}",
            f"SMALL PEDESTAL (P2) — {mats.get('small_pedestal', 'Brushed stainless steel')}",
            f"BASE PLATES — {mats.get('base_plate', 'Anti-sliding rubber pads')}",
        ],
        general_notes=["ALL DIMENSIONS IN MILLIMETERS (MM) UNLESS NOTED", "TOLERANCES: +/- 2mm UNLESS OTHERWISE SPECIFIED"],
    )

    return DrawingModel(
        furniture_type="asymmetric_pedestal_table", views=[tv, fv, sv], title_block=title,
        known_dimensions={"length_cm": length_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm},
        estimated_components={
            "large_pedestal_diameter_cm": large_ped_dia_cm,
            "small_pedestal_diameter_cm": small_ped_dia_cm,
            "top_thickness_cm": top_thick_cm,
        },
    )


def build_generic_model(lines=None, circles=None, rects=None, client="", project="Furniture Shop Drawing"):
    """Build a DrawingModel straight from raw detected pixel-space geometry,
    for furniture types with no dedicated template. Normalizes/scales the
    detected lines, circles and rectangles to fit the page instead of
    fabricating a round-pedestal-table shape that has nothing to do with
    what was actually drawn.
    """
    lines = lines or []
    circles = [c for c in (circles or []) if len(c) >= 3 and c[2] > 0]
    rects = rects or []
    n = datetime.now().strftime('%Y-%m-%d')

    xs, ys = [], []
    for (x1, y1), (x2, y2) in lines:
        xs += [x1, x2]; ys += [y1, y2]
    for cx, cy, r in circles:
        xs += [cx - r, cx + r]; ys += [cy - r, cy + r]
    for x1, y1, x2, y2 in rects:
        xs += [x1, x2]; ys += [y1, y2]

    view = View(name="DETECTED GEOMETRY")
    if not xs or not ys:
        tb = TitleBlockData("Generic 2D Furniture Drawing", project=project, client=client,
                             scale="1:1", revision="A", date=n)
        return DrawingModel(furniture_type="generic_2d_furniture", views=[view], title_block=tb)

    src_w = max(xs) - min(xs) or 1.0
    src_h = max(ys) - min(ys) or 1.0
    # Target footprint inside the page, leaving room for the title block/border.
    target_w, target_h = 320.0, 220.0
    sc = min(target_w / src_w, target_h / src_h)
    ox, oy = 50.0, 40.0

    def tx(x): return ox + (x - min(xs)) * sc
    def ty(y): return oy + (y - min(ys)) * sc

    for (x1, y1), (x2, y2) in lines:
        view.lines.append(LineComponent(start=Point(tx(x1), ty(y1)), end=Point(tx(x2), ty(y2)), layer="OBJECT"))
    for cx, cy, r in circles:
        view.circles.append(CircleComponent(center=Point(tx(cx), ty(cy)), radius=r * sc, layer="OBJECT"))
    for x1, y1, x2, y2 in rects:
        view.polygons.append(PolygonComponent(
            points=[Point(tx(x1), ty(y1)), Point(tx(x2), ty(y1)), Point(tx(x2), ty(y2)), Point(tx(x1), ty(y2))],
            layer="OBJECT", name="rect"))
    view.texts.append(TextComponent(content="DETECTED GEOMETRY (unclassified)",
                                     position=Point(ox, oy + target_h + 12), height=3, layer="MTEXT"))

    tb = TitleBlockData("Generic 2D Furniture Drawing", project=project, client=client,
                         scale="1:1", revision="A", date=n)
    return DrawingModel(furniture_type="generic_2d_furniture", views=[view], title_block=tb)


def build_reception_counter_model(w=180.0, h=110.0):
    sc = 0.3; fx = (420 - w * sc) / 2; fy, ty = 50.0, 50.0 + h * sc; n = datetime.now().strftime('%Y-%m-%d')
    fv = View(name="FRONT VIEW")
    fv.polygons.append(PolygonComponent(points=[Point(fx, fy), Point(fx+w*sc, fy), Point(fx+w*sc, ty), Point(fx, ty)], layer="OBJECT", name="counter_body"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx+w*sc+8, fy), p2=Point(fx+w*sc+8, ty), label=f"H = {h:g} cm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx, fy-8), p2=Point(fx+w*sc, fy-8), label=f"W = {w:g} cm", layer="DIMENSION"))
    fv.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx, ty+10), height=3, layer="MTEXT"))
    tb = TitleBlockData(f"Reception Counter {w:.0f}x{h:.0f}", project="Furniture Shop Drawing", scale="1:3", revision="A", date=n)
    return DrawingModel(furniture_type="reception_counter", views=[fv], title_block=tb,
        known_dimensions={"width_cm": w, "overall_height_cm": h})


def build_bed_headboard_model(w=180.0, h=60.0, d=5.0, client="", project="Furniture Shop Drawing"):
    sc = 0.4; w2 = w * sc; h2 = h * sc; fx = (420 - w2) / 2; floor_y = 30.0; top_y = floor_y + h2
    n = datetime.now().strftime('%Y-%m-%d')
    fv = View(name="FRONT VIEW")
    fv.polygons.append(PolygonComponent(points=[Point(fx, floor_y), Point(fx + w2, floor_y), Point(fx + w2, top_y), Point(fx, top_y)], layer="OBJECT", name="headboard"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx + w2 + 8, floor_y), p2=Point(fx + w2 + 8, top_y), label=f"H = {h:g} cm", layer="DIMENSION"))
    fv.dimensions.append(DimensionComponent(p1=Point(fx, floor_y - 8), p2=Point(fx + w2, floor_y - 8), label=f"W = {w:g} cm", layer="DIMENSION"))
    fv.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx, top_y + 10), height=3, layer="MTEXT"))
    tb = TitleBlockData(f"Bed Headboard {w:.0f}x{h:.0f}", project=project, client=client, scale="1:2.5", revision="A", date=n)
    return DrawingModel(furniture_type="bed_headboard", views=[fv], title_block=tb,
        known_dimensions={"width_cm": w, "overall_height_cm": h})
