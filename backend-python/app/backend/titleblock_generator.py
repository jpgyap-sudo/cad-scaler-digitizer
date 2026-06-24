"""Professional title block generator for shop drawings."""
from datetime import datetime


def generate_title_block(msp, title="Furniture Drawing", page_w=420, page_h=297,
                         designer="AI CAD Drafter", project="CAD Scaler Digitizer"):
    """
    Draw professional title block in bottom-right corner.
    Uses LWPOLYLINE for border, MTEXT for labels.
    All on TITLE or BORDER layers (never layer 0).
    """
    tb_w, tb_h = 180, 55
    ox, oy = page_w - tb_w - 10, 10
    now = datetime.now().strftime('%Y-%m-%d')

    # Sheet border
    _add_lwpolyline(msp, [(0, 0), (page_w, 0), (page_w, page_h), (0, page_h)], True, 'BORDER')

    # Title block outer
    _add_lwpolyline(msp, [(ox, oy), (ox + tb_w, oy), (ox + tb_w, oy + tb_h), (ox, oy + tb_h)], True, 'TITLE')

    # Divider lines
    _add_line(msp, (ox, oy + tb_h - 15), (ox + tb_w, oy + tb_h - 15), 'TITLE')
    _add_line(msp, (ox, oy + tb_h - 30), (ox + tb_w, oy + tb_h - 30), 'TITLE')

    # Title block content
    _add_mtext(msp, f'PROJECT: {project}', (ox + 3, oy + tb_h - 13), 2.5, 'TITLE')
    _add_mtext(msp, f'DRAWING: {title}', (ox + 3, oy + tb_h - 28), 2.5, 'TITLE')
    _add_mtext(msp, f'SCALE: cm    DATE: {now}', (ox + 3, oy + 18), 2.5, 'TITLE')
    _add_mtext(msp, f'DRAWN BY: {designer}', (ox + 3, oy + 3), 2.5, 'TITLE')


def _add_lwpolyline(msp, points, closed, layer):
    try:
        msp.add_lwpolyline(points, close=closed, dxfattribs={'layer': layer})
    except Exception:
        for i in range(len(points) - 1):
            msp.add_line(points[i], points[i + 1], dxfattribs={'layer': layer})
        if closed:
            msp.add_line(points[-1], points[0], dxfattribs={'layer': layer})


def _add_line(msp, p1, p2, layer):
    msp.add_line(p1, p2, dxfattribs={'layer': layer})


def _add_mtext(msp, text, pos, height, layer):
    if not text:
        return
    try:
        m = msp.add_mtext(text, dxfattribs={'layer': layer, 'char_height': height})
        m.dxf.insert = pos
    except Exception:
        t = msp.add_text(text, dxfattribs={'height': height, 'layer': layer})
        t.dxf.insert = pos
