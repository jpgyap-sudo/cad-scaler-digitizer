"""
Modular backend for CAD Scaler Digitizer.
Each module handles a specific concern:
- vision.py: OpenCV primitive detection
- ocr.py: Tesseract + PaddleOCR text extraction
- geometry_cleanup.py: Constraint solver (angle snap, endpoint snap, etc.)
- dimension_validator.py: Cross-validate OCR dims against geometry
- furniture_classifier.py: Identify furniture type from features
- dxf_exporter.py: Generate professional DXF with hatching + title block
"""
