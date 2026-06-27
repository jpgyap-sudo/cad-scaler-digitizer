"""
SVG Preview Generator for Parsed DXF Geometry
===============================================
Generates an SVG preview image from parsed DXF geometry data.
Used by the crawl processor to create visual previews of
crawled reference CAD files.
"""

from __future__ import annotations

import svgwrite


def generate_preview_svg(geometry: dict, output_path: str) -> None:
    """Generate an SVG preview from parsed DXF geometry.
    
    Args:
        geometry: Dict from parse_dxf() with 'bbox' and 'entities' keys
        output_path: Where to write the SVG file
    """
    bbox = geometry.get("bbox") or {"minX": 0, "minY": 0, "width": 1000, "height": 1000}
    min_x = bbox["minX"]
    min_y = bbox["minY"]
    width = max(bbox["width"], 1)
    height = max(bbox["height"], 1)

    canvas_w = 1000
    canvas_h = 1000
    scale = min(canvas_w / width, canvas_h / height) * 0.9
    offset_x = (canvas_w - width * scale) / 2
    offset_y = (canvas_h - height * scale) / 2

    def tx(x: float) -> float:
        return (x - min_x) * scale + offset_x

    def ty(y: float) -> float:
        # DXF Y is up; SVG Y is down.
        return canvas_h - ((y - min_y) * scale + offset_y)

    dwg = svgwrite.Drawing(output_path, size=(canvas_w, canvas_h))
    dwg.add(dwg.rect(insert=(0, 0), size=(canvas_w, canvas_h), fill="white"))

    for e in geometry.get("entities", []):
        t = e.get("type")

        if t == "line":
            x1, y1 = e["start"]
            x2, y2 = e["end"]
            dwg.add(dwg.line(
                (tx(x1), ty(y1)), (tx(x2), ty(y2)),
                stroke="black", stroke_width=1,
            ))

        elif t == "circle":
            cx, cy = e["center"]
            r = e["radius"] * scale
            dwg.add(dwg.circle(
                center=(tx(cx), ty(cy)), r=r,
                fill="none", stroke="black", stroke_width=1,
            ))

        elif t == "arc":
            cx, cy = e["center"]
            r = e["radius"] * scale
            dwg.add(dwg.circle(
                center=(tx(cx), ty(cy)), r=r,
                fill="none", stroke="gray", stroke_width=1,
            ))

        elif t == "polyline":
            pts = [(tx(x), ty(y)) for x, y in e.get("points", [])]
            if len(pts) >= 2:
                dwg.add(dwg.polyline(
                    pts,
                    fill="none", stroke="black", stroke_width=1,
                ))

        elif t == "text":
            x, y = e["insert"]
            dwg.add(dwg.text(
                e.get("text", ""),
                insert=(tx(x), ty(y)),
                font_size=12, fill="black",
            ))

    dwg.save()
