"""
DXF Parser for Crawled Reference Files
========================================
Parses DXF files downloaded by the crawler, extracting geometry data
for indexing in Qdrant and generating SVG previews.

This module reads existing DXF files (not to be confused with the
DXF generation pipeline in app.backend.dxf_exporter).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import ezdxf


@dataclass
class BBox:
    min_x: float = 1e18
    min_y: float = 1e18
    max_x: float = -1e18
    max_y: float = -1e18

    def add(self, x: float, y: float):
        self.min_x = min(self.min_x, x)
        self.min_y = min(self.min_y, y)
        self.max_x = max(self.max_x, x)
        self.max_y = max(self.max_y, y)

    def as_dict(self):
        if self.min_x > self.max_x:
            return None
        return {
            "minX": self.min_x,
            "minY": self.min_y,
            "maxX": self.max_x,
            "maxY": self.max_y,
            "width": self.max_x - self.min_x,
            "height": self.max_y - self.min_y,
        }


def parse_dxf(path: str) -> dict[str, Any]:
    """Parse a DXF file and return geometry as a serializable dict.
    
    Returns:
        dict with keys: version, units, counts, bbox, entities
    """
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    entities: list[dict[str, Any]] = []
    bbox = BBox()

    counts = {
        "entityCount": 0,
        "lineCount": 0,
        "circleCount": 0,
        "arcCount": 0,
        "polylineCount": 0,
        "textCount": 0,
    }

    for e in msp:
        dxftype = e.dxftype()
        counts["entityCount"] += 1

        try:
            layer = e.dxf.layer
        except Exception:
            layer = "0"

        if dxftype == "LINE":
            start = e.dxf.start
            end = e.dxf.end
            bbox.add(start.x, start.y)
            bbox.add(end.x, end.y)
            counts["lineCount"] += 1
            entities.append({
                "type": "line",
                "layer": layer,
                "start": [start.x, start.y],
                "end": [end.x, end.y],
            })

        elif dxftype == "CIRCLE":
            center = e.dxf.center
            radius = float(e.dxf.radius)
            bbox.add(center.x - radius, center.y - radius)
            bbox.add(center.x + radius, center.y + radius)
            counts["circleCount"] += 1
            entities.append({
                "type": "circle",
                "layer": layer,
                "center": [center.x, center.y],
                "radius": radius,
            })

        elif dxftype == "ARC":
            center = e.dxf.center
            radius = float(e.dxf.radius)
            bbox.add(center.x - radius, center.y - radius)
            bbox.add(center.x + radius, center.y + radius)
            counts["arcCount"] += 1
            entities.append({
                "type": "arc",
                "layer": layer,
                "center": [center.x, center.y],
                "radius": radius,
                "startAngle": float(e.dxf.start_angle),
                "endAngle": float(e.dxf.end_angle),
            })

        elif dxftype in {"LWPOLYLINE", "POLYLINE"}:
            points = []
            if dxftype == "LWPOLYLINE":
                for p in e.get_points():
                    x, y = float(p[0]), float(p[1])
                    bbox.add(x, y)
                    points.append([x, y])
            else:
                for v in e.vertices:
                    x, y = float(v.dxf.location.x), float(v.dxf.location.y)
                    bbox.add(x, y)
                    points.append([x, y])

            counts["polylineCount"] += 1
            entities.append({
                "type": "polyline",
                "layer": layer,
                "points": points,
                "closed": bool(e.closed) if hasattr(e, "closed") else False,
            })

        elif dxftype in {"TEXT", "MTEXT"}:
            counts["textCount"] += 1
            text = e.dxf.text if dxftype == "TEXT" else e.text
            insert = e.dxf.insert
            bbox.add(insert.x, insert.y)
            entities.append({
                "type": "text",
                "layer": layer,
                "text": text,
                "insert": [insert.x, insert.y],
            })

    b = bbox.as_dict()
    return {
        "version": "0.1",
        "units": str(doc.units),
        "counts": counts,
        "bbox": b,
        "entities": entities,
    }
