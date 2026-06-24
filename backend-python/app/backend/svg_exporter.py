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
"""

from typing import Optional
from app.backend.drawing_model import DrawingModel, View

# Layer color map
LAYER_COLORS = {
    "OBJECT": "#1a1a1a",
    "DIMENSION": "#16a34a",
    "LEADER": "#0891b2",
    "CENTER": "#2563eb",
    "MTEXT": "#334155",
    "TEXT": "#475569",
    "HATCH": "#94a3b8",
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


def _render_view(view: View) -> str:
    """Render a single view to SVG elements."""
    elements = []

    # Hatches first (background)
    for h in view.hatches:
        color = _color(h.layer)
        pts = [(p.x, p.y) for p in h.points]
        elements.append(_svg_polygon(pts, stroke=color, fill=f"{color}20", sw=0.5))

    # Circles
    for c in view.circles:
        color = _color(c.layer)
        elements.append(_svg_circle(c.center.x, c.center.y, c.radius, stroke=color, sw=1.2))

    # Polygons
    for p in view.polygons:
        color = _color(p.layer, p.linetype)
        dash = "6,3" if p.linetype == "HIDDEN" else ""
        pts = [(pt.x, pt.y) for pt in p.points]
        elements.append(_svg_polygon(pts, stroke=color, sw=1.0, dash=dash))

    # Lines
    for l in view.lines:
        color = _color(l.layer)
        dash = "12,4,2,4" if l.layer == "CENTER" else ""
        elements.append(_svg_line(l.start.x, l.start.y, l.end.x, l.end.y, stroke=color, sw=0.8, dash=dash))

    # Dimensions
    for d in view.dimensions:
        color = _color("DIMENSION")
        elements.append(_svg_line(d.p1.x, d.p1.y, d.p2.x, d.p2.y, stroke=color, sw=0.6))
        mid_x, mid_y = (d.p1.x + d.p2.x) / 2, (d.p1.y + d.p2.y) / 2
        label = d.label.replace("%%c", "Ø")
        elements.append(_svg_text(mid_x, mid_y - 4, label, color=color, size=9, anchor="middle"))

    # Leaders
    for l in view.leaders:
        color = _color("LEADER")
        elements.append(_svg_line(l.start.x, l.start.y, l.end.x, l.end.y, stroke=color, sw=0.8))
        # Arrowhead triangle
        dx, dy = l.end.x - l.start.x, l.end.y - l.start.y
        mag = max(0.1, (dx**2 + dy**2)**0.5)
        ux, uy = dx / mag, dy / mag
        arrow = 4
        p1 = (l.end.x - arrow * ux + 2 * uy, l.end.y - arrow * uy - 2 * ux)
        p2 = (l.end.x - arrow * ux - 2 * uy, l.end.y - arrow * uy + 2 * ux)
        elements.append(_svg_polygon([(l.end.x, l.end.y), p1, p2], stroke=color, fill=color, sw=0.5))
        elements.append(_svg_text(l.start.x + 5, l.start.y - 3, l.text, color=color, size=8))

    # Texts
    for t in view.texts:
        color = _color(t.layer)
        elements.append(_svg_text(t.position.x, t.position.y, t.content, color=color, size=t.height * 3.5))

    return "\n  ".join(elements)


def render_svg(model: DrawingModel, width: Optional[int] = None, height: Optional[int] = None) -> str:
    """
    Render a DrawingModel to an SVG string.

    Args:
        model: The drawing model to render
        width: SVG width in pixels (defaults to model.page_width * 3)
        height: SVG height in pixels (defaults to model.page_height * 3)

    Returns:
        Complete SVG document as a string
    """
    w = width or int(model.page_width * 3)
    h = height or int(model.page_height * 3)
    scale_x = w / model.page_width
    scale_y = h / model.page_height

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {model.page_width:.0f} {model.page_height:.0f}" width="{w}" height="{h}">',
        f'<rect width="{model.page_width:.0f}" height="{model.page_height:.0f}" fill="white"/>',
    ]

    # === SHEET BORDER ===
    svg_parts.append(_svg_rect(0, 0, model.page_width, model.page_height,
                                stroke=LAYER_COLORS["BORDER"], sw=1.5))

    # === VIEWS ===
    for view in model.views:
        svg_parts.append(f'<!-- {view.name} -->')
        svg_parts.append(_render_view(view))

    # === TITLE BLOCK (Bottom-Right) ===
    tb = model.title_block
    tb_w, tb_h = 180, 60
    ox, oy = model.page_width - tb_w - 10, 10
    svg_parts.append(_svg_rect(ox, oy, tb_w, tb_h, stroke=LAYER_COLORS["TITLE"], sw=1.0))
    # Dividers
    row_h = tb_h / 4
    col_mid = ox + tb_w * 0.65
    for i in range(1, 4):
        y = oy + row_h * i
        svg_parts.append(_svg_line(ox, y, ox + tb_w, y, stroke=LAYER_COLORS["TITLE"], sw=0.5))
    svg_parts.append(_svg_line(col_mid, oy, col_mid, oy + tb_h, stroke=LAYER_COLORS["TITLE"], sw=0.5))
    # TB text
    c = LAYER_COLORS["TITLE"]
    svg_parts.append(_svg_text(ox + 3, oy + tb_h - 4, f"PROJECT: {tb.project[:30]}", c, 7))
    svg_parts.append(_svg_text(col_mid + 3, oy + tb_h - 4, f"CLIENT: {tb.client[:20] or '  '}", c, 7))
    svg_parts.append(_svg_text(ox + 3, oy + tb_h - row_h - 4, f"DRAWING: {tb.drawing_title[:50]}", c, 7))
    svg_parts.append(_svg_text(ox + 3, oy + tb_h - 2*row_h - 4, f"SCALE: {tb.scale}  DATE: {tb.date}", c, 7))
    svg_parts.append(_svg_text(col_mid + 3, oy + tb_h - 2*row_h - 4, f"REV: {tb.revision}", c, 7))
    svg_parts.append(_svg_text(ox + 3, oy + 4, f"DRAWN: {tb.designer[:25]}", c, 7))

    # === MATERIAL NOTES (Top-Left) ===
    nx, ny = 12, model.page_height - 18
    svg_parts.append(_svg_text(nx, ny, "MATERIAL / FINISH NOTES:", LAYER_COLORS["MTEXT"], 9))
    for i, note in enumerate(tb.material_notes):
        svg_parts.append(_svg_text(nx, ny - 6 - i * 5, f"  {i+1}. {note[:60]}", LAYER_COLORS["MTEXT"], 7))

    # === GENERAL NOTES ===
    gy = ny - 6 - len(tb.material_notes) * 5 - 6
    svg_parts.append(_svg_text(nx, gy, "GENERAL NOTES:", LAYER_COLORS["MTEXT"], 9))
    for i, note in enumerate(tb.general_notes):
        svg_parts.append(_svg_text(nx, gy - 6 - i * 5, f"  {i+1}. {note[:60]}", LAYER_COLORS["MTEXT"], 7))

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


# ===== Public API =====

def drawing_to_svg(model: DrawingModel, width: int = 1260, height: int = 891) -> str:
    """Convenience: render DrawingModel to SVG string."""
    return render_svg(model, width, height)
