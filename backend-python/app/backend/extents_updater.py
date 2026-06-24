"""Update DXF header extents so viewers zoom correctly."""


def update_extents(doc):
    """Calculate and set $EXTMIN and $EXTMAX in DXF header."""
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')

    for entity in doc.modelspace():
        try:
            for point in [entity.dxf.start, entity.dxf.end]:
                if hasattr(point, 'x'):
                    if point.x < min_x: min_x = point.x
                    if point.y < min_y: min_y = point.y
                    if point.x > max_x: max_x = point.x
                    if point.y > max_y: max_y = point.y
        except Exception:
            try:
                c = entity.dxf.center
                if hasattr(c, 'x'):
                    if c.x - entity.dxf.radius < min_x: min_x = c.x - entity.dxf.radius
                    if c.y - entity.dxf.radius < min_y: min_y = c.y - entity.dxf.radius
                    if c.x + entity.dxf.radius > max_x: max_x = c.x + entity.dxf.radius
                    if c.y + entity.dxf.radius > max_y: max_y = c.y + entity.dxf.radius
            except Exception:
                pass

    if min_x != float('inf'):
        doc.header['$EXTMIN'] = (min_x - 10, min_y - 10, 0)
        doc.header['$EXTMAX'] = (max_x + 10, max_y + 10, 0)

    return doc


def setup_a3_sheet(doc):
    """Set up A3 landscape sheet extents."""
    doc.header['$EXTMIN'] = (-10, -10, 0)
    doc.header['$EXTMAX'] = (430, 307, 0)
    doc.header['$LIMMIN'] = (0, 0, 0)
    doc.header['$LIMMAX'] = (420, 297, 0)
    return doc
