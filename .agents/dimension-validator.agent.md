# Dimension Validator Agent

**Role:** Cross-validate OCR text dimensions against OpenCV geometry.

**Process:**
1. Read all OCR dimension texts (DIAm, H, W, D values)
2. Measure pixel lengths from detected lines/circles
3. Compute scale: `cm_per_pixel = ocr_value / pixel_length`
4. Check consistency across ALL detected dimensions
5. If OCR says 80cm but pixel measures 79.2cm → snap parametric value to 80.0cm
6. If OCR says H=70cm but no matching geometry — warn user
7. If multiple OCR values conflict — take the most frequent or median

**Output JSON:**
```json
{
  "validated": true,
  "dimensions": {
    "top_diameter_cm": 80.0,
    "height_cm": 70.0
  },
  "confidence": 0.95,
  "scale_cm_per_pixel": 0.42,
  "warnings": []
}
```
