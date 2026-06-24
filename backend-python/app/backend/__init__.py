"""
Modular backend for CAD Scaler Digitizer v2.0.

Core pipeline:
- vision.py: OpenCV primitive detection (lines, circles, rectangles)
- ocr.py: Tesseract + OpenAI Vision OCR text extraction
- geometry_cleanup.py: Constraint solver (angle snap, endpoint snap)
- dimension_validator.py: Cross-validate OCR dims against geometry
- furniture_classifier.py: Identify furniture type from features
- semantic_proportion_validator.py: Validate semantic furniture proportions
- visual_ratio_scaler.py: Estimate component proportions from known dims
- furniture_component_segmenter.py: Identify sub-components from OCR/AI
- polyline_builder.py: Convert line groups to polylines

CAD generation:
- dxf_exporter.py: Professional DXF templates (9 furniture types)
- layer_manager.py: Standard DXF layers (OBJECT, DIMENSION, LEADER, etc.)
- titleblock_generator.py: Professional shop drawing title block + notes
- extents_updater.py: Auto-calculate DXF extents for proper zoom
- dxf_auditor.py: DXF quality validation and scoring
- text_normalizer.py: Clean OCR text for DXF insertion
- text_tokenizer.py: Legacy dimension string tokenizer (unused)

Intelligence:
- chat_agent.py: Ollama Hermes-powered conversational refinement
- leader_dimension_classifier.py: Distinguish dimensions vs leaders
- anti_hallucination_validator.py: VISIBLE/ESTIMATED/UNKNOWN rules
- feedback_learner.py: Echo Drafter passive learning system
- vector_calibration.py: Coordinate calibration pipeline (unused)

Services:
- ml_engine.py: ONNX ML classification + dimension prediction
- pdf_exporter.py: PDF shop drawing export
- freecad_exporter.py: FreeCAD FCStd conversion
"""

# Re-export key symbols for convenience (safe import — may fail without ezdxf)
try:
    from app.backend.furniture_classifier import classify_furniture, normalize_furniture_type
    from app.backend.dxf_exporter import (
        save_generic, save_round_pedestal_table, save_rectangular_table,
        save_cabinet, save_sofa, save_coffee_table, save_dining_chair,
        save_wardrobe, save_reception_counter,
    )
except ImportError:
    pass  # ezdxf not installed (e.g. outside Docker)
