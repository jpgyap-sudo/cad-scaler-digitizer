from __future__ import annotations
from pathlib import Path
import ezdxf
from .models import CadEntity

def export_entities_to_dxf(entities: list[CadEntity], output_path: str):
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM

    for layer in ["OBJECT", "DIMENSIONS", "ANNOTATION", "UNKNOWN"]:
        if layer not in doc.layers:
            doc.layers.add(layer)

    msp = doc.modelspace()

    for entity in entities:
        layer = entity.layer or "OBJECT"
        g = entity.geometry
        if entity.type == "line":
            msp.add_line(g["start"], g["end"], dxfattribs={"layer": layer})
        elif entity.type == "circle":
            msp.add_circle(g["center"], g["radius"], dxfattribs={"layer": layer})
        elif entity.type == "text":
            msp.add_text(
                g.get("text", ""),
                dxfattribs={"height": g.get("height", 25), "layer": layer},
            ).set_placement(g.get("insert", (0, 0)))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output_path)
    return output_path
