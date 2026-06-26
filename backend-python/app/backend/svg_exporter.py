"""
SVG Exporter — render DrawingModel to SVG for instant browser preview.

No dependencies beyond Python stdlib. Renders:
- Circles, polygons, lines with proper layers/colors
- Dimensions with text labels
- Leaders with arrowheads
- Title block with material notes
- Hatch patterns (simplified as filled polygons)

Layer colors (matching ezdxf layer definitions):
  OBJECT=black, DIMENSION=green, LEADER=cyan, CENTER=blue,
  MTEXT=#333, HATCH=gray, HIDDEN=#999, TITLE=magenta, BORDER=black

Y-AXIS NOTE:
  DrawingModel uses DXF convention: Y increases UPWARD (tabletop = high Y).
  SVG uses screen convention: Y increases DOWNWARD (top of page = Y=0).
  All geometry is Y-flipped via: svg_y = page_height - dxf_y
"""

from typing import Optional
from app.backend.drawing_model import DrawingModel, View

# Layer color map — AutoCAD classic style
LAYER_COLORS = {
    "OBJECT": "#1a1a1a",       # black object lines
    "DIMENSION": "#e6c700",    # yellow dimensions (AutoCAD classic)
    "LEADER": "#000000",       # black leader lines (matches reference)
    "CENTER": "#2563eb",       # blue centerlines
    "MTEXT": "#1a1a1a",        # black text
    "TEXT": "#1a1a1a",
    "HATCH": "#94a3b8",        # gray hatch
    "HIDDEN": "#94a3b8",
    "TITLE": "#7c3aed",
    "BORDER": "#1a1a1a",
}


def _color(layer: str, linetype: str = "CONTINUOUS") -> str:
    if linetype == "HIDDEN":
        return LAYER_COLORS.get("HIDDEN", "#999")
    return LAYER_COLORS.get(layer, "#1a1a1a")


def _svg_rect(x, y, w, h, stroke="#1a1a1a", fill="none", sw=1.0, dash=""):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" stroke="{stroke}" fill="{fill}" stroke-width="{sw}"{dash_attr}/>'


def _svg_circle(cx, cy, r, stroke="#1a1a1a", fill="none", sw=1.0, dash=""):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" stroke="{stroke}" fill="{fill}" stroke-width="{sw}"{dash_attr}/>'


def _svg_line(x1, y1, x2, y2, stroke="#1a1a1a", sw=1.0, dash=""):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"{dash_attr}/>'


def _svg_polygon(points, stroke="#1a1a1a", fill="none", sw=1.0, dash=""):
    pts_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in points)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polygon points="{pts_str}" stroke="{stroke}" fill="{fill}" stroke-width="{sw}"{dash_attr}/>'


def _svg_text(x, y, text, color="#1a1a1a", size=10, anchor="start"):
    # Escape XML special chars
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" font-family="monospace" font-size="{size}px" text-anchor="{anchor}">{safe}</text>'


def _render_view_flipped(view: View, page_h: float) -> str:
    """
    Render a single view with Y-axis flipped.
    DXF uses Y-up (high Y = top of drawing).
    SVG uses Y-down (low Y = top of screen).
    Conversion: svg_y = page_height - dxf_y
    """
    elements = []

    def fy(y): return page_h - y

    # Hatches first (background)
    for h in view.hatches:
        color = _color(h.layer)
        pts = [(p.x, fy(p.y)) for p in h.points]
        elements.append(_svg_polygon(pts, stroke=color, fill=f"{color}20", sw=0.5))

    # Circles
    for c in view.circles:
        color = _color(c.layer)
        elements.append(_svg_circle(c.center.x, fy(c.center.y), c.radius, stroke=color, sw=1.2))

    # Polygons
    for p in view.polygons:
        color = _color(p.layer, p.linetype)
        dash = "6,3" if p.linetype == "HIDDEN" else ""
        pts = [(pt.x, fy(pt.y)) for pt in p.points]
        elements.append(_svg_polygon(pts, stroke=color, sw=1.0, dash=dash))

    # Lines
    for l in view.lines:
        color = _color(l.layer)
        dash = "12,4,2,4" if l.layer == "CENTER" else ""
        elements.append(_svg_line(l.start.x, fy(l.start.y), l.end.x, fy(l.end.y),
                                   stroke=color, sw=0.8, dash=dash))

    # Dimensions
    for d in view.dimensions:
        color = _color("DIMENSION")
        p1y = fy(d.p1.y)
        p2y = fy(d.p2.y)
        elements.append(_svg_line(d.p1.x, p1y, d.p2.x, p2y, stroke=color, sw=0.6))
        mid_x = (d.p1.x + d.p2.x) / 2
        mid_y = (p1y + p2y) / 2
        label = d.label.replace("%%c", "\u00d8")
        # Offset label above the dimension line (subtract in SVG = move up visually)
        elements.append(_svg_text(mid_x, mid_y - 4, label, color=color, size=9, anchor="middle"))

    # Leaders
    for l in view.leaders:
        color = _color("LEADER")
        sx, sy = l.start.x, fy(l.start.y)
        ex, ey = l.end.x, fy(l.end.y)
        # Draw leader line
        elements.append(_svg_line(sx, sy, ex, ey, stroke=color, sw=0.8))
        # Small horizontal shoulder at text end (like AutoCAD leaders).
        # These are right-side callouts (start.x sits to the right of the
        # front view, see drawing_model.py's lx_text), so the shoulder and
        # text must grow further RIGHT, away from the object -- anchor="end"
        # here previously made long strings grow LEFT from this point,
        # shooting clean across the page into the TOP VIEW.
        shoulder = 5
        elements.append(_svg_line(sx, sy, sx + shoulder, sy, stroke=color, sw=0.8))
        # Arrowhead triangle at end point (pointing toward object)
        dx, dy = ex - sx, ey - sy
        mag = max(0.1, (dx**2 + dy**2)**0.5)
        ux, uy = dx / mag, dy / mag
        arrow = 3
        p1 = (ex - arrow * ux + 1.5 * uy, ey - arrow * uy - 1.5 * ux)
        p2 = (ex - arrow * ux - 1.5 * uy, ey - arrow * uy + 1.5 * ux)
        elements.append(_svg_polygon([(ex, ey), p1, p2], stroke=color, fill=color, sw=0.5))
        # Label after the shoulder, growing rightward into the margin
        elements.append(_svg_text(sx + shoulder + 2, sy + 3, l.text, color=color, size=7, anchor="start"))

    # Texts
    for t in view.texts:
        color = _color(t.layer)
        elements.append(_svg_text(t.position.x, fy(t.position.y), t.content,
                                   color=color, size=t.height * 3.5))

    return "\n  ".join(elements)


