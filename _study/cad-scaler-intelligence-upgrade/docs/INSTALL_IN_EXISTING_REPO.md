# Install Into Existing `cad-scaler-digitizer`

## 1. Copy backend files

```bash
cp -r backend-python/app/backend/cad_intelligence \
  /path/to/cad-scaler-digitizer/backend-python/app/backend/
```

## 2. Install dependencies

```bash
pip install opencv-python numpy ezdxf pytest
```

## 3. Add import to your process route

```python
from app.backend.cad_intelligence.pipeline import run_cad_intelligence_pipeline
from app.backend.cad_intelligence.export_debug import pipeline_result_to_dict
from app.backend.cad_intelligence.dxf_exporter import export_entities_to_dxf
```

## 4. Use after OCR

```python
result = run_cad_intelligence_pipeline(
    image_path=page_image_path,
    ocr_items=ocr_items,
    default_unit="mm",
)

debug = pipeline_result_to_dict(result)

export_entities_to_dxf(
    result.entities,
    output_path=output_dxf_path,
)
```

## 5. Return debug JSON to frontend

Return:

```json
{
  "scale": "...",
  "confidence": "...",
  "entities": "...",
  "associations": "..."
}
```
