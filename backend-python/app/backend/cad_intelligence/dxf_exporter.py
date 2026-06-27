"""Score-weighted DXF export — assigns layer based on confidence level.
High confidence (>=0.75): OBJECT layer (solid)
Medium confidence (0.45-0.74): HIDDEN layer (dashed)
Low confidence (<0.45): ANNOTATION layer (thin/grey)
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import ezdxf
from .models import CadEntity


def entity_layer(e: CadEntity) -> str:
    """Determine DXF layer from entity confidence + source."""
    if e.source == "user_confirmed":
        return "OBJECT"
    if e.confidence >= 0.75:
        return "OBJECT"
    if e.confidence >= 0.45:
        return "HIDDEN"  # Dashed — less certain
    return "ANNOTATION"  # Thin/grey — speculative


def export_entities_to_dxf(
    entities: list[CadEntity],
    output_path: str,
    title: Optional[str] = None,
):
    """Export entities to DXF with confidence-based layer assignment.

    High confidence (>=0.75) → OBJECT (solid)
    Medium confidence (0.45-0.74) → HIDDEN (dashed)
    Low confidence (<0.45) → ANNOTATION (thin)
    """
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM

    # Add layers with appropriate linetypes
    for layer_def in [
        ("OBJECT", "Continuous"),
        ("HIDDEN", "DASHED"),
        ("ANNOTATION", "Continuous"),
        ("DIMENSIONS", "Continuous"),
        ("UNKNOWN", "Continuous"),
    ]:
        name, lt = layer_def
        if name not in doc.layers:
            doc.layers.new(name, dxfattribs={"linetype": lt})

    msp = doc.modelspace()

    for entity in entities:
        layer = entity_layer(entity)
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

    if title:
        msp.add_text(
            title,
            dxfattribs={"height": 50, "layer": "ANNOTATION"},
        ).set_placement((10, 10))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output_path)
    return output_path