def render_svg(model: DrawingModel, width: Optional[int] = None, height: Optional[int] = None) -> str:
    """
    Render a DrawingModel to an SVG string.

    All view geometry is Y-flipped (DXF Y-up → SVG Y-down) so that the tabletop
    appears at the TOP of the preview and the base at the BOTTOM, matching the
    reference shop drawing orientation.

    Args:
        model: The drawing model to render
        width: SVG width in pixels (defaults to model.page_width * 3)
        height: SVG height in pixels (defaults to model.page_height * 3)

    Returns:
        Complete SVG document as a string
    """
    # Use a wider virtual canvas to fit the larger-scale drawing
    VW = max(model.page_width, 600.0)   # virtual width
    VH = max(model.page_height, 420.0)  # virtual height
    w = width or int(VW * 2)
    h = height or int(VH * 2)
    PH = VH  # page height used for Y-flip

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VW:.0f} {VH:.0f}" width="{w}" height="{h}">',
        f'<rect width="{VW:.0f}" height="{VH:.0f}" fill="white"/>',
    ]

    # === SHEET BORDER ===
    svg_parts.append(_svg_rect(0, 0, VW, VH,
                                stroke=LAYER_COLORS["BORDER"], sw=1.5))

    # === VIEWS — Y-flipped so DXF Y-up coords render correctly in SVG Y-down space ===
    for view in model.views:
        svg_parts.append(f'<!-- {view.name} -->')
        svg_parts.append(_render_view_flipped(view, PH))

    # === TITLE BLOCK (Bottom-Right, safely within VW/VH) ===
    tb = model.title_block
    tb_w, tb_h = 210, 70
    ox, oy = VW - tb_w - 8, VH - tb_h - 8
    svg_parts.append(_svg_rect(ox, oy, tb_w, tb_h, stroke=LAYER_COLORS["TITLE"], sw=1.0))
    row_h = tb_h / 5
    col_mid = ox + tb_w * 0.62
    for i in range(1, 5):
        yy = oy + row_h * i
        svg_parts.append(_svg_line(ox, yy, ox + tb_w, yy, stroke=LAYER_COLORS["TITLE"], sw=0.5))
    svg_parts.append(_svg_line(col_mid, oy, col_mid, oy + tb_h, stroke=LAYER_COLORS["TITLE"], sw=0.5))
    c = LAYER_COLORS["TITLE"]
    svg_parts.append(_svg_text(ox + 3, oy + 11,  f"DRAWN: {tb.designer[:25]}", c, 7))
    svg_parts.append(_svg_text(ox + 3, oy + 25,  f"SCALE: {tb.scale}", c, 7))
    svg_parts.append(_svg_text(col_mid + 3, oy + 11, f"DATE: {tb.date}", c, 7))
    svg_parts.append(_svg_text(col_mid + 3, oy + 25, f"REV: {tb.revision}", c, 7))
    svg_parts.append(_svg_text(ox + 3, oy + 39,  f"DRAWING: {tb.drawing_title[:40]}", c, 7))
    svg_parts.append(_svg_text(ox + 3, oy + 53,  f"PROJECT: {tb.project[:30]}", c, 7))
    svg_parts.append(_svg_text(col_mid + 3, oy + 53, f"CLIENT: {tb.client[:18] or '—'}", c, 7))

    # === MATERIAL NOTES (Bottom-Left, stacked upward from bottom) ===
    note_line_h = 8
    total_note_lines = len(tb.material_notes) + len(tb.general_notes) + 4  # +4 for headers
    ny_start = VH - 8
    nx = 8
    cur_y = ny_start
    svg_parts.append(_svg_text(nx, cur_y, "MATERIAL / FINISH NOTES:", LAYER_COLORS["MTEXT"], 8))
    cur_y += note_line_h
    for i, note in enumerate(tb.material_notes):
        svg_parts.append(_svg_text(nx + 4, cur_y, f"{i+1}. {note[:65]}", LAYER_COLORS["MTEXT"], 6.5))
        cur_y += note_line_h - 1
    cur_y += 4
    svg_parts.append(_svg_text(nx, cur_y, "GENERAL NOTES:", LAYER_COLORS["MTEXT"], 8))
    cur_y += note_line_h
    for i, note in enumerate(tb.general_notes):
        svg_parts.append(_svg_text(nx + 4, cur_y, f"{i+1}. {note[:65]}", LAYER_COLORS["MTEXT"], 6.5))
        cur_y += note_line_h - 1

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


# ===== Public API =====

def drawing_to_svg(model: DrawingModel, width: int = 1260, height: int = 891) -> str:
    """Convenience: render DrawingModel to SVG string."""
    return render_svg(model, width, height)
