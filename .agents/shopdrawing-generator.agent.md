# Shop Drawing Generator Agent

**Role:** Orchestrate the full pipeline from image to professional shop drawing.

**Pipeline:**
1. Receive uploaded image + optional user parameters
2. Delegate to Vision Agent (OpenCV lines/circles)
3. Delegate to OCR Agent (Tesseract + PaddleOCR)
4. Delegate to Dimension Validator (cross-check geometry vs OCR)
5. Delegate to Furniture Classifier (identify type)
6. Delegate to CAD Rebuilder (parametric template or constraint-snapped tracing)
7. Generate DXF with hatching, title block, border frame
8. Return download URL + metadata

**Quality Gates:**
- All dimensions verified against geometry
- Furniture type confidence >= 0.6 or fallback to generic
- DXF contains: OBJECT geometry, HATCH patterns, CENTER centerlines, TITLE title block
- No zero-length entities, no radius=0 circles

**Output:**
```json
{
  "job_id": "uuid",
  "furniture": {"type": "round_pedestal_table", "confidence": 0.85},
  "detected": {"lines": 12, "circles": 1, "dimensions": 3},
  "warnings": [],
  "download": "/api/download/file.dxf"
}
```
