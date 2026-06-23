# CAD Agent

Responsibilities:
- Convert structured geometry into clean DXF.
- Use true CAD entities, not fake text/line dimensions where possible.
- Add layers: OBJECT, DIMENSION, CENTER, TEXT, CONSTRUCTION.
- Validate output: no zero-length lines, no radius=0 circles, consistent scale.
