from pathlib import Path
import ezdxf

from app.cad_kernel.entities.primitives import RectangleEntity, CircleEntity, TextEntity, CylinderEntity, BoxEntity


class DXFExporter:
    def export(self, document, path: str):
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()

        for layer in document.layers.values():
            if layer.name not in doc.layers:
                doc.layers.new(layer.name, dxfattribs={"color": layer.color})

        for e in document.entities.values():
            if isinstance(e, RectangleEntity):
                pts = [(p.x, p.y) for p in e.corners()]
                msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": e.layer})

            elif isinstance(e, CircleEntity):
                msp.add_circle((e.center.x, e.center.y), e.radius, dxfattribs={"layer": e.layer})

            elif isinstance(e, TextEntity):
                msp.add_text(e.text, dxfattribs={"height": e.height, "layer": e.layer}).set_placement((e.insert.x, e.insert.y))

            elif isinstance(e, CylinderEntity):
                # top-view footprint
                msp.add_circle((e.center.x, e.center.y), e.diameter / 2, dxfattribs={"layer": e.layer})

            elif isinstance(e, BoxEntity):
                # top-view footprint
                x, y = e.center.x, e.center.y
                pts = [
                    (x - e.length/2, y - e.depth/2),
                    (x + e.length/2, y - e.depth/2),
                    (x + e.length/2, y + e.depth/2),
                    (x - e.length/2, y + e.depth/2),
                ]
                msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": e.layer})

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(path)
        return path
