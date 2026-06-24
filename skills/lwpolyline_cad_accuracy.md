# LWPOLYLINE CAD Accuracy Skill

## Purpose
Guide the agent to generate precise, clean LWPOLYLINE entities in DXF output for professional shop drawings.

## When to Use
- Generating any closed polygonal shape (tabletop, cabinet, sofa outline)
- Replacing individual LINE segments with a single LWPOLYLINE
- Creating professional DXF files for AutoCAD, LibreCAD, FreeCAD

## Rules

### 1. Always Prefer LWPOLYLINE Over Individual Lines
- A rectangle should be ONE LWPOLYLINE, not 4 LINE entities
- A cabinet outline should be ONE LWPOLYLINE, not 4 edges
- Exception: long structural lines or centerlines should remain individual LINE entities

### 2. LWPOLYLINE Syntax (ezdxf)
```python
# Closed polyline (rectangle, outline, polygon)
msp.add_lwpolyline(
    [(x1,y1), (x2,y1), (x2,y2), (x1,y2)],
    close=True,
    dxfattribs={'layer': 'OBJECT'}
)

# Open polyline (profile, partial shape) 
msp.add_lwpolyline(
    [(x1,y1), (x2,y2), (x3,y3)],
    close=False,
    dxfattribs={'layer': 'OBJECT'}
)
```

### 3. Coordinate Precision
- All coordinates must be floats, not integers
- Round to 1 decimal place maximum: `round(x, 1)`
- Ensure clockwise or counter-clockwise winding is consistent
- Verify no zero-length segments (adjacent duplicate points)

### 4. Fallback Strategy
If `msp.add_lwpolyline()` raises an exception:
```python
try:
    msp.add_lwpolyline(points, close=True, dxfattribs={'layer': layer})
except Exception:
    # Fallback to individual lines
    for i in range(len(points)-1):
        msp.add_line(points[i], points[i+1], dxfattribs={'layer': layer})
    msp.add_line(points[-1], points[0], dxfattribs={'layer': layer})
```

### 5. Layer Assignment
| Layer | Color | Use |
|-------|-------|-----|
| OBJECT | White (7) | Main geometry — LWPOLYLINE, CIRCLE |
| DIMENSION | Green (3) | Dimension lines |
| CENTER | Blue (5) | Centerlines (LINE only) |
| TEXT | Yellow (2) | Labels, annotations |
| HATCH | Grey (8) | Hatching patterns |
| HIDDEN | Dark Grey (251) | Hidden/dashed lines |
| TITLE | Magenta (6) | Title block border |
| BORDER | White (7) | Page border |

### 6. Validation Checklist
Before saving DXF:
- [ ] All closed shapes use LWPOLYLINE (not LINE segments)
- [ ] No zero-length entities exist
- [ ] Layers are correctly assigned
- [ ] Title block has all required fields (DRAWING, SCALE, DATE, DESIGNER)
- [ ] HATCH entities use valid pattern names (ANSI31, ANSI37)
- [ ] Dimensions are rendered with `dim.render()`
- [ ] Document units are set: `doc.units = ezdxf.units.CM`

### 7. Example: Professional Table Outline
```python
# Bad: 4 individual lines
msp.add_line((0,0), (100,0), dxfattribs={'layer':'OBJECT'})
msp.add_line((100,0), (100,50), dxfattribs={'layer':'OBJECT'})
msp.add_line((100,50), (0,50), dxfattribs={'layer':'OBJECT'})
msp.add_line((0,50), (0,0), dxfattribs={'layer':'OBJECT'})

# Good: 1 LWPOLYLINE
msp.add_lwpolyline([(0,0), (100,0), (100,50), (0,50)], close=True, dxfattribs={'layer':'OBJECT'})
```

## Related Files
- `backend-python/app/backend/dxf_exporter.py` — reference implementation
- `backend-python/tests/test_dxf_exporter.py` — validation tests
