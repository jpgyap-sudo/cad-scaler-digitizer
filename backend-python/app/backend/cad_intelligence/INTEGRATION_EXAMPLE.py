from app.backend.cad_intelligence.pipeline import run_cad_intelligence_pipeline
from app.backend.cad_intelligence.export_debug import pipeline_result_to_dict
from app.backend.cad_intelligence.dxf_exporter import export_entities_to_dxf

def process_with_new_intelligence(image_path: str, ocr_items: list[dict], output_dxf_path: str):
    result = run_cad_intelligence_pipeline(
        image_path=image_path,
        ocr_items=ocr_items,
        default_unit="mm",
    )
    debug_json = pipeline_result_to_dict(result)
    export_entities_to_dxf(result.entities, output_path=output_dxf_path)
    return {
        "dxf_path": output_dxf_path,
        "scale": debug_json["scale"],
        "confidence": debug_json["debug"]["confidence_summary"],
        "debug": debug_json,
    }
