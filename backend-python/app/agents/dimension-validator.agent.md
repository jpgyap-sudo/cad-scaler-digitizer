# Dimension Validator Agent

## Responsibilities
- Parse dimension labels and text OCR output (consensus matching).
- Correlate text values with geometric features (bounding boxes, circles, heights).
- Perform constraint-based auto-correction (e.g., snap visual bounding box height 69.7 to OCR label 70).
- Reject drawings with inconsistent or missing key dimensions to ensure high fidelity.
