"""Update DXF header extents so viewers zoom correctly."""
import ezdxf


def _set_ext(doc, key, x, y, z=0):
    """Safely set a header extent — handles different ezdxf versions."""
    try:
        doc.header[key] = (x, y, z)
    except Exception:
        try:
            from ezdxf.math import Vec3
            doc.header[key] = Vec3(x, y, z)
        except Exception:
            pass


def update_extents(doc):
    """Calculate extents from modelspace entities and set $EXTMIN/$EXTMAX."""
    try:
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        found_any = False

        for entity in doc.modelspace():
            try:
                if entity.dxftype() == 'LWPOLYLINE':
                    for point in entity.vertices():
                        vx, vy = float(point[0]), float(point[1])
                        if vx < min_x: min_x = vx
                        if vy < min_y: min_y = vy
                        if vx > max_x: max_x = vx
                        if vy > max_y: max_y = vy
                        found_any = True
                elif entity.dxftype() == 'LINE':
                    sx, sy = entity.dxf.start.x, entity.dxf.start.y
                    ex, ey = entity.dxf.end.x, entity.dxf.end.y
                    for vx, vy in [(sx, sy), (ex, ey)]:
                        if vx < min_x: min_x = vx
                        if vy < min_y: min_y = vy
                        if vx > max_x: max_x = vx
                        if vy > max_y: max_y = vy
                    found_any = True
                elif entity.dxftype() == 'CIRCLE':
                    cx, cy = entity.dxf.center.x, entity.dxf.center.y
                    r = entity.dxf.radius
                    for vx, vy in [(cx - r, cy - r), (cx + r, cy + r)]:
                        if vx < min_x: min_x = vx
                        if vy < min_y: min_y = vy
                        if vx > max_x: max_x = vx
                        if vy > max_y: max_y = vy
                    found_any = True
                elif entity.dxftype() == 'MTEXT':
                    ins = entity.dxf.insert
                    if ins.x < min_x: min_x = ins.x
                    if ins.y < min_y: min_y = ins.y
                    if ins.x > max_x: max_x = ins.x
                    if ins.y > max_y: max_y = ins.y
                    found_any = True
            except Exception:
                continue

        if found_any:
            margin_x = max(10, (max_x - min_x) * 0.05)
            margin_y = max(10, (max_y - min_y) * 0.05)
            _set_ext(doc, '$EXTMIN', min_x - margin_x, min_y - margin_y)
            _set_ext(doc, '$EXTMAX', max_x + margin_x, max_y + margin_y)
        else:
            # Fallback to A3
            _set_ext(doc, '$EXTMIN', -10, -10)
            _set_ext(doc, '$EXTMAX', 430, 307)
    except Exception:
        # Ultimate fallback — try direct header var
        try:
            _set_ext(doc, '$EXTMIN', -10, -10)
            _set_ext(doc, '$EXTMAX', 430, 307)
        except Exception:
            pass

    return doc


def setup_a3_sheet(doc):
    """Set up A3 landscape sheet defaults (for use before adding entities)."""
    return doc
