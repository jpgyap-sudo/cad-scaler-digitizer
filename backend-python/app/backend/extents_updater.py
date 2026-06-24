"""Update DXF header extents so viewers zoom correctly."""
import ezdxf


def _set_ext(doc, key, x, y, z=0.0):
    """Set a header extent — tries multiple ezdxf API variants."""
    from ezdxf.math import Vec3
    v = Vec3(float(x), float(y), float(z))
    # Attempt 1: direct tuple assignment
    try:
        doc.header[key] = (float(x), float(y), float(z))
        return
    except Exception:
        pass
    # Attempt 2: Vec3 object
    try:
        doc.header[key] = v
        return
    except Exception:
        pass
    # Attempt 3: set_var method
    try:
        doc.header.set_var(key, v)
        return
    except Exception:
        pass
    # Attempt 4: raw variable set
    try:
        h = doc.header
        if hasattr(h, '_vars'):
            h._vars[key] = v
        return
    except Exception:
        pass
    print(f"[ExtentsUpdater] All 4 attempts failed to set {key}")


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
                elif entity.dxftype() == 'HATCH':
                    for path in entity.paths:
                        for v in path.vertices:
                            vx, vy = float(v[0]), float(v[1])
                            if vx < min_x: min_x = vx
                            if vy < min_y: min_y = vy
                            if vx > max_x: max_x = vx
                            if vy > max_y: max_y = vy
                            found_any = True
                elif entity.dxftype() == 'TEXT':
                    ins = entity.dxf.insert
                    if ins.x < min_x: min_x = ins.x
                    if ins.y < min_y: min_y = ins.y
                    if ins.x > max_x: max_x = ins.x
                    if ins.y > max_y: max_y = ins.y
                    found_any = True
                elif entity.dxftype() == 'INSERT':
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
            print("[ExtentsUpdater] No entities found — using A3 default extents")
            _set_ext(doc, '$EXTMIN', -10, -10)
            _set_ext(doc, '$EXTMAX', 430, 307)
    except Exception as e:
        print(f"[ExtentsUpdater] Calculation failed ({e}) — falling back to A3 default extents")
        try:
            _set_ext(doc, '$EXTMIN', -10, -10)
            _set_ext(doc, '$EXTMAX', 430, 307)
        except Exception:
            pass

    return doc


def setup_a3_sheet(doc):
    """Set up A3 landscape sheet defaults (for use before adding entities)."""
    return doc
