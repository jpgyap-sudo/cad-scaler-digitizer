"""Professional shop drawing title block and notes generator."""

from datetime import datetime


def generate_title_block(msp, title="Furniture Drawing", page_w=420, page_h=297,
                         designer="AI CAD Drafter", project="CAD Scaler Digitizer",
                         client="", scale="1:1", revision="A",
                         material_notes=None):
    """
    Professional shop drawing layout with:
    - A3 sheet border
    - Title block (bottom-right) with client, project, scale, revision
    - Material/finish notes (top-left)
    - General tolerances block
    """
    now = datetime.now().strftime('%Y-%m-%d')

    # === SHEET BORDER ===
    _add_lwpolyline(msp, [(0, 0), (page_w, 0), (page_w, page_h), (0, page_h)], True, 'BORDER')

    # === TITLE BLOCK (Bottom-Right) ===
    tb_w, tb_h = 180, 60
    ox, oy = page_w - tb_w - 10, 10

    # Outer border
    _add_lwpolyline(msp, [(ox, oy), (ox + tb_w, oy),
                           (ox + tb_w, oy + tb_h), (ox, oy + tb_h)], True, 'TITLE')

    # Vertical divider (left 2/3, right 1/3)
    col_mid = ox + tb_w * 0.65
    _add_line(msp, (col_mid, oy), (col_mid, oy + tb_h), 'TITLE')

    # Horizontal dividers (4 rows)
    row_h = tb_h / 4
    for i in range(1, 4):
        y = oy + row_h * i
        _add_line(msp, (ox, y), (ox + tb_w, y), 'TITLE')

    # Row 1: PROJECT | CLIENT
    _add_mtext(msp, 'PROJECT:', (ox + 3, oy + row_h * 3 + 2), 2.2, 'TITLE')
    _add_mtext(msp, project[:40], (ox + 3, oy + row_h * 3 - 5), 2.5, 'TITLE')
    _add_mtext(msp, 'CLIENT:', (col_mid + 3, oy + row_h * 3 + 2), 2.2, 'TITLE')
    _add_mtext(msp, client[:30] if client else '—', (col_mid + 3, oy + row_h * 3 - 5), 2.5, 'TITLE')

    # Row 2: DRAWING TITLE (full width)
    _add_mtext(msp, 'DRAWING:', (ox + 3, oy + row_h * 2 + 2), 2.2, 'TITLE')
    _add_mtext(msp, title[:60], (ox + 3, oy + row_h * 2 - 5), 2.5, 'TITLE')

    # Row 3: SCALE | DATE | REV
    _add_mtext(msp, f'SCALE: {scale}', (ox + 3, oy + row_h + 2), 2.2, 'TITLE')
    _add_mtext(msp, f'DATE: {now}', (ox + 42, oy + row_h + 2), 2.2, 'TITLE')
    _add_mtext(msp, f'REV: {revision}', (col_mid + 3, oy + row_h + 2), 2.2, 'TITLE')

    # Row 4: DRAWN | CHECKED
    _add_mtext(msp, f'DRAWN: {designer[:25]}', (ox + 3, oy + 2), 2.2, 'TITLE')
    _add_mtext(msp, 'CHECKED:', (col_mid + 3, oy + 2), 2.2, 'TITLE')

    # === MATERIAL / FINISH NOTES (Top-Left) ===
    nx, ny = 12, page_h - 18
    default_notes = material_notes or [
        "WOOD TOP — Solid hardwood, stained finish",
        "PEDESTAL BASE — Textured metal, powder coated",
    ]
    _add_mtext(msp, 'MATERIAL / FINISH NOTES:', (nx, ny), 2.5, 'MTEXT')
    for i, note in enumerate(default_notes):
        _add_mtext(msp, f'  {i+1}. {note[:70]}', (nx, ny - 6 - i * 5), 2.2, 'MTEXT')

    # === GENERAL NOTES (Top-Left, below material notes) ===
    gy = ny - 6 - len(default_notes) * 5 - 6
    _add_mtext(msp, 'GENERAL NOTES:', (nx, gy), 2.5, 'MTEXT')
    gen_notes = [
        "ALL DIMENSIONS IN CENTIMETERS (CM) UNLESS NOTED",
        "TOLERANCES: +/- 2mm UNLESS OTHERWISE SPECIFIED",
        "REFER TO FINISH SAMPLE FOR COLOR & TEXTURE",
    ]
    for i, note in enumerate(gen_notes):
        _add_mtext(msp, f'  {i+1}. {note[:75]}', (nx, gy - 6 - i * 5), 2.2, 'MTEXT')

    # === SCALE BAR (Bottom-Left, above border) ===
    sx, sy = 12, 16
    bar_len = 40  # mm on paper representing 40cm at 1:2 scale
    _add_line(msp, (sx, sy), (sx + bar_len, sy), 'TITLE')
    _add_line(msp, (sx, sy - 2), (sx, sy + 2), 'TITLE')
    _add_line(msp, (sx + bar_len / 2, sy - 2), (sx + bar_len / 2, sy + 2), 'TITLE')
    _add_line(msp, (sx + bar_len, sy - 2), (sx + bar_len, sy + 2), 'TITLE')
    _add_mtext(msp, f'SCALE 1:2  ({scale} in cm)', (sx, sy + 4), 2, 'TITLE')


# ===== Helper functions =====

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
