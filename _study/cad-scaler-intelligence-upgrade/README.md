# CAD Scaler Digitizer — Intelligence Upgrade

Drop these files into:

cad-scaler-digitizer/backend-python/app/backend/cad_intelligence/

This upgrade adds:

- OCR dimension parsing
- line/circle detection
- line role classification
- dimension-to-geometry association
- scale solving
- reconstructed CAD entities
- confidence scoring
- optional DXF export
- frontend review type helpers

Main import:

```python
from app.backend.cad_intelligence.pipeline import run_cad_intelligence_pipeline
```

Example:

```python
result = run_cad_intelligence_pipeline(
    image_path="uploads/source.png",
    ocr_items=[
        {"text": "80 DIA", "bbox": [100, 200, 180, 230], "confidence": 0.91}
    ],
    default_unit="mm",
)
```
