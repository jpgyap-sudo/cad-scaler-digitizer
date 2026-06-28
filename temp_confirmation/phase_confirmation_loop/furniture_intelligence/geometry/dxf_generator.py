from __future__ import annotations
from pathlib import Path
try:
    import ezdxf
except Exception:  # installed via requirements.txt in real app
    ezdxf = None
from furniture_intelligence.schemas.furniture_analysis import ApprovedTemplate


def _layers(doc):
    for name, color in [('OUTLINE',7),('CENTER',3),('DIM',2),('HIDDEN',8),('SECTION',1),('TEXT',7),('MATERIAL_STONE',9),('MATERIAL_METAL',6)]:
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={'color': color})


def _ellipse(msp, center, major, ratio, layer):
    msp.add_ellipse(center=center, major_axis=(major,0), ratio=ratio, dxfattribs={'layer': layer})


def generate_dxf(approved: ApprovedTemplate, out_path: str) -> str:
    p = approved.parameters_mm
    L = p.get('overall_length', 1200)
    D = p.get('overall_depth', 700)
    H = p.get('overall_height', 360)
    T = p.get('top_thickness', 22)
    bowl = p.get('bowl_diameter', 220)
    base_bot = p.get('base_bottom_diameter', 520)
    base_top = p.get('base_top_diameter', 320)
    base_h = p.get('base_height', H-T)

    if ezdxf is None:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text('DXF generation requires ezdxf. Run: pip install ezdxf\n', encoding='utf-8')
        return out_path
    doc = ezdxf.new('R2010')
    _layers(doc)
    msp = doc.modelspace()

    # Top view
    ox, oy = 0, 0
    msp.add_text('TOP VIEW / PLAN', height=35, dxfattribs={'layer':'TEXT'}).set_placement((ox-L/2, oy+D/2+80))
    _ellipse(msp, (ox, oy, 0), L/2, D/L, 'MATERIAL_STONE')
    msp.add_circle((ox, oy, 0), bowl/2, dxfattribs={'layer':'MATERIAL_METAL'})
    msp.add_circle((ox, oy, 0), bowl*0.36, dxfattribs={'layer':'OUTLINE'})
    msp.add_line((-L/2-80,0),(L/2+80,0), dxfattribs={'layer':'CENTER'})
    msp.add_line((0,-D/2-80),(0,D/2+80), dxfattribs={'layer':'CENTER'})

    # Front elevation
    fx, fy = 0, -900
    msp.add_text('FRONT ELEVATION', height=35, dxfattribs={'layer':'TEXT'}).set_placement((fx-L/2, fy+H+100))
    msp.add_lwpolyline([(fx-L/2,fy+H),(fx+L/2,fy+H),(fx+L/2,fy+H-T),(fx-L/2,fy+H-T),(fx-L/2,fy+H)], dxfattribs={'layer':'MATERIAL_STONE'})
    msp.add_lwpolyline([(fx-base_top/2,fy+base_h),(fx+base_top/2,fy+base_h),(fx+base_bot/2,fy),(fx-base_bot/2,fy),(fx-base_top/2,fy+base_h)], dxfattribs={'layer':'MATERIAL_METAL'})
    msp.add_line((fx,fy-40),(fx,fy+H+40), dxfattribs={'layer':'CENTER'})

    # Side elevation
    sx, sy = 1400, -900
    msp.add_text('SIDE ELEVATION', height=35, dxfattribs={'layer':'TEXT'}).set_placement((sx-D/2, sy+H+100))
    msp.add_lwpolyline([(sx-D/2,sy+H),(sx+D/2,sy+H),(sx+D/2,sy+H-T),(sx-D/2,sy+H-T),(sx-D/2,sy+H)], dxfattribs={'layer':'MATERIAL_STONE'})
    msp.add_lwpolyline([(sx-base_top/2,sy+base_h),(sx+base_top/2,sy+base_h),(sx+base_bot/2,sy),(sx-base_bot/2,sy),(sx-base_top/2,sy+base_h)], dxfattribs={'layer':'MATERIAL_METAL'})
    msp.add_line((sx,sy-40),(sx,sy+H+40), dxfattribs={'layer':'CENTER'})

    # Section
    qx, qy = 0, -1600
    msp.add_text('SECTION A-A', height=35, dxfattribs={'layer':'TEXT'}).set_placement((qx-L/2, qy+H+100))
    msp.add_lwpolyline([(qx-L/2,qy+H),(qx+L/2,qy+H),(qx+L/2,qy+H-T),(qx-L/2,qy+H-T),(qx-L/2,qy+H)], dxfattribs={'layer':'SECTION'})
    # bowl section simplified arc/polyline
    msp.add_arc(center=(qx,qy+H-T), radius=bowl/2, start_angle=200, end_angle=340, dxfattribs={'layer':'MATERIAL_METAL'})
    msp.add_lwpolyline([(qx-base_top/2,qy+base_h),(qx+base_top/2,qy+base_h),(qx+base_bot/2,qy),(qx-base_bot/2,qy),(qx-base_top/2,qy+base_h)], dxfattribs={'layer':'SECTION'})

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)
    return out_path
