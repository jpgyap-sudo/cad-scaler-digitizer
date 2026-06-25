"""
Intermediate Drawing Model — JSON representation between AI pipeline and CAD output.

Inspired by:
- Microsoft maker.js: JSON-based 2D drawing model with paths, models, chains
- build123d: Operator-driven component composition
- CADAM: Parametric controls for post-generation adjustment

Architecture:
  Image → AI pipeline → DrawingModel (JSON) → SVG | DXF | PDF

Benefits:
- SVG preview in browser (no matplotlib/ezdxf needed)
- Parametric adjustment without re-running AI
- Multi-format export from single source
- Validation before DXF generation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Literal
import json
import math


# ===== Primitive Types =====

@dataclass
class Point:
    x: float
    y: float

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    @classmethod
    def from_tuple(cls, t: Tuple[float, float]) -> "Point":
        return cls(x=t[0], y=t[1])


@dataclass
class CircleComponent:
    """Circle primitive."""
    type: Literal["circle"] = "circle"
    center: Point = field(default_factory=lambda: Point(0, 0))
    radius: float = 0.0
    layer: str = "OBJECT"


@dataclass
class PolygonComponent:
    """Closed polygon (LWPOLYLINE)."""
    type: Literal["polygon"] = "polygon"
    points: List[Point] = field(default_factory=list)
    layer: str = "OBJECT"
    name: str = ""  # e.g. "tabletop", "neck", "pedestal_body", "base_foot"
    linetype: str = "CONTINUOUS"  # CONTINUOUS or HIDDEN


@dataclass
class LineComponent:
    """Single line segment."""
    type: Literal["line"] = "line"
    start: Point = field(default_factory=lambda: Point(0, 0))
    end: Point = field(default_factory=lambda: Point(0, 0))
    layer: str = "OBJECT"


@dataclass
class TextComponent:
    """Single-line text annotation."""
    type: Literal["text"] = "text"
    content: str = ""
    position: Point = field(default_factory=lambda: Point(0, 0))
    height: float = 3.0
    layer: str = "MTEXT"


@dataclass
class DimensionComponent:
    """Dimension with label."""
    type: Literal["dimension"] = "dimension"
    p1: Point = field(default_factory=lambda: Point(0, 0))
    p2: Point = field(default_factory=lambda: Point(0, 0))
    label: str = ""
    layer: str = "DIMENSION"


@dataclass
class LeaderComponent:
    """Leader line with arrowhead and text."""
    type: Literal["leader"] = "leader"
    start: Point = field(default_factory=lambda: Point(0, 0))
    end: Point = field(default_factory=lambda: Point(0, 0))
    text: str = ""
    layer: str = "LEADER"


@dataclass
class HatchComponent:
    """Hatch fill for a polygon."""
    type: Literal["hatch"] = "hatch"
    points: List[Point] = field(default_factory=list)
    pattern: str = "ANSI31"  # ANSI31, ANSI37, etc.
    scale: float = 0.3
    angle_deg: float = 45.0
    layer: str = "HATCH"


# ===== View =====

@dataclass
class View:
    """A single view (top, front, side) within the drawing."""
    name: str  # e.g. "TOP VIEW", "FRONT VIEW"
    circles: List[CircleComponent] = field(default_factory=list)
    polygons: List[PolygonComponent] = field(default_factory=list)
    lines: List[LineComponent] = field(default_factory=list)
    texts: List[TextComponent] = field(default_factory=list)
    dimensions: List[DimensionComponent] = field(default_factory=list)
    leaders: List[LeaderComponent] = field(default_factory=list)
    hatches: List[HatchComponent] = field(default_factory=list)


# ===== Title Block =====

@dataclass
class TitleBlockData:
    """Title block metadata."""
    drawing_title: str = "Furniture Drawing"
    project: str = ""
    client: str = ""
    scale: str = "1:1"
    revision: str = "A"
    designer: str = "AI CAD Drafter"
    date: str = ""
    material_notes: List[str] = field(default_factory=list)
    general_notes: List[str] = field(default_factory=list)


# ===== Full Drawing Model =====

@dataclass
class DrawingModel:
    """Complete furniture shop drawing."""
    furniture_type: str = ""
    page_width: float = 420.0  # A3 landscape
    page_height: float = 297.0
    scale: float = 0.5  # 1:2
    views: List[View] = field(default_factory=list)
    title_block: TitleBlockData = field(default_factory=TitleBlockData)
    known_dimensions: Dict[str, float] = field(default_factory=dict)
    estimated_components: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        def point_list(pts):
            return [{"x": p.x, "y": p.y} for p in pts]

        return {
            "furniture_type": self.furniture_type,
            "page_width": self.page_width,
            "page_height": self.page_height,
            "scale": self.scale,
            "views": [
                {
                    "name": v.name,
                    "circles": [{"center": {"x": c.center.x, "y": c.center.y},
                                 "radius": c.radius, "layer": c.layer} for c in v.circles],
                    "polygons": [{"points": point_list(p.points), "layer": p.layer,
                                  "name": p.name, "linetype": p.linetype} for p in v.polygons],
                    "lines": [{"start": {"x": l.start.x, "y": l.start.y},
                               "end": {"x": l.end.x, "y": l.end.y},
                               "layer": l.layer} for l in v.lines],
                    "texts": [{"content": t.content, "position": {"x": t.position.x, "y": t.position.y},
                               "height": t.height, "layer": t.layer} for t in v.texts],
                    "dimensions": [{"p1": {"x": d.p1.x, "y": d.p1.y},
                                    "p2": {"x": d.p2.x, "y": d.p2.y},
                                    "label": d.label, "layer": d.layer} for d in v.dimensions],
                    "leaders": [{"start": {"x": l.start.x, "y": l.start.y},
                                 "end": {"x": l.end.x, "y": l.end.y},
                                 "text": l.text, "layer": l.layer} for l in v.leaders],
                    "hatches": [{"points": point_list(h.points), "pattern": h.pattern,
                                 "scale": h.scale, "angle_deg": h.angle_deg,
                                 "layer": h.layer} for h in v.hatches],
                } for v in self.views
            ],
            "title_block": {
                "drawing_title": self.title_block.drawing_title,
                "project": self.title_block.project,
                "client": self.title_block.client,
                "scale": self.title_block.scale,
                "revision": self.title_block.revision,
                "designer": self.title_block.designer,
                "date": self.title_block.date,
                "material_notes": self.title_block.material_notes,
                "general_notes": self.title_block.general_notes,
            },
            "known_dimensions": self.known_dimensions,
            "estimated_components": self.estimated_components,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DrawingModel":
        """Deserialize from JSON dict."""
        def to_point(d):
            return Point(x=d["x"], y=d["y"])

        views = []
        for vd in data.get("views", []):
            views.append(View(
                name=vd["name"],
                circles=[CircleComponent(center=to_point(c["center"]),
                         radius=c["radius"], layer=c.get("layer", "OBJECT"))
                         for c in vd.get("circles", [])],
                polygons=[PolygonComponent(
                    points=[to_point(p) for p in p["points"]],
                    layer=p.get("layer", "OBJECT"),
                    name=p.get("name", ""),
                    linetype=p.get("linetype", "CONTINUOUS"))
                    for p in vd.get("polygons", [])],
                lines=[LineComponent(start=to_point(l["start"]),
                       end=to_point(l["end"]), layer=l.get("layer", "OBJECT"))
                       for l in vd.get("lines", [])],
                texts=[TextComponent(content=t["content"],
                       position=to_point(t["position"]),
                       height=t.get("height", 3), layer=t.get("layer", "MTEXT"))
                       for t in vd.get("texts", [])],
                dimensions=[DimensionComponent(p1=to_point(d["p1"]),
                            p2=to_point(d["p2"]), label=d["label"],
                            layer=d.get("layer", "DIMENSION"))
                            for d in vd.get("dimensions", [])],
                leaders=[LeaderComponent(start=to_point(l["start"]),
                         end=to_point(l["end"]), text=l["text"],
                         layer=l.get("layer", "LEADER"))
                         for l in vd.get("leaders", [])],
                hatches=[HatchComponent(points=[to_point(p) for p in h["points"]],
                         pattern=h.get("pattern", "ANSI31"),
                         scale=h.get("scale", 0.3),
                         angle_deg=h.get("angle_deg", 45),
                         layer=h.get("layer", "HATCH"))
                         for h in vd.get("hatches", [])],
            ))

        tb = data.get("title_block", {})
        return cls(
            furniture_type=data.get("furniture_type", ""),
            page_width=data.get("page_width", 420),
            page_height=data.get("page_height", 297),
            scale=data.get("scale", 0.5),
            views=views,
            title_block=TitleBlockData(
                drawing_title=tb.get("drawing_title", ""),
                project=tb.get("project", ""),
                client=tb.get("client", ""),
                scale=tb.get("scale", "1:1"),
                revision=tb.get("revision", "A"),
                designer=tb.get("designer", ""),
                date=tb.get("date", ""),
                material_notes=tb.get("material_notes", []),
                general_notes=tb.get("general_notes", []),
            ),
            known_dimensions=data.get("known_dimensions", {}),
            estimated_components=data.get("estimated_components", {}),
        )


# ===== Helper: Build drawing model for round pedestal table =====

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
) -> DrawingModel:
    """
    Build a complete DrawingModel for a round pedestal table matching
    professional shop drawing format.

    Components (top to bottom):
      - Tabletop slab          : top_dia_cm wide, top_thick_cm tall
      - Metal collar plate     : collar_dia_cm wide, ~10% height  (matte hairline black steel)
      - Neck connector ring    : neck_dia_cm wide, connects collar to pedestal
      - Textured pedestal cone : widens from neck_dia → base_dia over ~75% height
      - Base glide plate       : base_dia_cm wide, base_thick_cm tall (anti-sliding glides)

    Scale: 2 units per cm  (sc=2, so 80cm top = 160px wide — fills sheet properly)
    """
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d')

    # ── Scale: 1 unit = 0.5 cm  →  sc=2 means 1 cm = 2 drawing-units
    sc = 2.0

    # Derived pixel sizes
    r_top    = top_dia_cm    / 2 * sc   # tabletop half-width
    r_collar = collar_dia_cm / 2 * sc   # collar half-width
    r_neck   = neck_dia_cm   / 2 * sc   # neck half-width
    r_base   = base_dia_cm   / 2 * sc   # pedestal base half-width

    thick_top  = top_thick_cm  * sc     # tabletop thickness
    thick_base = base_thick_cm * sc     # base plate thickness

    # Distribute remaining height between collar, pedestal cone, and nothing else
    remaining_h   = max(1.0, height_cm - top_thick_cm - base_thick_cm)
    collar_h_cm   = remaining_h * 0.14   # ~10cm for 70cm table
    ped_h_cm      = remaining_h * 0.86   # rest is pedestal cone

    collar_h = collar_h_cm * sc
    ped_h    = ped_h_cm    * sc
    h_total  = height_cm * sc

    # Anchor: base sits at floor_y, tabletop top at floor_y + h_total
    floor_y  = 30.0
    top_y    = floor_y + h_total           # top of tabletop
    tab_bot  = top_y   - thick_top         # bottom of tabletop slab
    col_top  = tab_bot                     # collar starts here
    col_bot  = col_top  - collar_h         # collar ends here
    ped_bot  = col_bot  - ped_h            # pedestal cone ends here (= top of base)
    base_bot = floor_y                     # bottom of base plate

    # X centre of front view
    fx = 160.0

    # Leader X start (right side callouts)
    lx_start = fx + r_top + 12
    lx_text  = lx_start + 5

    # ===== TOP VIEW (small, top-left) =====
    top_view = View(name="TOP VIEW")
    tv_cx, tv_cy = 55.0, top_y - r_top * 0.5   # small circle top-left
    tv_r = top_dia_cm / 2 * 0.6   # smaller scale for top view

    top_view.circles.append(CircleComponent(center=Point(tv_cx, tv_cy), radius=tv_r, layer="OBJECT"))
    # Radial grain lines
    for i in range(8):
        angle = 2 * math.pi * i / 8
        x1 = tv_cx + tv_r * 0.15 * math.cos(angle)
        y1 = tv_cy + tv_r * 0.15 * math.sin(angle)
        x2 = tv_cx + tv_r * math.cos(angle)
        y2 = tv_cy + tv_r * math.sin(angle)
        top_view.lines.append(LineComponent(start=Point(x1, y1), end=Point(x2, y2), layer="HATCH"))
    # Centerlines
    ext = max(4.0, tv_r * 0.12)
    top_view.lines.append(LineComponent(start=Point(tv_cx - tv_r - ext, tv_cy),
                                         end=Point(tv_cx + tv_r + ext, tv_cy), layer="CENTER"))
    top_view.lines.append(LineComponent(start=Point(tv_cx, tv_cy - tv_r - ext),
                                         end=Point(tv_cx, tv_cy + tv_r + ext), layer="CENTER"))
    # Diameter dim on top view
    top_view.dimensions.append(DimensionComponent(
        p1=Point(tv_cx - tv_r, tv_cy + tv_r + ext),
        p2=Point(tv_cx + tv_r, tv_cy + tv_r + ext),
        label=f"\u00d8{top_dia_cm:g}", layer="DIMENSION"))
    top_view.texts.append(TextComponent(content="TOP VIEW",
        position=Point(tv_cx - 12, tv_cy - tv_r - ext - 3), height=2.5, layer="MTEXT"))

    # ===== FRONT VIEW =====
    front_view = View(name="FRONT VIEW")

    # 1. Tabletop slab (wide flat rectangle)
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - r_top, top_y), Point(fx + r_top, top_y),
                Point(fx + r_top, tab_bot), Point(fx - r_top, tab_bot)],
        layer="OBJECT", name="tabletop"))
    # Woodgrain hatch on tabletop
    front_view.hatches.append(HatchComponent(
        points=[Point(fx - r_top, top_y), Point(fx + r_top, top_y),
                Point(fx + r_top, tab_bot), Point(fx - r_top, tab_bot)],
        pattern="ANSI31", scale=0.8, angle_deg=45, layer="HATCH"))

    # 2. Metal collar plate (wide, sits directly under tabletop)
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - r_collar, col_top), Point(fx + r_collar, col_top),
                Point(fx + r_collar, col_bot), Point(fx - r_collar, col_bot)],
        layer="OBJECT", name="collar_plate"))

    # 3. Neck connector (narrow rectangle, same width as neck)
    #    (In reference this is implied by the collar narrowing toward pedestal)
    #    We draw a thin visible rectangle between collar and pedestal
    neck_h_px = collar_h * 0.3
    neck_top_y = col_bot
    neck_bot_y = col_bot - neck_h_px
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - r_neck, neck_top_y), Point(fx + r_neck, neck_top_y),
                Point(fx + r_neck, neck_bot_y), Point(fx - r_neck, neck_bot_y)],
        layer="OBJECT", name="neck_ring"))

    # 4. Textured pedestal cone (trapezoidal: narrow at top, wide at bottom)
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - r_neck, neck_bot_y), Point(fx + r_neck, neck_bot_y),
                Point(fx + r_base, ped_bot), Point(fx - r_base, ped_bot)],
        layer="OBJECT", name="pedestal_body"))
    # Cross-hatch texture on pedestal
    front_view.hatches.append(HatchComponent(
        points=[Point(fx - r_neck, neck_bot_y), Point(fx + r_neck, neck_bot_y),
                Point(fx + r_base, ped_bot), Point(fx - r_base, ped_bot)],
        pattern="ANSI37", scale=0.5, angle_deg=45, layer="HATCH"))

    # 5. Base glide plate (wide flat plate at floor)
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - r_base, ped_bot), Point(fx + r_base, ped_bot),
                Point(fx + r_base, base_bot), Point(fx - r_base, base_bot)],
        layer="OBJECT", name="base_plate"))

    # ── CENTRELINE ──────────────────────────────────────────────────────────
    front_view.lines.append(LineComponent(
        start=Point(fx, base_bot - 6), end=Point(fx, top_y + 6), layer="CENTER"))

    # ── DIMENSIONS ──────────────────────────────────────────────────────────
    dim_x_left = fx - r_top - 8   # left-side dimension chain X

    # Overall height (left side, spanning full height)
    front_view.dimensions.append(DimensionComponent(
        p1=Point(dim_x_left - 10, base_bot),
        p2=Point(dim_x_left - 10, top_y),
        label=f"{height_cm:g}", layer="DIMENSION"))

    # Tabletop thickness (left side)
    front_view.dimensions.append(DimensionComponent(
        p1=Point(dim_x_left, tab_bot),
        p2=Point(dim_x_left, top_y),
        label=f"{top_thick_cm:g}", layer="DIMENSION"))

    # Sub-height: collar + neck section
    front_view.dimensions.append(DimensionComponent(
        p1=Point(dim_x_left, neck_bot_y),
        p2=Point(dim_x_left, tab_bot),
        label=f"{collar_h_cm:.0f}", layer="DIMENSION"))

    # Sub-height: pedestal cone + base
    front_view.dimensions.append(DimensionComponent(
        p1=Point(dim_x_left, base_bot),
        p2=Point(dim_x_left, neck_bot_y),
        label=f"{ped_h_cm:.0f}", layer="DIMENSION"))

    # Top diameter (top of drawing)
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx - r_top, top_y + 6),
        p2=Point(fx + r_top, top_y + 6),
        label=f"{top_dia_cm:g}", layer="DIMENSION"))

    # Collar diameter (inside drawing)
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx - r_collar, col_top - 4),
        p2=Point(fx + r_collar, col_top - 4),
        label=f"{collar_dia_cm:g}", layer="DIMENSION"))

    # Neck / pedestal top diameter
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx - r_neck, neck_bot_y - 4),
        p2=Point(fx + r_neck, neck_bot_y - 4),
        label=f"{neck_dia_cm:g}", layer="DIMENSION"))

    # Pedestal base / base plate diameter
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx - r_base, ped_bot - 4),
        p2=Point(fx + r_base, ped_bot - 4),
        label=f"{base_dia_cm:g}", layer="DIMENSION"))

    # ── LEADER ANNOTATIONS (right side) ─────────────────────────────────────
    # 1. Collar plate → "Dia XXcm Metal base plate with screw holes - matte black steel"
    col_mid_y = (col_top + col_bot) / 2
    front_view.leaders.append(LeaderComponent(
        start=Point(lx_text, col_mid_y),
        end=Point(fx + r_collar, col_mid_y),
        text=f"Dia {collar_dia_cm:.0f}cm Metal base plate with screw holes- matte black steel",
        layer="LEADER"))

    # 2. Neck ring → "Matte hairline black steel"
    front_view.leaders.append(LeaderComponent(
        start=Point(lx_text, neck_top_y),
        end=Point(fx + r_neck, neck_top_y),
        text="Matte hairline black steel",
        layer="LEADER"))

    # 3. Pedestal top → "Dia XXcm Metal base plate - matte black steel"
    front_view.leaders.append(LeaderComponent(
        start=Point(lx_text, neck_bot_y),
        end=Point(fx + r_neck, neck_bot_y),
        text=f"Dia {base_dia_cm:.0f}cm Metal base plate - matte black steel",
        layer="LEADER"))

    # 4. Pedestal body midpoint → "Black hammered textured - apply PU coating"
    ped_mid_y = (neck_bot_y + ped_bot) / 2
    front_view.leaders.append(LeaderComponent(
        start=Point(lx_text, ped_mid_y),
        end=Point(fx + (r_neck + r_base) / 2, ped_mid_y),
        text="Black hammered textured- apply a layer of PU coating for paint protection",
        layer="LEADER"))

    # 5. Base plate → "Black table base with anti-sliding glides"
    base_mid_y = (ped_bot + base_bot) / 2
    front_view.leaders.append(LeaderComponent(
        start=Point(lx_text, base_mid_y),
        end=Point(fx + r_base, base_mid_y),
        text="Black table base with anti-sliding glides",
        layer="LEADER"))

    # View label
    front_view.texts.append(TextComponent(
        content="FRONT VIEW",
        position=Point(fx - r_top, base_bot - 12),
        height=3, layer="MTEXT"))

    # ===== TITLE BLOCK =====
    title = TitleBlockData(
        drawing_title=f"Round Pedestal Table \u00d8{top_dia_cm:.0f} x H{height_cm:.0f}",
        project=project,
        client=client,
        scale="1:2",
        revision="A",
        designer="AI CAD Drafter",
        date=now,
        material_notes=material_notes or [
            "WOOD TOP \u2014 Solid hardwood, stained finish",
            "PEDESTAL BASE \u2014 Black hammered textured metal, PU coat",
            "COLLAR PLATE \u2014 Matte hairline black steel",
            "BASE GLIDES \u2014 Anti-sliding rubber feet",
        ],
        general_notes=[
            "ALL DIMENSIONS IN CENTIMETERS (CM) UNLESS NOTED",
            "TOLERANCES: +/- 2mm UNLESS OTHERWISE SPECIFIED",
        ],
    )

    return DrawingModel(
        furniture_type="round_pedestal_table",
        views=[top_view, front_view],
        title_block=title,
        known_dimensions={"top_diameter_cm": top_dia_cm, "overall_height_cm": height_cm},
        estimated_components={
            "pedestal_diameter_cm": base_dia_cm,
            "neck_diameter_cm": neck_dia_cm,
            "top_thickness_cm": top_thick_cm,
        },
    )

    # ===== TOP VIEW =====
    top_view = View(name="TOP VIEW")
    top_view.circles.append(CircleComponent(center=Point(cx, cy), radius=r_px, layer="OBJECT"))

    # Radial sunburst lines
    for i in range(8):
        angle = 2 * math.pi * i / 8
        x1, y1 = cx + r_px * 0.15 * math.cos(angle), cy + r_px * 0.15 * math.sin(angle)
        x2, y2 = cx + r_px * math.cos(angle), cy + r_px * math.sin(angle)
        top_view.lines.append(LineComponent(start=Point(x1, y1), end=Point(x2, y2), layer="HATCH"))

    # Centerlines
    ext = max(4.0, r_px * 0.1)
    top_view.lines.append(LineComponent(start=Point(cx - r_px - ext, cy), end=Point(cx + r_px + ext, cy), layer="CENTER"))
    top_view.lines.append(LineComponent(start=Point(cx, cy - r_px - ext), end=Point(cx, cy + r_px + ext), layer="CENTER"))

    # Top dim
    top_view.dimensions.append(DimensionComponent(
        p1=Point(cx - r_px, cy), p2=Point(cx + r_px, cy),
        label=f"%%c{top_dia_cm:g} cm", layer="DIMENSION"))

    top_view.texts.append(TextComponent(content="TOP VIEW", position=Point(cx - 15, cy + r_px + ext + 5), height=3, layer="MTEXT"))

    # Top wood grain hatch (approximate as polygon)
    hatch_pts = [Point(cx + r_px * math.cos(2 * math.pi * i / 64),
                       cy + r_px * math.sin(2 * math.pi * i / 64)) for i in range(64)]
    top_view.hatches.append(HatchComponent(points=hatch_pts, pattern="ANSI31", scale=0.3, angle_deg=45, layer="HATCH"))

    # ===== FRONT VIEW =====
    front_view = View(name="FRONT VIEW")

    # Tabletop
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - r_px, top_y), Point(fx + r_px, top_y),
                Point(fx + r_px, neck_top_y), Point(fx - r_px, neck_top_y)],
        layer="OBJECT", name="tabletop"))

    # Neck
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - nr_px, neck_top_y), Point(fx + nr_px, neck_top_y),
                Point(fx + nr_px, neck_bot_y), Point(fx - nr_px, neck_bot_y)],
        layer="OBJECT", name="neck_ring"))

    # Pedestal body
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - nr_px, neck_bot_y), Point(fx + nr_px, neck_bot_y),
                Point(fx + br_px, ped_bot_y), Point(fx - br_px, ped_bot_y)],
        layer="OBJECT", name="pedestal_body"))

    # Base foot (estimated, dashed)
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - br_px, ped_bot_y), Point(fx + br_px, ped_bot_y),
                Point(fx + br_px, bot_y), Point(fx - br_px, bot_y)],
        layer="OBJECT", name="base_foot", linetype="HIDDEN"))

    # Base dim
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx - br_px, bot_y - 5), p2=Point(fx + br_px, bot_y - 5),
        label=f"%%c{base_dia_cm:g} cm", layer="DIMENSION"))

    # Centerline
    front_view.lines.append(LineComponent(start=Point(fx, bot_y - 5), end=Point(fx, top_y + 5), layer="CENTER"))

    # Height dim
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx + r_px + 10, bot_y), p2=Point(fx + r_px + 10, top_y),
        label=f"H = {height_cm:g} cm", layer="DIMENSION"))

    # Leaders
    front_view.leaders.append(LeaderComponent(
        start=Point(fx + br_px + 15, (neck_top_y + top_y) / 2),
        end=Point(fx + r_px, top_y), text="SOLID WOOD TOP", layer="LEADER"))
    front_view.leaders.append(LeaderComponent(
        start=Point(fx + br_px + 15, (neck_bot_y + ped_bot_y) / 2),
        end=Point(fx + br_px, (neck_bot_y + ped_bot_y) / 2),
        text="TEXTURED PEDESTAL BASE", layer="LEADER"))

    # Front view label
    front_view.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx - 20, top_y + 10), height=3, layer="MTEXT"))

    # Base estimated label
    front_view.texts.append(TextComponent(content="(EST.)", position=Point(fx - br_px - 15, (ped_bot_y + bot_y) / 2), height=2, layer="MTEXT"))

    # Column hatch
    front_view.hatches.append(HatchComponent(
        points=[Point(fx - nr_px, neck_bot_y), Point(fx + nr_px, neck_bot_y),
                Point(fx + br_px, ped_bot_y), Point(fx - br_px, ped_bot_y)],
        pattern="ANSI37", scale=0.3, layer="HATCH"))

    # ===== TITLE BLOCK =====
    title = TitleBlockData(
        drawing_title=f"Round Pedestal Table %%c{top_dia_cm:.0f} x H{height_cm:.0f}",
        project=project,
        client=client,
        scale=f"1:{int(2)}",
        revision="A",
        designer="AI CAD Drafter",
        date=now,
        material_notes=material_notes or [
            "WOOD TOP — Solid hardwood, stained finish",
            "PEDESTAL BASE — Textured hammered metal, black powder coat",
            "NECK RING — Brushed stainless steel",
        ],
        general_notes=[
            "ALL DIMENSIONS IN CENTIMETERS (CM) UNLESS NOTED",
            "TOLERANCES: +/- 2mm UNLESS OTHERWISE SPECIFIED",
        ],
    )

    return DrawingModel(
        furniture_type="round_pedestal_table",
        views=[top_view, front_view],
        title_block=title,
        known_dimensions={"top_diameter_cm": top_dia_cm, "overall_height_cm": height_cm},
        estimated_components={
            "pedestal_diameter_cm": base_dia_cm,
            "neck_diameter_cm": neck_dia_cm,
            "top_thickness_cm": top_thick_cm,
        },
    )


def build_rectangular_table_model(
    width_cm: float = 120.0,
    depth_cm: float = 80.0,
    height_cm: float = 70.0,
    leg_thickness_cm: float = 6.0,
    client: str = "",
    project: str = "Furniture Shop Drawing",
) -> DrawingModel:
    """Build a complete DrawingModel for a rectangular table."""
    sc = 0.4
    w = width_cm * sc
    d = depth_cm * sc
    h = height_cm * sc
    w2, d2 = w / 2, d / 2
    ox, y_mid = 100.0, 180.0
    lt = leg_thickness_cm * sc
    fx = 280.0
    floor_y = 30.0
    top_y = floor_y + h
    top_thick = max(lt * 0.8, 2.0)
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d')

    # ===== TOP VIEW =====
    top_view = View(name="TOP VIEW")
    top_view.polygons.append(PolygonComponent(
        points=[Point(ox - w2, y_mid - d2), Point(ox + w2, y_mid - d2),
                Point(ox + w2, y_mid + d2), Point(ox - w2, y_mid + d2)],
        layer="OBJECT", name="tabletop"))
    for lx, ly in [(ox - w2, y_mid - d2), (ox + w2 - lt, y_mid - d2),
                   (ox - w2, y_mid + d2 - lt), (ox + w2 - lt, y_mid + d2 - lt)]:
        top_view.polygons.append(PolygonComponent(
            points=[Point(lx, ly), Point(lx + lt, ly),
                    Point(lx + lt, ly + lt), Point(lx, ly + lt)],
            layer="HIDDEN", linetype="HIDDEN", name="leg_footprint"))
    top_view.lines.append(LineComponent(start=Point(ox - w2 - 5, y_mid), end=Point(ox + w2 + 5, y_mid), layer="CENTER"))
    top_view.lines.append(LineComponent(start=Point(ox, y_mid - d2 - 5), end=Point(ox, y_mid + d2 + 5), layer="CENTER"))
    top_view.dimensions.append(DimensionComponent(
        p1=Point(ox - w2, y_mid + d2 + 6), p2=Point(ox + w2, y_mid + d2 + 6),
        label=f"W = {width_cm:g} cm", layer="DIMENSION"))
    top_view.dimensions.append(DimensionComponent(
        p1=Point(ox + w2 + 6, y_mid - d2), p2=Point(ox + w2 + 6, y_mid + d2),
        label=f"D = {depth_cm:g} cm", layer="DIMENSION"))
    top_view.texts.append(TextComponent(content="TOP VIEW", position=Point(ox - 15, y_mid + d2 + 22), height=3, layer="MTEXT"))

    # ===== FRONT VIEW =====
    front_view = View(name="FRONT VIEW")
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - w2, top_y - top_thick), Point(fx + w2, top_y - top_thick),
                Point(fx + w2, top_y), Point(fx - w2, top_y)],
        layer="OBJECT", name="tabletop"))
    front_view.hatches.append(HatchComponent(
        points=[Point(fx - w2, top_y - top_thick), Point(fx + w2, top_y - top_thick),
                Point(fx + w2, top_y), Point(fx - w2, top_y)],
        pattern="ANSI31", scale=0.5, layer="HATCH"))
    leg_y_top = top_y - top_thick
    for lx in [fx - w2, fx + w2 - lt]:
        front_view.polygons.append(PolygonComponent(
            points=[Point(lx, floor_y), Point(lx + lt, floor_y),
                    Point(lx + lt, leg_y_top), Point(lx, leg_y_top)],
            layer="OBJECT", name="leg"))
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx + w2 + 8, floor_y), p2=Point(fx + w2 + 8, top_y),
        label=f"H = {height_cm:g} cm", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx - w2, floor_y - 8), p2=Point(fx + w2, floor_y - 8),
        label=f"W = {width_cm:g} cm", layer="DIMENSION"))
    front_view.lines.append(LineComponent(start=Point(fx, floor_y - 5), end=Point(fx, top_y + 5), layer="CENTER"))
    front_view.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx - w2, top_y + 10), height=3, layer="MTEXT"))

    title = TitleBlockData(
        drawing_title=f"Rectangular Table {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
        project=project, client=client,
        scale=f"1:{int(2.5)}", revision="A",
        designer="AI CAD Drafter", date=now,
        material_notes=["WOOD TOP — Solid hardwood, stained finish"],
        general_notes=["ALL DIMENSIONS IN CENTIMETERS (CM)", "TOLERANCES: +/- 2mm"],
    )

    return DrawingModel(
        furniture_type="rectangular_table",
        views=[top_view, front_view],
        title_block=title,
        known_dimensions={"width_cm": width_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm},
        estimated_components={"leg_thickness_cm": leg_thickness_cm},
    )


def build_cabinet_model(
    width_cm: float = 100.0,
    depth_cm: float = 50.0,
    height_cm: float = 180.0,
    client: str = "",
    project: str = "Furniture Shop Drawing",
) -> DrawingModel:
    """Build DrawingModel for a cabinet/wardrobe."""
    sc = 0.3
    w = width_cm * sc
    h = height_cm * sc
    fx = (420 - w) / 2
    floor_y = 50.0
    top_y = floor_y + h
    w2 = w / 2
    margin = w * 0.05
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d')

    front_view = View(name="FRONT VIEW")
    # Outer body
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx, floor_y), Point(fx + w, floor_y),
                Point(fx + w, top_y), Point(fx, top_y)],
        layer="OBJECT", name="cabinet_body"))
    # Double doors
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx + margin, floor_y + margin), Point(fx + w2 - 2, floor_y + margin),
                Point(fx + w2 - 2, top_y - margin), Point(fx + margin, top_y - margin)],
        layer="OBJECT", name="door_left"))
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx + w2 + 2, floor_y + margin), Point(fx + w - margin, floor_y + margin),
                Point(fx + w - margin, top_y - margin), Point(fx + w2 + 2, top_y - margin)],
        layer="OBJECT", name="door_right"))
    # Handles
    mid_y = (top_y + floor_y) / 2
    front_view.lines.append(LineComponent(start=Point(fx + w2 - 6, mid_y - 5), end=Point(fx + w2 - 6, mid_y + 5), layer="OBJECT"))
    front_view.lines.append(LineComponent(start=Point(fx + w2 + 6, mid_y - 5), end=Point(fx + w2 + 6, mid_y + 5), layer="OBJECT"))
    # Dimensions
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx + w + 8, floor_y), p2=Point(fx + w + 8, top_y),
        label=f"H = {height_cm:g} cm", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx, floor_y - 8), p2=Point(fx + w, floor_y - 8),
        label=f"W = {width_cm:g} cm", layer="DIMENSION"))
    front_view.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx, top_y + 10), height=3, layer="MTEXT"))

    title = TitleBlockData(
        drawing_title=f"Cabinet {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
        project=project, client=client, scale=f"1:{int(3.3)}", revision="A",
        designer="AI CAD Drafter", date=now,
        general_notes=["ALL DIMENSIONS IN CENTIMETERS (CM)"],
    )

    return DrawingModel(
        furniture_type="cabinet",
        views=[front_view], title_block=title,
        known_dimensions={"width_cm": width_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm},
    )


def build_sofa_model(
    width_cm: float = 200.0,
    depth_cm: float = 80.0,
    height_cm: float = 85.0,
    client: str = "",
    project: str = "Furniture Shop Drawing",
) -> DrawingModel:
    """Build DrawingModel for a sofa."""
    sc = 0.3
    w = width_cm * sc
    h = height_cm * sc
    fx = (420 - w) / 2
    floor_y = 50.0
    top_y = floor_y + h
    seat_y = floor_y + h * 0.55
    arm_h = h * 0.4
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d')

    front_view = View(name="FRONT VIEW")
    # Seat base
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx, floor_y), Point(fx + w, floor_y),
                Point(fx + w, seat_y), Point(fx, seat_y)],
        layer="OBJECT", name="seat_base"))
    # Backrest
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx, seat_y), Point(fx + w, seat_y),
                Point(fx + w, top_y - arm_h), Point(fx, top_y - arm_h)],
        layer="OBJECT", name="backrest"))
    # Armrests
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx - 5, seat_y - 5), Point(fx + 10, seat_y - 5),
                Point(fx + 10, top_y), Point(fx - 5, top_y)],
        layer="OBJECT", name="arm_left"))
    front_view.polygons.append(PolygonComponent(
        points=[Point(fx + w - 10, seat_y - 5), Point(fx + w + 5, seat_y - 5),
                Point(fx + w + 5, top_y), Point(fx + w - 10, top_y)],
        layer="OBJECT", name="arm_right"))
    # Dimensions
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx + w + 8, floor_y), p2=Point(fx + w + 8, top_y),
        label=f"H = {height_cm:g} cm", layer="DIMENSION"))
    front_view.dimensions.append(DimensionComponent(
        p1=Point(fx, floor_y - 8), p2=Point(fx + w, floor_y - 8),
        label=f"W = {width_cm:g} cm", layer="DIMENSION"))
    front_view.texts.append(TextComponent(content="FRONT VIEW", position=Point(fx, top_y + 10), height=3, layer="MTEXT"))

    title = TitleBlockData(
        drawing_title=f"Sofa {width_cm:.0f}x{depth_cm:.0f}x{height_cm:.0f}",
        project=project, client=client, scale=f"1:{int(3.3)}", revision="A",
        designer="AI CAD Drafter", date=now,
        general_notes=["ALL DIMENSIONS IN CENTIMETERS (CM)"],
    )

    return DrawingModel(
        furniture_type="sofa",
        views=[front_view], title_block=title,
        known_dimensions={"width_cm": width_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm},
    )


def build_coffee_table_model(w=100.0, d=60.0, h=45.0) -> DrawingModel:
    sc, cx, ym = 0.6, 100.0, 190.0; r = min(w, d) / 2 * sc
    from datetime import datetime as dt; n = dt.now().strftime('%Y-%m-%d')
    tv = View(name="TOP VIEW")
    tv.circles.append(CircleComponent(center=Point(cx, ym), radius=r, layer="OBJECT"))
    tv.lines.append(LineComponent(Point(cx-r-5, ym), Point(cx+r+5, ym), "CENTER"))
    tv.lines.append(LineComponent(Point(cx, ym-r-5), Point(cx, ym+r+5), "CENTER"))
    tv.dimensions.append(DimensionComponent(Point(cx-r, ym), Point(cx+r, ym), f"%%c{min(w,d):g} cm", "DIMENSION"))
    tv.texts.append(TextComponent("TOP VIEW", Point(cx-10, ym+r+10), 3, "MTEXT"))
    tb = TitleBlockData(f"Coffee Table {w:.0f}x{d:.0f}x{h:.0f}", project="Furniture Shop Drawing", scale="1:2", revision="A", date=n)
    return DrawingModel("coffee_table", [tv], tb, {"width_cm": w, "depth_cm": d, "overall_height_cm": h})


def build_dining_chair_model(w=45.0, h=90.0) -> DrawingModel:
    sc, w2 = 0.5, w * 0.5 * 0.5; fx = (420 - w * 0.5) / 2
    fy, ty = 50.0, 50.0 + h * 0.5; sy = fy + h * 0.5 * 0.5
    ref_point = Point(fx, ty+10)
    from datetime import datetime as dt; n = dt.now().strftime('%Y-%m-%d')
    fv = View(name="FRONT VIEW")
    p1 = Point(fx, sy); p2 = Point(fx+w*0.5, sy); p3 = Point(fx+w*0.5, ty); p4 = Point(fx, ty)
    fv.polygons.append(PolygonComponent([p1, p2, p3, p4], "OBJECT", "backrest"))
    p5 = Point(fx, fy); p6 = Point(fx+w*0.5, fy); p7 = Point(fx+w*0.5, sy); p8 = Point(fx, sy)
    fv.polygons.append(PolygonComponent([p5, p6, p7, p8], "OBJECT", "seat"))
    fv.dimensions.append(DimensionComponent(Point(fx+w*0.5+8, fy), Point(fx+w*0.5+8, ty), f"H = {h:g} cm", "DIMENSION"))
    fv.texts.append(TextComponent("FRONT VIEW", ref_point, 3, "MTEXT"))
    tb = TitleBlockData(f"Dining Chair {w:.0f}x{h:.0f}", project="Furniture Shop Drawing", scale="1:2", revision="A", date=n)
    return DrawingModel("dining_chair", [fv], tb, {"width_cm": w, "overall_height_cm": h})


def build_wardrobe_model(w=120.0, d=60.0, h=200.0) -> DrawingModel:
    return build_cabinet_model(w, d, h)


def build_reception_counter_model(w=180.0, h=110.0) -> DrawingModel:
    sc = 0.3; fx = (420 - w * sc) / 2; fy, ty = 50.0, 50.0 + h * sc
    from datetime import datetime as dt; n = dt.now().strftime('%Y-%m-%d')
    fv = View(name="FRONT VIEW")
    fv.polygons.append(PolygonComponent([Point(fx, fy), Point(fx+w*sc, fy), Point(fx+w*sc, ty), Point(fx, ty)], "OBJECT", "counter_body"))
    fv.dimensions.append(DimensionComponent(Point(fx+w*sc+8, fy), Point(fx+w*sc+8, ty), f"H = {h:g} cm", "DIMENSION"))
    fv.dimensions.append(DimensionComponent(Point(fx, fy-8), Point(fx+w*sc, fy-8), f"W = {w:g} cm", "DIMENSION"))
    fv.texts.append(TextComponent("FRONT VIEW", Point(fx, ty+10), 3, "MTEXT"))
    tb = TitleBlockData(f"Reception Counter {w:.0f}x{h:.0f}", project="Furniture Shop Drawing", scale="1:3", revision="A", date=n)
    return DrawingModel("reception_counter", [fv], tb, {"width_cm": w, "overall_height_cm": h})
