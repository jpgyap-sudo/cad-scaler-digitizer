# CAD Geometry Cleanup Skill

Run before writing DXF:
- Remove zero-length entities.
- Remove radius=0 circles.
- Merge collinear lines on the same axis.
- Snap endpoints within tolerance.
- Straighten near-horizontal and near-vertical lines.
- Replace circular polygons with true CIRCLE when >8 segments fit a circle.
- Replace 4 connected 90-degree lines with LWPOLYLINE rectangle.
- Validate dimensions: text label must match geometry within tolerance.
