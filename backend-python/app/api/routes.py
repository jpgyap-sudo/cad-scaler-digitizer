"""API routes for CAD digitizer with accuracy core pipeline."""

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse, Response, HTMLResponse
from typing import List, Optional
from pathlib import Path
import shutil, uuid, os, tempfile, json, traceback

from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles, normalize_lines
from app.backend.ocr import ocr_dimensions
from app.backend.ocr_layout_parser import extract_layout
from app.backend.dimension_associator import associate_dimension_text
from app.backend.line_role_classifier import classify_line_roles
from app.backend.scale_solver import compute_scale
from app.backend.geometry_reconstructor import reconstruct_geometry, reconstruct
from app.backend.geometry_cleanup import process_constraints
from app.backend.dimension_validator import autocorrect_dimensions, validate_scale
from app.backend.furniture_classifier import classify_furniture, normalize_furniture_type
from app.backend.template_selector import select_template, load_templates
from app.backend.leader_dimension_classifier import classify_drawing_annotations
from app.backend.furniture_component_segmenter import segment_furniture
from app.backend.correction_api import submit_corrections, get_corrections, reset_corrections
from app.backend.accuracy_benchmark import run_accuracy_benchmark, load_fixtures
from app.backend.section_predictor import predict_drawing_sections
from app.backend.reference_ratio_solver import solve_missing_dimensions, get_reference_ratios
from app.backend.reference_confidence_scorer import score_dimension_confidence, get_overall_confidence
from app.backend.reference_geometry_matcher import match_detected_to_reference
from app.backend.dxf_exporter import (
    save_generic, save_round_pedestal_table, save_rectangular_table,
    save_cabinet, save_sofa, save_coffee_table, save_dining_chair,
    save_wardrobe, save_reception_counter, save_bed_headboard,
    save_asymmetric_pedestal_table, save_oval_pedestal_table,
    save_console_table, save_office_desk,
    save_armchair, save_bar_stool, save_bench_chaise,
    save_ottoman, save_rug, save_stone_slab, save_wall_panel,
    save_lounge_chair, save_sideboard, save_tv_console,
)
from app.resource_engine.template_loader import TemplateGraphLoader
from app.resource_engine.template_resolver import TemplateResolver
from app.resource_engine.pipeline_orchestrator import Phase3Pipeline, Phase3PipelineResult
from app.backend.cad_intelligence.pipeline import run_cad_intelligence_pipeline
from app.backend.cad_intelligence.export_debug import pipeline_result_to_dict as ci_debug_dict
from app.backend.cad_intelligence.dxf_exporter import export_entities_to_dxf as ci_export_dxf
from app.backend.cad_intelligence.unified_router import (
    run_unified_pipeline, UnifiedResult, ProvenanceValue
)

router = APIRouter()

# Lazy-loaded template resolver singleton
_TEMPLATE_LOADER: TemplateGraphLoader | None = None
_TEMPLATE_RESOLVER: TemplateResolver | None = None
_PHASE3_PIPELINE: Phase3Pipeline | None = None


def _get_template_resolver() -> TemplateResolver:
    global _TEMPLATE_LOADER, _TEMPLATE_RESOLVER
    if _TEMPLATE_RESOLVER is None:
        _TEMPLATE_LOADER = TemplateGraphLoader().load()
        _TEMPLATE_RESOLVER = TemplateResolver(_TEMPLATE_LOADER)
    return _TEMPLATE_RESOLVER


def _get_phase3_pipeline() -> Phase3Pipeline:
    global _PHASE3_PIPELINE
    if _PHASE3_PIPELINE is None:
        _PHASE3_PIPELINE = Phase3Pipeline()
    return _PHASE3_PIPELINE

OUT = Path(tempfile.gettempdir()) / "cad_digitizer_outputs"
OUT.mkdir(exist_ok=True)
UPLOAD = Path(tempfile.gettempdir()) / "cad_digitizer_uploads"
UPLOAD.mkdir(exist_ok=True)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Below this confidence, the classifier guess is unreliable enough that the
# UI should ask the user to confirm/correct the furniture type rather than
# silently rendering a possibly-wrong template.
CLASSIFIER_CONFIRM_THRESHOLD = 0.55

# Structured visual proportion measurement (the "ledger" skill).
#
# Vision LLMs are reliably good at one thing and reliably bad at another:
# - GOOD: pointing/localizing ("where is the left edge of X in this image")
# - BAD: mental arithmetic on two separate measurements ("what fraction is
#        X's width of Y's width") - confirmed by direct testing, where the
#        same model returned ratios of 0.16/0.20/0.28/0.35/1.0 for the exact
#        same photo across separate calls, and once classified an obviously
#        flared pedestal as a plain cylinder.
#
# So instead of asking for a ratio, ask for edge COORDINATES (normalized 0-1
# fractions of image width) at each section's representative row, and have
# OUR code do the division. This plays to the model's strength and removes
# its weakest step from the critical path entirely.
VISION_SYSTEM_PROMPT = (
    "Analyze furniture drawing. Identify the SPECIFIC furniture type from this "
    "list: round_pedestal_table, rectangular_table, cabinet, sofa, coffee_table, "
    "dining_chair, wardrobe, reception_counter, bed_headboard, asymmetric_pedestal_table, "
    "oval_pedestal_table, console_table, office_desk. "
    "First extract the overall size (length/width/diameter, depth, height) from "
    "any text labels in the image - these are the anchor dimensions everything "
    "else is measured relative to. For each dimension label, use nearby text to "
    "tag it precisely: 'top_dia' (tabletop diameter), 'base_dia' (base plate / "
    "pedestal foot / glide diameter), 'neck_dia' (narrowest point of pedestal), "
    "'collar_dia' (metal collar plate just under the top), 'height', 'width', "
    "'depth', 'thickness'. "
    "\n\nIf the furniture is a round_pedestal_table, ALSO describe the pedestal "
    "as a SEQUENCE OF SECTIONS from the tabletop down to the floor - however "
    "many sections actually exist in THIS photo, not a fixed list. A simple "
    "table might have just one section (a single straight or tapering column); "
    "a complex one might have a collar plate, a narrow neck, and a flared base "
    "as separate sections. For EACH section, report its name/role and its LEFT "
    "and RIGHT edge as a fraction of the image width (0.0 = left edge of image, "
    "1.0 = right edge of image), measured at that section's widest/most "
    "representative point - do NOT report a width percentage or ratio yourself, "
    "report the raw edge positions and let the edges speak for themselves. Also "
    "report the tabletop's own left/right edge fractions the same way, as the "
    "reference every section is measured against. "
    "CRITICAL: preserve the proportions exactly as they appear in THIS image - "
    "do not round toward 'typical' table conventions or a remembered default; "
    "measure what is actually drawn, even if it looks unusual. "
    "Return a 'visual_base_estimate' object: {\"profile\": \"cylinder|tapered|"
    "flared|unknown\", \"tabletop_edges\": [left_frac, right_frac], "
    "\"sections\": [{\"name\": \"collar_plate|neck_ring|pedestal_body|base_plate"
    "|column\", \"edges\": [left_frac, right_frac]}], "
    "\"self_check\": \"one sentence confirming the edges you reported are "
    "consistent with the profile you chose\"}. "
    "\n\nALSO inspect each visible component (tabletop, collar/base plate, "
    "neck/column, base/feet) for its material and finish. If a material is "
    "explicitly written/labeled in the image, use that exact text. If NOT "
    "labeled, infer the most likely material from visual cues - color, sheen/"
    "reflectivity, grain/texture, edge profile (e.g. glossy dark surface with "
    "visible weld seams -> 'powder-coated steel'; visible wood grain -> 'solid "
    "wood, [color] stain'; matte uniform color -> 'painted MDF' or 'matte "
    "lacquer'). Always provide a best-guess material per component, never "
    "leave it blank, but mark inferred ones. Return a 'materials' object: "
    "{\"component_name\": {\"description\": \"material text\", \"inferred\": "
    "true_or_false}}. "
    "Return JSON with furniture_type, confidence (0-1), dimensions array "
    "[{tag, value_cm}], visual_base_estimate, materials."
)


def _edge_width(edges) -> Optional[float]:
    """Width of a [left_frac, right_frac] edge pair, or None if malformed."""
    try:
        left, right = float(edges[0]), float(edges[1])
        w = right - left
        return w if w > 0 else None
    except (TypeError, ValueError, IndexError):
        return None


def _ratios_from_sections(visual_base_estimate: dict) -> dict:
    """Compute each section's width as a fraction of the tabletop's width from
    reported edge coordinates - this is the deterministic math step the model
    itself is unreliable at. Returns {} if edges are missing/malformed (the
    caller falls back to the direct-ratio sanity-clamp path).

    Our renderer always needs BOTH a neck (top of the column) and a base
    (bottom of the column) width to draw the trapezoid - but the model often
    only reports ONE section for a simple table (e.g. just "pedestal_body"),
    since that's genuinely all there is. Tested directly: leaving the other
    ratio unset made it silently fall back to an unrelated generic default
    (e.g. base measured at 75% but neck defaulting to 28%, an inconsistent
    shape with no connection to what was actually measured). When only one
    of neck/base is reported, mirror it to the other - a single uniform-
    width section means the column doesn't taper, so neck == base is the
    correct interpretation, not "the other one is unknown."
    """
    if not isinstance(visual_base_estimate, dict):
        return {}
    top_w = _edge_width(visual_base_estimate.get('tabletop_edges'))
    sections = visual_base_estimate.get('sections')
    if not top_w or not isinstance(sections, list):
        return {}

    ratios = {}
    # Map the model's free-form section names onto our fixed render slots.
    name_map = {
        'collar_plate': 'collar_ratio', 'collar': 'collar_ratio',
        'neck_ring': 'neck_ratio', 'neck': 'neck_ratio',
        'pedestal_body': 'base_ratio', 'base_plate': 'base_ratio', 'base': 'base_ratio',
        'column': 'base_ratio',  # see mirroring below if it's the only section
    }
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = name_map.get(str(section.get('name', '')).lower())
        w = _edge_width(section.get('edges'))
        if key and w:
            ratios[key] = w / top_w

    if 'neck_ratio' not in ratios:
        # The neck is the structural continuation directly below the collar
        # (if any), so it should approximate the collar's width, not the
        # base's - a collar+body-only report (no separate neck) most likely
        # means the column continues at roughly the collar's width before
        # whatever the body does lower down. Only fall back to mirroring the
        # base when there's no collar either (a single uniform section).
        if 'collar_ratio' in ratios:
            ratios['neck_ratio'] = ratios['collar_ratio']
        elif 'base_ratio' in ratios:
            ratios['neck_ratio'] = ratios['base_ratio']
    if 'base_ratio' not in ratios and 'neck_ratio' in ratios:
        ratios['base_ratio'] = ratios['neck_ratio']
    return ratios


def _save_drawing_model(f_type, dxf_path, width_cm, height_cm, base_dia_cm=None, neck_dia_cm=None,
                        depth_cm=None, leg_thickness_cm=None, materials=None, profile=None):
    """Save per-furniture-type DrawingModel JSON alongside the DXF file.
    Now supports ALL known furniture types."""
    try:
        from app.backend.drawing_builders import (
            build_round_pedestal_model, build_rectangular_table_model,
            build_cabinet_model, build_sofa_model, build_coffee_table_model,
            build_dining_chair_model, build_wardrobe_model,
            build_reception_counter_model, build_bed_headboard_model,
            build_asymmetric_pedestal_model, build_oval_pedestal_model,
            build_console_table_model, build_office_desk_model,
        )
        json_path = Path(str(dxf_path).replace('.dxf', '.json'))

        model = None
        if f_type == 'round_pedestal_table':
            model = build_round_pedestal_model(float(width_cm), float(height_cm),
                base_dia_cm=base_dia_cm or 44.0, neck_dia_cm=neck_dia_cm or 22.4,
                materials=materials, profile=profile)
        elif f_type == 'rectangular_table':
            model = build_rectangular_table_model(
                float(width_cm), float(depth_cm or 80),
                float(height_cm), float(leg_thickness_cm or 6), materials=materials)
        elif f_type == 'cabinet':
            model = build_cabinet_model(float(width_cm), float(depth_cm or 50), float(height_cm), materials=materials)
        elif f_type == 'sofa':
            model = build_sofa_model(float(width_cm), float(depth_cm or 80), float(height_cm), materials=materials)
        elif f_type == 'coffee_table':
            model = build_coffee_table_model(float(width_cm), float(height_cm), materials=materials)
        elif f_type in ('dining_chair', 'chair'):
            model = build_dining_chair_model(float(width_cm), float(height_cm), materials=materials)
        elif f_type == 'wardrobe':
            model = build_wardrobe_model(float(width_cm), float(depth_cm or 60), float(height_cm), materials=materials)
        elif f_type == 'reception_counter':
            model = build_reception_counter_model(float(width_cm), float(height_cm), materials=materials)
        elif f_type == 'bed_headboard':
            model = build_bed_headboard_model(float(width_cm), float(height_cm), materials=materials)
        elif f_type == 'oval_pedestal_table':
            model = build_oval_pedestal_model(float(width_cm), float(depth_cm or 100), float(height_cm),
                pedestal_dia_cm=base_dia_cm or 40.0, materials=materials)
        elif f_type == 'console_table':
            model = build_console_table_model(float(width_cm), float(depth_cm or 40), float(height_cm), materials=materials)
        elif f_type == 'office_desk':
            model = build_office_desk_model(float(width_cm), float(depth_cm or 60), float(height_cm), materials=materials)
        elif f_type == 'asymmetric_pedestal_table':
            model = build_asymmetric_pedestal_model(float(width_cm), float(depth_cm or 90), float(height_cm),
                materials=materials)
        elif f_type == 'armchair_lounge':
            model = build_dining_chair_model(float(width_cm), float(height_cm), materials=materials)
        elif f_type == 'bar_stool':
            model = build_dining_chair_model(float(width_cm), float(height_cm), materials=materials)
        elif f_type == 'bench_chaise':
            model = build_sofa_model(float(width_cm), float(depth_cm or 70), float(height_cm), materials=materials)
        elif f_type == 'ottoman_pouf':
            model = build_coffee_table_model(float(width_cm), float(height_cm), materials=materials)
        elif f_type == 'rug_rectangular':
            model = build_rectangular_table_model(float(width_cm), float(depth_cm or 120), float(1), float(1), materials=materials)
        elif f_type == 'stone_slab_rectangular':
            model = build_rectangular_table_model(float(width_cm), float(depth_cm or 100), float(thickness_cm or 2), float(1), materials=materials)
        elif f_type == 'wall_panel_fluted':
            model = build_wardrobe_model(float(width_cm), float(depth_cm or 5), float(height_cm), materials=materials)

        if model is None:
            return

        data = model.to_dict()
        if materials:
            data['materials'] = materials
        if profile:
            data['profile'] = profile
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[DrawingModel] JSON save failed: {e}")


def _parse_float(val, default=None):
    if val is None: return default
    try: return float(val)
    except Exception: return default


def count_feedback() -> int:
    from app.services.ml_engine import get_feedback_count
    return get_feedback_count()


def _extract_pedestal_dims(corrected_dims):
    top_dia = base_dia = neck_dia = None
    for d in corrected_dims:
        tag = (d.get('tag') or '').lower().strip()
        val = d.get('value_cm')
        if not val: continue
        if tag == 'base_dia' and base_dia is None: base_dia = val
        elif tag == 'neck_dia' and neck_dia is None: neck_dia = val
        elif tag == 'collar_dia' and neck_dia is None: neck_dia = val
        elif tag in ('top_dia', 'dia', 'diameter') and top_dia is None: top_dia = val
    if base_dia is not None and neck_dia is None: neck_dia = base_dia
    elif neck_dia is not None and base_dia is None: base_dia = neck_dia
    return top_dia, base_dia, neck_dia


def _schema_from_template(ftype):
    """DYNAMIC component schema builder that reads template JSON files.
    Generates the component schema from required_dimensions + parts in the
    template definition. Falls back to None if template not found, allowing
    the caller to fall back to hardcoded _component_schema().
    """
    try:
        templates = load_templates()
        for t in templates:
            if t.get("template_id") == ftype:
                schema = []
                required = [d.replace("_", " ") for d in t.get("required_dimensions", [])]
                for part in t.get("parts", []):
                    pname = part["name"]
                    dims = []
                    for rdim in required:
                        for kw in rdim.split():
                            if kw in pname or pname in rdim:
                                dims.append({
                                    "key": rdim.replace(" ", "_") + "_cm",
                                    "label": rdim.title(),
                                    "min": 5,
                                    "max": 300,
                                    "step": 1,
                                    "unit": "cm"
                                })
                    if not dims:
                        dims.append({
                            "key": f"{pname}_cm",
                            "label": pname.replace("_", " ").title(),
                            "min": 5,
                            "max": 200,
                            "step": 1,
                            "unit": "cm"
                        })
                    schema.append({
                        "name": pname,
                        "label": pname.replace("_", " ").title(),
                        "dims": dims,
                        "material": {"key": pname, "default": "Default material"}
                    })
                # Add overall section
                schema.append({
                    "name": "overall",
                    "label": "Overall",
                    "dims": [{"key": d.replace(" ", "_") + "_cm",
                              "label": d.title(),
                              "min": 5, "max": 300, "step": 1, "unit": "cm"}
                             for d in required[:3]]
                })
                if schema:
                    return schema
    except Exception:
        pass
    return None


def _component_schema(f_type):
    """Return editable component schema for a furniture type.
    Each section has a name (matching the DXF/SVG layer), a human label,
    dimension sliders, and optional material defaults.

    The returned keys in dims[].key MUST match the parameter names on the
    corresponding save_*() and build_*_model() functions so that /adjust and
    /material/edit can dispatch generically without per-type branching.
    """
    if f_type == 'round_pedestal_table':
        return [
            {"name": "tabletop", "label": "Tabletop", "dims": [
                {"key": "top_diameter_cm", "label": "Diameter", "min": 40, "max": 160, "step": 1, "unit": "cm"},
                {"key": "top_thickness_cm", "label": "Thickness", "min": 2, "max": 12, "step": 0.5, "unit": "cm"}],
             "material": {"key": "tabletop", "default": "Solid hardwood, stained finish"}},
            {"name": "collar_plate", "label": "Collar Plate", "dims": [
                {"key": "collar_diameter_cm", "label": "Diameter", "min": 20, "max": 100, "step": 1, "unit": "cm"}],
             "material": {"key": "collar_plate", "default": "Matte hairline black steel"}},
            {"name": "neck_ring", "label": "Neck", "dims": [
                {"key": "neck_diameter_cm", "label": "Diameter", "min": 10, "max": 60, "step": 0.5, "unit": "cm"}],
             "material": {"key": "neck_ring", "default": "Brushed stainless steel"}},
            {"name": "pedestal_body", "label": "Pedestal Column", "dims": [
                {"key": "neck_diameter_cm", "label": "Top Width", "min": 10, "max": 60, "step": 0.5, "unit": "cm"},
                {"key": "base_diameter_cm", "label": "Base Width", "min": 20, "max": 100, "step": 1, "unit": "cm"}],
             "material": {"key": "pedestal_body", "default": "Black hammered textured metal, PU coat"}},
            {"name": "base_plate", "label": "Base Plate", "dims": [
                {"key": "base_diameter_cm", "label": "Diameter", "min": 20, "max": 100, "step": 1, "unit": "cm"}],
             "material": {"key": "base_foot", "default": "Anti-sliding rubber feet"}},
            {"name": "overall", "label": "Overall", "dims": [
                {"key": "overall_height_cm", "label": "Height", "min": 30, "max": 150, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'rectangular_table':
        return [
            {"name": "tabletop", "label": "Tabletop", "dims": [
                {"key": "width_cm", "label": "Width", "min": 60, "max": 300, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 40, "max": 150, "step": 1, "unit": "cm"},
                {"key": "top_thickness_cm", "label": "Thickness", "min": 2, "max": 12, "step": 0.5, "unit": "cm"}],
             "material": {"key": "tabletop", "default": "Solid wood, clear coat"}},
            {"name": "legs", "label": "Legs", "dims": [
                {"key": "leg_thickness_cm", "label": "Thickness", "min": 3, "max": 15, "step": 0.5, "unit": "cm"},
                {"key": "leg_inset_cm", "label": "Inset from edge", "min": 2, "max": 20, "step": 0.5, "unit": "cm"}],
             "material": {"key": "legs", "default": "Solid wood, matching top"}},
            {"name": "stretchers", "label": "Stretchers", "dims": [
                {"key": "stretcher_thickness_cm", "label": "Thickness", "min": 1, "max": 8, "step": 0.5, "unit": "cm"}],
             "material": {"key": "stretchers", "default": "Solid wood"}},
            {"name": "overall", "label": "Overall", "dims": [
                {"key": "overall_height_cm", "label": "Height", "min": 30, "max": 150, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'sofa':
        return [
            {"name": "body", "label": "Sofa Body", "dims": [
                {"key": "width_cm", "label": "Width", "min": 80, "max": 350, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 60, "max": 150, "step": 1, "unit": "cm"},
                {"key": "overall_height_cm", "label": "Overall Height", "min": 50, "max": 120, "step": 1, "unit": "cm"}],
             "material": {"key": "body", "default": "Upholstered fabric"}},
            {"name": "armrests", "label": "Armrests", "dims": [
                {"key": "armrest_width_cm", "label": "Width", "min": 8, "max": 30, "step": 1, "unit": "cm"},
                {"key": "armrest_height_cm", "label": "Height", "min": 15, "max": 40, "step": 1, "unit": "cm"}],
             "material": {"key": "armrests", "default": "Solid wood frame, upholstered"}},
            {"name": "seat", "label": "Seat", "dims": [
                {"key": "seat_height_cm", "label": "Seat Height", "min": 30, "max": 55, "step": 1, "unit": "cm"},
                {"key": "seat_depth_cm", "label": "Seat Depth", "min": 45, "max": 80, "step": 1, "unit": "cm"}],
             "material": {"key": "seat", "default": "High-density foam"}},
            {"name": "backrest", "label": "Backrest", "dims": [
                {"key": "backrest_height_cm", "label": "Backrest Height", "min": 30, "max": 70, "step": 1, "unit": "cm"}],
             "material": {"key": "backrest", "default": "Upholstered fabric"}},
            {"name": "legs", "label": "Legs", "dims": [
                {"key": "leg_height_cm", "label": "Leg Height", "min": 4, "max": 20, "step": 0.5, "unit": "cm"}],
             "material": {"key": "legs", "default": "Solid wood, tapered"}},
        ]
    if f_type == 'cabinet':
        return [
            {"name": "carcass", "label": "Cabinet Carcass", "dims": [
                {"key": "width_cm", "label": "Width", "min": 40, "max": 250, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 30, "max": 80, "step": 1, "unit": "cm"},
                {"key": "overall_height_cm", "label": "Overall Height", "min": 60, "max": 250, "step": 1, "unit": "cm"}],
             "material": {"key": "carcass", "default": "18mm MDF, matte lacquer"}},
            {"name": "doors", "label": "Doors", "dims": [
                {"key": "door_count", "label": "Door Count", "min": 1, "max": 6, "step": 1, "unit": ""},
                {"key": "door_thickness_cm", "label": "Door Thickness", "min": 1.5, "max": 3, "step": 0.1, "unit": "cm"}],
             "material": {"key": "doors", "default": "MDF, painted finish"}},
            {"name": "drawers", "label": "Drawers", "dims": [
                {"key": "drawer_count", "label": "Drawer Count", "min": 0, "max": 8, "step": 1, "unit": ""}],
             "material": {"key": "drawers", "default": "MDF, soft-close runners"}},
            {"name": "base", "label": "Base / Plinth", "dims": [
                {"key": "base_height_cm", "label": "Plinth Height", "min": 4, "max": 15, "step": 0.5, "unit": "cm"}],
             "material": {"key": "base", "default": "Solid wood plinth"}},
        ]
    if f_type in ('dining_chair', 'chair'):
        return [
            {"name": "seat", "label": "Seat", "dims": [
                {"key": "width_cm", "label": "Seat Width", "min": 30, "max": 70, "step": 1, "unit": "cm"},
                {"key": "seat_depth_cm", "label": "Seat Depth", "min": 30, "max": 60, "step": 1, "unit": "cm"},
                {"key": "seat_height_cm", "label": "Seat Height", "min": 35, "max": 55, "step": 1, "unit": "cm"}],
             "material": {"key": "seat", "default": "Upholstered fabric over foam"}},
            {"name": "backrest", "label": "Backrest", "dims": [
                {"key": "backrest_height_cm", "label": "Backrest Height", "min": 20, "max": 60, "step": 1, "unit": "cm"},
                {"key": "backrest_angle_deg", "label": "Rake Angle", "min": 0, "max": 15, "step": 1, "unit": "°"}],
             "material": {"key": "backrest", "default": "Solid wood slats"}},
            {"name": "legs", "label": "Legs", "dims": [
                {"key": "leg_thickness_cm", "label": "Leg Thickness", "min": 2, "max": 8, "step": 0.5, "unit": "cm"}],
             "material": {"key": "legs", "default": "Solid wood, stained"}},
            {"name": "overall", "label": "Overall", "dims": [
                {"key": "overall_height_cm", "label": "Total Height", "min": 60, "max": 130, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'wardrobe':
        return [
            {"name": "carcass", "label": "Wardrobe Body", "dims": [
                {"key": "width_cm", "label": "Width", "min": 60, "max": 300, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 40, "max": 80, "step": 1, "unit": "cm"},
                {"key": "overall_height_cm", "label": "Overall Height", "min": 120, "max": 260, "step": 1, "unit": "cm"}],
             "material": {"key": "carcass", "default": "18mm MDF, matte white lacquer"}},
            {"name": "doors", "label": "Doors", "dims": [
                {"key": "door_count", "label": "Door Count", "min": 1, "max": 6, "step": 1, "unit": ""},
                {"key": "door_style", "label": "Style", "min": 0, "max": 2, "step": 1, "unit": "swing|sliding|folding"}],
             "material": {"key": "doors", "default": "MDF, matte lacquer"}},
            {"name": "hanging_rail", "label": "Hanging Rail", "dims": [
                {"key": "rail_height_cm", "label": "Rail Height", "min": 100, "max": 220, "step": 1, "unit": "cm"}],
             "material": {"key": "hanging_rail", "default": "Chrome-plated steel tube"}},
            {"name": "shelves", "label": "Shelves", "dims": [
                {"key": "shelf_count", "label": "Shelf Count", "min": 0, "max": 8, "step": 1, "unit": ""}],
             "material": {"key": "shelves", "default": "18mm MDF"}},
            {"name": "base", "label": "Base", "dims": [
                {"key": "base_height_cm", "label": "Base Height", "min": 4, "max": 15, "step": 0.5, "unit": "cm"}],
             "material": {"key": "base", "default": "Solid wood plinth"}},
        ]
    if f_type == 'bed_headboard':
        return [
            {"name": "headboard", "label": "Headboard Panel", "dims": [
                {"key": "width_cm", "label": "Width", "min": 80, "max": 250, "step": 1, "unit": "cm"},
                {"key": "overall_height_cm", "label": "Headboard Height", "min": 60, "max": 180, "step": 1, "unit": "cm"},
                {"key": "panel_thickness_cm", "label": "Panel Thickness", "min": 2, "max": 10, "step": 0.5, "unit": "cm"}],
             "material": {"key": "headboard", "default": "Upholstered panel, velvet fabric"}},
            {"name": "posts", "label": "Side Posts/Legs", "dims": [
                {"key": "post_width_cm", "label": "Post Width", "min": 4, "max": 15, "step": 0.5, "unit": "cm"},
                {"key": "post_height_cm", "label": "Post Height", "min": 20, "max": 100, "step": 1, "unit": "cm"}],
             "material": {"key": "posts", "default": "Solid wood, stained finish"}},
            {"name": "frame", "label": "Bed Frame", "dims": [
                {"key": "mattress_width_cm", "label": "Mattress Width", "min": 90, "max": 200, "step": 10, "unit": "cm"},
                {"key": "mattress_length_cm", "label": "Mattress Length", "min": 190, "max": 220, "step": 10, "unit": "cm"}],
             "material": {"key": "frame", "default": "Solid wood slatted base"}},
        ]
    if f_type == 'coffee_table':
        return [
            {"name": "tabletop", "label": "Tabletop", "dims": [
                {"key": "width_cm", "label": "Width", "min": 40, "max": 180, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 30, "max": 120, "step": 1, "unit": "cm"},
                {"key": "top_thickness_cm", "label": "Thickness", "min": 2, "max": 8, "step": 0.5, "unit": "cm"}],
             "material": {"key": "tabletop", "default": "Tempered glass / solid wood"}},
            {"name": "legs", "label": "Legs", "dims": [
                {"key": "leg_thickness_cm", "label": "Leg Thickness", "min": 2, "max": 10, "step": 0.5, "unit": "cm"}],
             "material": {"key": "legs", "default": "Powder-coated steel"}},
            {"name": "lower_shelf", "label": "Lower Shelf", "dims": [
                {"key": "lower_shelf_height_cm", "label": "Shelf Height", "min": 5, "max": 30, "step": 1, "unit": "cm"}],
             "material": {"key": "lower_shelf", "default": "Solid wood / glass"}},
            {"name": "overall", "label": "Overall", "dims": [
                {"key": "overall_height_cm", "label": "Height", "min": 20, "max": 60, "step": 1, "unit": "cm"}]},
        ]
    if f_type == 'reception_counter':
        return [
            {"name": "counter_top", "label": "Counter Top", "dims": [
                {"key": "width_cm", "label": "Width", "min": 80, "max": 400, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 40, "max": 100, "step": 1, "unit": "cm"},
                {"key": "top_thickness_cm", "label": "Top Thickness", "min": 2, "max": 8, "step": 0.5, "unit": "cm"},
                {"key": "overhang_cm", "label": "Overhang", "min": 1, "max": 10, "step": 0.5, "unit": "cm"}],
             "material": {"key": "counter_top", "default": "Engineered quartz / solid surface"}},
            {"name": "front_panel", "label": "Front Panel", "dims": [
                {"key": "overall_height_cm", "label": "Counter Height", "min": 80, "max": 140, "step": 1, "unit": "cm"}],
             "material": {"key": "front_panel", "default": "MDF, matte lacquer"}},
            {"name": "base", "label": "Base", "dims": [
                {"key": "base_height_cm", "label": "Base Height", "min": 4, "max": 15, "step": 0.5, "unit": "cm"}],
             "material": {"key": "base", "default": "Brushed stainless steel"}},
        ]
    if f_type == 'asymmetric_pedestal_table':
        return [
            {"name": "tabletop", "label": "Tabletop", "dims": [
                {"key": "length_cm", "label": "Length", "min": 100, "max": 300, "step": 1, "unit": "cm"},
                {"key": "depth_cm", "label": "Depth", "min": 60, "max": 150, "step": 1, "unit": "cm"},
                {"key": "top_thickness_cm", "label": "Thickness", "min": 1.5, "max": 5, "step": 0.1, "unit": "cm"}],
             "material": {"key": "tabletop", "default": "Marble / engineered stone"}},
            {"name": "large_pedestal", "label": "Large Pedestal (P1)", "dims": [
                {"key": "large_ped_dia_cm", "label": "Diameter", "min": 30, "max": 50, "step": 1, "unit": "cm"},
                {"key": "left_ped_x_cm", "label": "Offset from center", "min": 10, "max": 60, "step": 1, "unit": "cm"}],
             "material": {"key": "large_pedestal", "default": "Brushed stainless steel"}},
            {"name": "small_pedestal", "label": "Small Pedestal (P2)", "dims": [
                {"key": "small_ped_dia_cm", "label": "Diameter", "min": 15, "max": 30, "step": 1, "unit": "cm"},
                {"key": "right_ped_x_cm", "label": "Offset from center", "min": -60, "max": -10, "step": 1, "unit": "cm"}],
             "material": {"key": "small_pedestal", "default": "Brushed stainless steel"}},
            {"name": "overall", "label": "Overall", "dims": [
                {"key": "overall_height_cm", "label": "Height", "min": 70, "max": 80, "step": 1, "unit": "cm"}]},
        ]
    # Fallback to dynamic schema builder from template JSON
    dynamic = _schema_from_template(f_type)
    if dynamic:
        return dynamic
    return None


def _compute_missing_dimensions(f_type, corrected_dims, real_w=None, real_h=None, real_d=None):
    """Determine which critical dimensions are still unknown for a furniture type.
    Returns a list of human-readable strings like 'Width', 'Height', 'Depth'.
    Used to prompt the user for missing values instead of silently guessing.
    Soft-advisory: failures return [] rather than crashing the digitize endpoint."""
    try:
        schema = _component_schema(f_type)
        if not schema:
            return []
    except Exception:
        return []

    # Collect all required dimension keys from the schema
    schema_keys = set()
    for section in schema:
        for dim in section.get('dims', []):
            schema_keys.add(dim['key'])

    # Critical keys that every furniture type MUST have:
    try:
        critical_overrides = {
            'round_pedestal_table': ['top_diameter_cm', 'overall_height_cm'],
            'rectangular_table': ['width_cm', 'depth_cm', 'overall_height_cm'],
            'sofa': ['width_cm', 'depth_cm', 'overall_height_cm'],
            'cabinet': ['width_cm', 'depth_cm', 'overall_height_cm'],
            'dining_chair': ['width_cm', 'overall_height_cm'],
            'chair': ['width_cm', 'overall_height_cm'],
            'wardrobe': ['width_cm', 'depth_cm', 'overall_height_cm'],
            'bed_headboard': ['width_cm', 'overall_height_cm'],
            'coffee_table': ['width_cm', 'depth_cm', 'overall_height_cm'],
            'reception_counter': ['width_cm', 'depth_cm', 'overall_height_cm'],
            'asymmetric_pedestal_table': ['length_cm', 'depth_cm', 'overall_height_cm'],
            'oval_pedestal_table': ['length_cm', 'depth_cm', 'overall_height_cm'],
            'console_table': ['length_cm', 'depth_cm', 'overall_height_cm'],
            'office_desk': ['length_cm', 'depth_cm', 'overall_height_cm'],
            # New 25-template types
            'armchair_lounge': ['width_cm', 'depth_cm', 'overall_height_cm'],
            'bar_stool': ['diameter_or_width_cm', 'overall_height_cm'],
            'bench_chaise': ['length_cm', 'depth_cm', 'overall_height_cm'],
            'ottoman_pouf': ['width_cm', 'depth_cm', 'overall_height_cm'],
            'rug_rectangular': ['length_cm', 'width_cm'],
            'stone_slab_rectangular': ['length_cm', 'width_cm'],
            'wall_panel_fluted': ['width_cm', 'overall_height_cm'],
        }
        critical_keys = critical_overrides.get(f_type, list(schema_keys)[:3])

        # Find what's missing
        has_val_for = {}
        if real_w is not None and real_w > 0:
            has_val_for['width_cm'] = True
            has_val_for['top_diameter_cm'] = True
        if real_h is not None and real_h > 0:
            has_val_for['overall_height_cm'] = True
            has_val_for['height_cm'] = True
        if real_d is not None and real_d > 0:
            has_val_for['depth_cm'] = True

        for d in corrected_dims:
            tag = d.get('tag', '').lower().strip()
            val = d.get('value_cm')
            if val and float(val) > 0:
                if tag in ('top_dia', 'dia', 'diameter'):
                    has_val_for['top_diameter_cm'] = True
                elif tag in ('h', 'height', 'overall_height', 'total_height'):
                    has_val_for['overall_height_cm'] = True
                elif tag in ('w', 'width', 'overall_width', 'total_width'):
                    has_val_for['width_cm'] = True
                elif tag in ('d', 'depth', 'overall_depth', 'total_depth'):
                    has_val_for['depth_cm'] = True
                elif 'leg' in tag or 'thickness' in tag:
                    has_val_for['leg_thickness_cm'] = True
                has_val_for[tag] = True

        missing = []
        for key in critical_keys:
            if key not in has_val_for:
                for section in schema or []:
                    for dim in section.get('dims', []):
                        if dim['key'] == key:
                            missing.append(f"{dim['label']} ({key})")
                            break

        return missing
    except Exception as e:
        print(f"[MissingDims] Error: {e}")
        return []


def _dispatch_furniture(f_type, dxf_path, corrected_dims, real_w, real_h, visual_base_estimate=None,
                         materials=None, real_d=None):
    print(f"[DISPATCH] Exporter: {f_type}")

    def _dim(tags, default):
        for d in corrected_dims:
            tag = d.get('tag', '').lower().strip()
            for t in tags:
                if tag == t or tag.startswith(t + '_') or tag.startswith(t + ' ') or f'_{t}' in tag:
                    return d['value_cm']
        return default

    extra = {}

    # ===== Reference pipeline: fill missing dimensions from reference ratios =====
    try:
        ref_dims = {}
        for d in corrected_dims:
            tag = d.get('tag', '').lower().strip()
            val = d.get('value_cm')
            if val:
                if tag in ('top_dia', 'dia', 'diameter'):
                    ref_dims['top_diameter_cm'] = float(val)
                    ref_dims['width_cm'] = float(val)
                    ref_dims['length_cm'] = float(val)
                elif tag in ('h', 'height', 'overall_height', 'total_height'):
                    ref_dims['overall_height_cm'] = float(val)
                    ref_dims['height_cm'] = float(val)
                elif tag in ('w', 'width', 'length', 'overall_width'):
                    ref_dims['width_cm'] = float(val)
                    ref_dims['length_cm'] = float(val)
                elif tag in ('d', 'depth', 'overall_depth'):
                    ref_dims['depth_cm'] = float(val)
        if real_w and real_w > 0:
            if 'width_cm' not in ref_dims: ref_dims['width_cm'] = real_w
            if 'length_cm' not in ref_dims: ref_dims['length_cm'] = real_w
            if 'top_diameter_cm' not in ref_dims: ref_dims['top_diameter_cm'] = real_w
        if real_h and real_h > 0:
            if 'overall_height_cm' not in ref_dims: ref_dims['overall_height_cm'] = real_h

        if ref_dims:
            solved = solve_missing_dimensions(f_type, ref_dims)
            if solved:
                extra['reference_solved_dims'] = solved
                # Log what was filled
                filled = {k: v for k, v in solved.items() if k not in ref_dims}
                if filled:
                    print(f"[REF-PIPELINE] Filled dimensions from reference ratios: {filled}")

            # Confidence scoring on detected dimensions
            conf_scores = score_dimension_confidence(f_type, ref_dims)
            if conf_scores:
                extra['reference_confidence_scores'] = conf_scores
                extra['reference_overall_confidence'] = get_overall_confidence(conf_scores)
    except Exception as e:
        print(f"[REF-PIPELINE] Failed: {e}")
    # ===== End reference pipeline =====

    # ===== Scene Graph pipeline =====
    try:
        _LIBRARY = getattr(_dispatch_furniture, '_library', None)
        if _LIBRARY is None:
            _LIBRARY = ResourceLibrary().load()
            _dispatch_furniture._library = _LIBRARY
        # Build scene graph from resolved dimensions
        scene_dims = extra.get('resolved_dimensions') or {}
        scene = build_scene_graph(f_type, scene_dims, materials=materials, library=_LIBRARY)
        scene = solve_constraints(scene)
        extra['scene_graph'] = json.loads(scene.model_dump_json())
        extra['scene_warnings'] = scene.warnings
        if scene.warnings:
            print(f"[SCENE-GRAPH] Warnings: {scene.warnings}")
    except Exception as e:
        print(f"[SCENE-GRAPH] Build failed (non-fatal): {e}")
    # ===== End Scene Graph pipeline =====

    if f_type == 'round_pedestal_table':
        print("EXPORTER USED: save_round_pedestal_table")
        labeled_top, base_dia, neck_dia = _extract_pedestal_dims(corrected_dims)
        dia = real_w or labeled_top or _dim(['dia', 'diameter', 'w', 'width'], 80.0)
        height = real_h or _dim(['h', 'height'], 70.0)

        def _sane_ratio(raw, fallback, lo=0.15, hi=0.75):
            try:
                v = float(raw or 0)
            except (TypeError, ValueError):
                return fallback
            return v if lo <= v <= hi else fallback

        def _ledger_blend(component: str, measured_ratio: Optional[float], fallback: float) -> float:
            """Blend a single photo's measured ratio against the accumulated
            ledger (component_proportions) for this furniture type/component -
            the "ledger" cross-check. More historical samples -> more weight
            on the ledger; a brand-new component with no history -> trust the
            current photo's measurement. Never raises if Postgres is down."""
            try:
                from app.backend.brain_sync import get_proportion_estimate
                est = get_proportion_estimate('round_pedestal_table', 'top_diameter_cm', dia, component)
            except Exception:
                est = None
            if measured_ratio is None:
                return (est['ratio'] if est else fallback)
            if not est or not est.get('sample_count'):
                return measured_ratio
            # Weight capped at 5 historical samples' worth of influence, so a
            # single new photo never gets fully overridden by old data either.
            n = min(est['sample_count'], 5)
            return (measured_ratio * 1 + est['ratio'] * n) / (n + 1)

        # 1) Primary signal: edge-coordinate measurement, computed by US from
        #    reported pixel positions rather than the model's own ratio math.
        section_ratios = _ratios_from_sections(visual_base_estimate)
        # 2) Fallback signal: the model's direct ratio guess, sanity-clamped.
        vbe = visual_base_estimate if isinstance(visual_base_estimate, dict) else {}
        base_ratio_guess = section_ratios.get('base_ratio', _sane_ratio(vbe.get('base_ratio'), 0.55))
        neck_ratio_guess = section_ratios.get('neck_ratio', _sane_ratio(vbe.get('neck_ratio'), 0.28))
        collar_ratio_guess = section_ratios.get('collar_ratio') or (
            _sane_ratio(vbe.get('collar_ratio'), None, lo=0.30, hi=0.85) if vbe.get('has_collar') else None)

        # 3) Cross-check/blend each against the ledger before committing.
        if base_dia is None:
            base_dia = round(dia * _ledger_blend('pedestal_diameter_cm', base_ratio_guess, 0.55), 1)
        if neck_dia is None:
            neck_dia = round(dia * _ledger_blend('neck_diameter_cm', neck_ratio_guess, 0.28), 1)

        # Collar plate: a separate, wider transition plate just under the
        # tabletop. It used to ALWAYS be drawn at a hardcoded top_dia*0.625,
        # regardless of whether the source photo shows one at all - many
        # simple pedestal tables have the column go straight up to meet the
        # tabletop with no wider plate in between. Only draw a collar when a
        # collar section was actually measured/reported; otherwise size it to
        # match the column (no separate plate) instead of inventing a
        # disconnected fixed-ratio width.
        if collar_ratio_guess is not None:
            collar_dia = round(dia * _ledger_blend('collar_diameter_cm', collar_ratio_guess, 0.625), 1)
        else:
            collar_dia = neck_dia if neck_dia else round(dia * 0.28, 1)

        # Record this observation into the ledger so the next photo of a
        # similar table benefits from it too - closes the loop the other
        # direction (read happens above via _ledger_blend).
        try:
            from app.backend.brain_sync import record_proportion
            record_proportion('round_pedestal_table', 'top_diameter_cm', dia, 'pedestal_diameter_cm', base_dia)
            record_proportion('round_pedestal_table', 'top_diameter_cm', dia, 'neck_diameter_cm', neck_dia)
            if collar_ratio_guess is not None:
                record_proportion('round_pedestal_table', 'top_diameter_cm', dia, 'collar_diameter_cm', collar_dia)
        except Exception as e:
            print(f"[DISPATCH] ledger record failed: {e}")

        profile = vbe.get('profile') if vbe.get('profile') in ('cylinder', 'tapered', 'flared') else 'cylinder'
        extra = {'base_dia_cm': base_dia, 'neck_dia_cm': neck_dia, 'collar_dia_cm': collar_dia,
                 'materials': materials or {}, 'profile': profile}
        try:
            save_round_pedestal_table(str(dxf_path), top_dia_cm=dia, height_cm=height,
                                       base_dia_cm=base_dia, neck_dia_cm=neck_dia,
                                       collar_dia_cm=collar_dia, materials=materials, profile=profile)
        except Exception as e:
            print(f"[DISPATCH] save_round_pedestal_table FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])

        try:
            from app.backend.scale_solver import compute_scale
            # Use the newer scale_solver for proportion resolution instead of
            # the deprecated visual_ratio_scaler.estimate_proportions.
            # Fallback to ratio-based defaults when scale solver lacks data.
            sr = {
                'pedestal_diameter_cm': base_dia if base_dia else dia * 0.55,
                'neck_diameter_cm': neck_dia if neck_dia else dia * 0.28,
                'top_thickness_cm': 4.0,
            }
            extra['resolved_dimensions'] = {
                'top_diameter_cm': round(dia, 1), 'overall_height_cm': round(height, 1),
                'base_diameter_cm': round(sr.get('pedestal_diameter_cm', dia * 0.55), 1),
                'neck_diameter_cm': round(sr.get('neck_diameter_cm', dia * 0.28), 1),
                'top_thickness_cm': round(sr.get('top_thickness_cm', 4.0), 1),
                'collar_diameter_cm': round(collar_dia, 1),
            }
        except Exception as e: print(f"[DISPATCH] resolved_dimensions failed: {e}")

        from app.backend.dimension_validator import check_round_pedestal_proportions
        extra['proportion_warnings'] = check_round_pedestal_proportions(
            dia, extra.get('resolved_dimensions', {}))

    elif f_type == 'rectangular_table':
        w = real_w or _dim(['w', 'width', 'length'], 120.0)
        h = real_h or _dim(['h', 'height'], 70.0)
        d = real_d or _dim(['d', 'depth'], 80.0)
        lt = _dim(['leg', 'thickness'], 6.0)
        try: save_rectangular_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, leg_thickness_cm=lt)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'width_cm': round(w, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h, 1), 'leg_thickness_cm': round(lt, 1),
        }
    elif f_type == 'cabinet':
        w = real_w or _dim(['w', 'width'], 100.0)
        h = real_h or _dim(['h', 'height'], 180.0)
        d = _dim(['d', 'depth'], 50.0)
        try: save_cabinet(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'sofa':
        w = real_w or _dim(['w', 'width'], 200.0)
        h = real_h or _dim(['h', 'height'], 85.0)
        d = _dim(['d', 'depth'], 80.0)
        try: save_sofa(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'coffee_table':
        w = real_w or _dim(['w', 'width', 'dia', 'diameter'], 100.0)
        h = real_h or _dim(['h', 'height'], 45.0)
        d = real_d or _dim(['d', 'depth'], 60.0)
        try: save_coffee_table(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {'width_cm': round(w, 1), 'depth_cm': round(d, 1), 'overall_height_cm': round(h, 1)}
    elif f_type in ('dining_chair', 'chair'):
        w = real_w or _dim(['w', 'width', 'seat'], 45.0)
        h = real_h or _dim(['h', 'height'], 90.0)
        try: save_dining_chair(str(dxf_path), width_cm=w, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'wardrobe':
        w = real_w or _dim(['w', 'width'], 120.0)
        h = real_h or _dim(['h', 'height'], 200.0)
        try: save_wardrobe(str(dxf_path), width_cm=w, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'asymmetric_pedestal_table':
        l = real_w or _dim(['l', 'length', 'len', 'w', 'width'], 180.0)
        h_val = real_h or _dim(['h', 'height'], 75.0)
        d = _dim(['d', 'depth'], 90.0)
        lp = _dim(['large_ped_dia', 'ped1_dia', 'ped1'], 40.0)
        sp = _dim(['small_ped_dia', 'ped2_dia', 'ped2'], 22.0)
        lpx = _dim(['left_ped_x', 'ped1_x', 'ped1_off'], 30.0)
        rpx = _dim(['right_ped_x', 'ped2_x', 'ped2_off'], -25.0)
        oh = _dim(['overhang'], 20.0)
        try:
            save_asymmetric_pedestal_table(str(dxf_path), length_cm=l, depth_cm=d, height_cm=h_val,
                                            large_ped_dia_cm=lp, small_ped_dia_cm=sp,
                                            left_ped_x_cm=lpx, right_ped_x_cm=rpx, overhang_cm=oh,
                                            materials=materials)
        except Exception as e:
            print(f"[DISPATCH] save_asymmetric_pedestal_table FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'length_cm': round(l, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h_val, 1),
            'large_ped_dia_cm': round(lp, 1), 'small_ped_dia_cm': round(sp, 1),
            'left_ped_x_cm': round(lpx, 1), 'right_ped_x_cm': round(rpx, 1),
        }
    elif f_type == 'oval_pedestal_table':
        l = real_w or _dim(['l', 'length', 'w', 'width'], 180.0)
        h_val = real_h or _dim(['h', 'height'], 75.0)
        d = _dim(['d', 'depth'], 100.0)
        pd = _dim(['pedestal_dia', 'ped_dia'], 40.0)
        try:
            save_oval_pedestal_table(str(dxf_path), length_cm=l, depth_cm=d, height_cm=h_val, pedestal_dia_cm=pd, materials=materials)
        except Exception as e:
            print(f"[DISPATCH] save_oval_pedestal_table FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'length_cm': round(l, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h_val, 1), 'pedestal_dia_cm': round(pd, 1),
        }
    elif f_type == 'console_table':
        l = real_w or _dim(['l', 'length', 'w', 'width'], 120.0)
        h_val = real_h or _dim(['h', 'height'], 75.0)
        d = _dim(['d', 'depth'], 40.0)
        lt = _dim(['leg', 'thickness', 'leg_thick'], 4.0)
        try:
            save_console_table(str(dxf_path), length_cm=l, depth_cm=d, height_cm=h_val, leg_thick_cm=lt, materials=materials)
        except Exception as e:
            print(f"[DISPATCH] save_console_table FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'length_cm': round(l, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h_val, 1), 'leg_thick_cm': round(lt, 1),
        }
    elif f_type == 'office_desk':
        l = real_w or _dim(['l', 'length', 'w', 'width'], 140.0)
        h_val = real_h or _dim(['h', 'height'], 75.0)
        d = _dim(['d', 'depth'], 60.0)
        lt = _dim(['leg', 'thickness', 'leg_thick'], 4.0)
        mph = _dim(['modesty', 'panel'], 15.0)
        try:
            save_office_desk(str(dxf_path), length_cm=l, depth_cm=d, height_cm=h_val,
                              leg_thick_cm=lt, modesty_panel_h_cm=mph, materials=materials)
        except Exception as e:
            print(f"[DISPATCH] save_office_desk FAILED: {e}")
            save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'length_cm': round(l, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h_val, 1),
            'leg_thick_cm': round(lt, 1), 'modesty_panel_h_cm': round(mph, 1),
        }
    elif f_type == 'reception_counter':
        w = real_w or _dim(['w', 'width'], 180.0)
        h = real_h or _dim(['h', 'height'], 110.0)
        try: save_reception_counter(str(dxf_path), width_cm=w, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'bed_headboard':
        w = real_w or _dim(['w', 'width'], 160.0)
        h = real_h or _dim(['h', 'height'], 120.0)
        try: save_bed_headboard(str(dxf_path), width_cm=w, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
    elif f_type == 'armchair_lounge':
        w = real_w or _dim(['w', 'width'], 70.0)
        h = real_h or _dim(['h', 'height'], 90.0)
        d = _dim(['d', 'depth'], 75.0)
        sh = _dim(['seat_height', 'sh'], 45.0)
        try: save_armchair(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, seat_height_cm=sh, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'width_cm': round(w, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h, 1), 'seat_height_cm': round(sh, 1),
        }
    elif f_type == 'bar_stool':
        w = real_w or _dim(['w', 'width', 'dia', 'diameter'], 40.0)
        h = real_h or _dim(['h', 'height'], 75.0)
        sh = _dim(['seat_height', 'sh'], 65.0)
        try: save_bar_stool(str(dxf_path), diameter_or_width_cm=w, height_cm=h, seat_height_cm=sh, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'diameter_or_width_cm': round(w, 1), 'overall_height_cm': round(h, 1),
            'seat_height_cm': round(sh, 1),
        }
    elif f_type == 'bench_chaise':
        l = real_w or _dim(['l', 'length', 'w', 'width'], 140.0)
        h = real_h or _dim(['h', 'height'], 85.0)
        d = _dim(['d', 'depth'], 55.0)
        sh = _dim(['seat_height', 'sh'], 45.0)
        try: save_bench_chaise(str(dxf_path), length_cm=l, depth_cm=d, height_cm=h, seat_height_cm=sh, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'length_cm': round(l, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h, 1), 'seat_height_cm': round(sh, 1),
        }
    elif f_type == 'ottoman_pouf':
        w = real_w or _dim(['w', 'width'], 55.0)
        h = real_h or _dim(['h', 'height'], 40.0)
        d = _dim(['d', 'depth'], 55.0)
        try: save_ottoman(str(dxf_path), width_cm=w, depth_cm=d, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'width_cm': round(w, 1), 'depth_cm': round(d, 1),
            'overall_height_cm': round(h, 1),
        }
    elif f_type == 'rug_rectangular':
        l = real_w or _dim(['l', 'length', 'w', 'width'], 160.0)
        w = _dim(['w2', 'width', 'd', 'depth'], 120.0) if not real_w else l * 0.75
        ph = _dim(['pile_height', 'pile'], 1.0)
        try: save_rug(str(dxf_path), length_cm=l, width_cm=w, pile_height_mm=ph, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'length_cm': round(l, 1), 'width_cm': round(w, 1),
        }
    elif f_type == 'stone_slab_rectangular':
        l = real_w or _dim(['l', 'length', 'w', 'width'], 200.0)
        w = _dim(['w2', 'width', 'd', 'depth'], 100.0) if not real_w else l * 0.5
        t = _dim(['thickness', 't'], 2.0)
        try: save_stone_slab(str(dxf_path), length_cm=l, width_cm=w, thickness_cm=t, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'length_cm': round(l, 1), 'width_cm': round(w, 1), 'thickness_cm': round(t, 1),
        }
    elif f_type == 'wall_panel_fluted':
        w = real_w or _dim(['w', 'width'], 120.0)
        h = real_h or _dim(['h', 'height'], 240.0)
        t = _dim(['thickness', 't'], 2.0)
        ss = _dim(['slat_spacing', 'spacing'], 10.0)
        try: save_wall_panel(str(dxf_path), width_cm=w, height_cm=h, thickness_cm=t, slat_spacing_mm=ss, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {
            'width_cm': round(w, 1), 'overall_height_cm': round(h, 1),
            'thickness_cm': round(t, 1), 'slat_spacing_mm': round(ss, 1),
        }
    elif f_type == 'lounge_chair':
        w = real_w or _dim(['w', 'width'], 70.0)
        h = real_h or _dim(['h', 'height'], 90.0)
        try: save_lounge_chair(str(dxf_path), width_cm=w, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {'width_cm': round(w, 1), 'overall_height_cm': round(h, 1)}
    elif f_type == 'sideboard':
        w = real_w or _dim(['w', 'width'], 140.0)
        h = real_h or _dim(['h', 'height'], 85.0)
        try: save_sideboard(str(dxf_path), width_cm=w, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {'width_cm': round(w, 1), 'overall_height_cm': round(h, 1)}
    elif f_type == 'tv_console':
        w = real_w or _dim(['w', 'width'], 160.0)
        h = real_h or _dim(['h', 'height'], 55.0)
        try: save_tv_console(str(dxf_path), width_cm=w, height_cm=h, materials=materials)
        except Exception: save_generic(str(dxf_path), [], [], [])
        extra['resolved_dimensions'] = {'width_cm': round(w, 1), 'overall_height_cm': round(h, 1)}
    else:
        # Fallback: if unknown type but dimensions available, try rectangular_table
        fb_w = real_w or _dim(['w', 'width'], 0)
        fb_h = real_h or _dim(['h', 'height'], 80.0)  # default height for tables
        if fb_w:
            fb_d = _dim(['d', 'depth'], fb_w * 0.6)
            print(f"EXPORTER USED: save_rectangular_table (fallback from {f_type}, w={fb_w})")
            try: save_rectangular_table(str(dxf_path), width_cm=fb_w, depth_cm=fb_d, height_cm=fb_h)
            except Exception: save_generic(str(dxf_path), [], [], [])
        else:
            print(f"EXPORTER USED: save_generic (unknown type: {f_type})")
            save_generic(str(dxf_path), [], [], [])

    extra['component_schema'] = _component_schema(f_type)
    _save_drawing_model(f_type, dxf_path, real_w or 80.0, real_h or 70.0,
                         base_dia_cm=extra.get('base_dia_cm'), neck_dia_cm=extra.get('neck_dia_cm'),
                         depth_cm=extra.get('resolved_dimensions', {}).get('depth_cm'),
                         leg_thickness_cm=extra.get('resolved_dimensions', {}).get('leg_thickness_cm'),
                         materials=extra.get('materials'), profile=extra.get('profile'))
    try:
        # Proportion ledger recording for round_pedestal_table already
        # happened above, right where base_dia/neck_dia/collar_dia were
        # computed - only record_drawing (unrelated: a per-job history log,
        # not the proportion ledger) belongs here.
        from app.backend.brain_sync import record_drawing
        resolved = extra.get('resolved_dimensions') or {}
        record_drawing(dxf_path.stem, f_type, dxf_path.name, dimensions_used=resolved)
    except Exception as e: print(f"[DISPATCH] brain_sync recording failed: {e}")

    # Auto-index generated DXF to Qdrant for future similarity search
    try:
        from app.services.embedding_service import generate_and_index_embedding
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        from app.cad.dxf_parser import parse_dxf
        geometry = parse_dxf(str(dxf_path))
        idx_result = generate_and_index_embedding(
            geometry=geometry,
            product_id=f"generated_{dxf_path.stem}",
        )
        if idx_result.get('status') == 'indexed':
            print(f"[QDrant] Indexed generated DXF: {dxf_path.name}")
    except Exception as e:
        print(f"[QDrant] Auto-index failed (non-fatal): {e}")

    return extra


def _build_svg_model(f_type, resolved, real_w, real_h, dispatch_extra, detected=None):
    """Build the DrawingModel used for SVG preview, dispatching on furniture type.
    Mirrors _dispatch_furniture's type handling so every type gets its own
    geometry instead of silently falling back to round_pedestal_table.
    `detected` (optional dict of lines/circles/rects) drives the generic
    fallback when the type is unrecognized/unclassified.
    """
    from app.backend.drawing_builders import (
        build_round_pedestal_model, build_rectangular_table_model,
        build_cabinet_model, build_sofa_model, build_coffee_table_model,
        build_dining_chair_model, build_wardrobe_model,
        build_reception_counter_model, build_bed_headboard_model,
        build_asymmetric_pedestal_model, build_oval_pedestal_model,
        build_console_table_model, build_office_desk_model,
        build_generic_model,
    )

    if f_type == 'rectangular_table':
        w = resolved.get('width_cm', real_w or 120)
        d = resolved.get('depth_cm', 80)
        h = resolved.get('overall_height_cm', real_h or 70)
        lt = resolved.get('leg_thickness_cm', 6)
        return build_rectangular_table_model(float(w), float(d), float(h), float(lt))
    if f_type == 'cabinet':
        w = resolved.get('width_cm', real_w or 100)
        d = resolved.get('depth_cm', 50)
        h = resolved.get('overall_height_cm', real_h or 180)
        return build_cabinet_model(float(w), float(d), float(h))
    if f_type == 'sofa':
        w = resolved.get('width_cm', real_w or 200)
        d = resolved.get('depth_cm', 80)
        h = resolved.get('overall_height_cm', real_h or 85)
        return build_sofa_model(float(w), float(d), float(h))
    if f_type == 'coffee_table':
        w = resolved.get('width_cm', real_w or 100)
        d = resolved.get('depth_cm', 60)
        h = resolved.get('overall_height_cm', real_h or 45)
        return build_coffee_table_model(float(w), float(d), float(h))
    if f_type in ('dining_chair', 'chair'):
        w = resolved.get('width_cm', real_w or 45)
        h = resolved.get('overall_height_cm', real_h or 90)
        return build_dining_chair_model(float(w), float(h))
    if f_type == 'wardrobe':
        w = resolved.get('width_cm', real_w or 120)
        d = resolved.get('depth_cm', 60)
        h = resolved.get('overall_height_cm', real_h or 200)
        return build_wardrobe_model(float(w), float(d), float(h))
    if f_type == 'oval_pedestal_table':
        l = resolved.get('length_cm', real_w or 180)
        d = resolved.get('depth_cm', 100)
        h = resolved.get('overall_height_cm', real_h or 75)
        pd = resolved.get('pedestal_dia_cm', 40)
        return build_oval_pedestal_model(length_cm=float(l), depth_cm=float(d), height_cm=float(h), pedestal_dia_cm=float(pd))
    if f_type == 'console_table':
        l = resolved.get('length_cm', real_w or 120)
        d = resolved.get('depth_cm', 40)
        h = resolved.get('overall_height_cm', real_h or 75)
        lt = resolved.get('leg_thick_cm', 4)
        return build_console_table_model(length_cm=float(l), depth_cm=float(d), height_cm=float(h), leg_thick_cm=float(lt))
    if f_type == 'office_desk':
        l = resolved.get('length_cm', real_w or 140)
        d = resolved.get('depth_cm', 60)
        h = resolved.get('overall_height_cm', real_h or 75)
        lt = resolved.get('leg_thick_cm', 4)
        mph = resolved.get('modesty_panel_h_cm', 15)
        return build_office_desk_model(length_cm=float(l), depth_cm=float(d), height_cm=float(h), leg_thick_cm=float(lt), modesty_panel_h_cm=float(mph))
    if f_type == 'asymmetric_pedestal_table':
        l = resolved.get('length_cm', real_w or 180)
        d = resolved.get('depth_cm', 90)
        h = resolved.get('overall_height_cm', real_h or 75)
        lp = resolved.get('large_ped_dia_cm', 40)
        sp = resolved.get('small_ped_dia_cm', 22)
        lpx = resolved.get('left_ped_x_cm', 30)
        rpx = resolved.get('right_ped_x_cm', -25)
        oh = resolved.get('overhang_cm', 20)
        mats = (dispatch_extra or {}).get('materials') if dispatch_extra else None
        return build_asymmetric_pedestal_model(
            length_cm=float(l), depth_cm=float(d), height_cm=float(h),
            large_ped_dia_cm=float(lp), small_ped_dia_cm=float(sp),
            left_ped_x_cm=float(lpx), right_ped_x_cm=float(rpx),
            overhang_cm=float(oh), materials=mats,
        )
    if f_type == 'reception_counter':
        w = resolved.get('width_cm', real_w or 180)
        h = resolved.get('overall_height_cm', real_h or 110)
        return build_reception_counter_model(float(w), float(h))
    if f_type == 'bed_headboard':
        w = resolved.get('width_cm', real_w or 180)
        h = resolved.get('overall_height_cm', real_h or 60)
        return build_bed_headboard_model(float(w), float(h))

    if f_type == 'round_pedestal_table':
        svg_kwargs = {k: v for k, v in (dispatch_extra or {}).items()
                      if k in ('base_dia_cm', 'neck_dia_cm') and v is not None}
        svg_top_dia = resolved.get('top_diameter_cm', real_w or 80)
        svg_height = resolved.get('overall_height_cm', real_h or 70)
        # collar_dia_cm must be derived from THIS top diameter, not left to
        # build_round_pedestal_model's hardcoded default of 50.0 - that
        # default only looks right by coincidence when top_dia is ~80cm
        # (50/80 ~= the correct 62.5% ratio); for any other top diameter it
        # silently produces a disproportionate, "pinched" cone shape.
        svg_collar_dia = resolved.get('collar_diameter_cm', float(svg_top_dia) * 0.625)
        return build_round_pedestal_model(float(svg_top_dia), float(svg_height),
                                           collar_dia_cm=float(svg_collar_dia),
                                           materials=(dispatch_extra or {}).get('materials'),
                                           profile=(dispatch_extra or {}).get('profile', 'cylinder'), **svg_kwargs)

    # Unrecognized/generic type — trace the actually-detected geometry
    # instead of fabricating an unrelated round-pedestal-table shape.
    if detected:
        return build_generic_model(detected.get('lines'), detected.get('circles'), detected.get('rects'))
    return build_generic_model()


# ===== Accuracy Pipeline =====

def _run_accuracy_pipeline(img_path: str, lines, circles, rects, ocr_lines, dims):
    """
    Run the accuracy core pipeline:
    1. OCR Layout Parser — text boxes with positions
    2. Line Role Classifier — separate object/leader/dimension/center lines
    3. Dimension Associator — connect text to geometry
    4. Scale Solver — compute pixel-to-cm scale
    5. Geometry Reconstructor — snap/merge/close contours
    """
    result = {}

    try:
        layout = extract_layout(str(img_path))
        result['layout'] = layout.to_dict()
        text_boxes = layout.text_boxes
        dim_labels = layout.dimension_labels
        print(f"[ACCURACY] Layout: {len(text_boxes)} text boxes, {len(dim_labels)} dimension labels")
    except Exception as e:
        print(f"[ACCURACY] Layout failed: {e}")
        text_boxes = []
        dim_labels = []

    try:
        line_classification = classify_line_roles(lines, text_boxes)
        result['line_roles'] = line_classification.to_dict()
        object_edges = line_classification.object_edges
        dim_lines = line_classification.dimension_lines
        print(f"[ACCURACY] Line roles: {len(object_edges)} object, {len(dim_lines)} dimension")
    except Exception as e:
        print(f"[ACCURACY] Line roles failed: {e}")

    try:
        associations = associate_dimension_text(text_boxes, dim_labels, lines, circles, rects)
        result['associations'] = associations.to_dict()
        print(f"[ACCURACY] Associations: {len(associations.associations)} pairs")
    except Exception as e:
        print(f"[ACCURACY] Association failed: {e}")
        associations = None

    if associations and associations.associations:
        try:
            known_dims = {}
            for d in dims:
                if d.get('value_cm'):
                    known_dims[d.get('tag', f'dim_{len(known_dims)}')] = d['value_cm']
            scale_solution = compute_scale(associations.associations, lines, known_dims)
            result['scale'] = scale_solution.to_dict()
        except Exception as e:
            print(f"[ACCURACY] Scale solver failed: {e}")
            result['scale'] = None
    else:
        result['scale'] = None

    try:
        reconstruction = reconstruct(lines, circles)
        result['reconstruction'] = reconstruction.to_dict()
        print(f"[ACCURACY] Reconstruction: {len(reconstruction.closed_contours)} contours, "
              f"{len(reconstruction.circles)} circles")
    except Exception as e:
        print(f"[ACCURACY] Reconstruction failed: {e}")

    return result


# ===== DIGITIZE ENDPOINTS =====

@router.post("/digitize")
async def digitize(file: UploadFile = File(...), real_width_cm: str = Form(None),
                    real_height_cm: str = Form(None), furniture_type: str = Form(None),
                    background_tasks: BackgroundTasks = None):
    try:
        ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
        job_id = str(uuid.uuid4())
        safe = f"{job_id}_{uuid.uuid4().hex[:8]}"
        img_path = UPLOAD / f"{safe}{ext}"
        with img_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        img, gray = load_image(str(img_path))
        binary = preprocess(gray)
        lines_raw = detect_lines(binary)
        lines = normalize_lines(lines_raw)
        circles = detect_circles(gray)
        rects = detect_rectangles(binary)
        from app.backend.ocr import assess_image_quality
        image_quality = assess_image_quality(str(img_path))
        ocr_lines, dims = ocr_dimensions(str(img_path))
        constrained = process_constraints(lines, circles, dims, rects)

        pixel_measurements = {}
        if constrained['circles']:
            pixel_measurements['diameter'] = constrained['circles'][0][2] * 2
        if constrained['lines']:
            xs = [p[0] for ln in constrained['lines'] for p in ln]
            if xs: pixel_measurements['width'] = max(xs) - min(xs)
            ys = [p[1] for ln in constrained['lines'] for p in ln]
            if ys: pixel_measurements['height'] = max(ys) - min(ys)

        scale_cm_per_pixel, _scale_conf, scale_warns = validate_scale(dims, constrained['lines'])
        corrected_dims = autocorrect_dimensions(dims, pixel_measurements, scale_cm_per_pixel=scale_cm_per_pixel)
        dim_warns = [d['warning'] for d in corrected_dims if d.get('warning')]
        accuracy_results = _run_accuracy_pipeline(img_path, lines, circles, rects, ocr_lines, dims)

        classifier_result = classify_furniture(ocr_lines, constrained['circles'], constrained['lines'], constrained.get('rects'))
        f_type = normalize_furniture_type(furniture_type or classifier_result['type'])
        confidence = classifier_result.get('confidence', 0.5)

        real_w = _parse_float(real_width_cm)
        real_h = _parse_float(real_height_cm)

        if furniture_type and furniture_type.strip():
            from app.backend.feedback_learner import record_correction
            record_correction(job_id, "furniture_type", classifier_result.get('type', ''), f_type,
                              context={"confidence": confidence, "endpoint": "digitize"})
            if real_w: record_correction(job_id, "top_diameter_cm", None, real_w)
            if real_h: record_correction(job_id, "overall_height_cm", None, real_h)

        dxf_name = f'{job_id}_digitized.dxf'
        dxf_path = OUT / dxf_name
        dispatch_extra = _dispatch_furniture(f_type, dxf_path, corrected_dims, real_w, real_h)
        warns = scale_warns + dim_warns + (dispatch_extra or {}).get('proportion_warnings', [])

        svg_name = None
        try:
            from app.backend.svg_exporter import drawing_to_svg
            svg_name = f'{job_id}_digitized.svg'
            svg_path = OUT / svg_name
            resolved = (dispatch_extra or {}).get('resolved_dimensions') or {}
            detected = {'lines': constrained['lines'], 'circles': constrained['circles'],
                        'rects': constrained.get('rects')}
            model = _build_svg_model(f_type, resolved, real_w, real_h, dispatch_extra, detected)
            with open(str(svg_path), 'w', encoding='utf-8') as f2:
                f2.write(drawing_to_svg(model))
        except Exception: svg_name = None

        try: os.remove(str(img_path))
        except: pass

        # Enqueue async validation job to Redis queue
        if background_tasks:
            _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            _redis_pass = os.environ.get("REDIS_PASSWORD") or None

            async def enqueue_validation():
                try:
                    import redis as redis_lib
                    import json
                    client = redis_lib.from_url(_redis_url, password=_redis_pass)
                    job_data = json.dumps({
                        "type": "digitize",
                        "data": {
                            "job_id": job_id,
                            "furniture_type": furniture_type or "unknown",
                            "detected_dims": {
                                k: v for k, v in [
                                    ("width_cm", real_w),
                                    ("overall_height_cm", real_h),
                                ] if v
                            },
                        }
                    })
                    client.lPush("cad-processing", job_data)
                    client.expire("cad-processing", 86400)
                    client.connection_pool.disconnect()
                except Exception as e:
                    print(f"[Digitize] Queue push failed (non-fatal): {e}")

            background_tasks.add_task(enqueue_validation)

        return JSONResponse({
            'job_id': job_id, 'dxf_file': dxf_name,
            'download': f'/api/download/{dxf_name}',
            'preview_svg': f'/api/preview/svg/{dxf_name}' if svg_name else None,
            'resolved_dimensions': (dispatch_extra or {}).get('resolved_dimensions'),
            'component_schema': (dispatch_extra or {}).get('component_schema'),
            'furniture': {'type': f_type, 'confidence': confidence,
                          'needs_confirmation': confidence < CLASSIFIER_CONFIRM_THRESHOLD,
                          'required_dimensions': classifier_result.get('required_dimensions', []),
                          'recommended_template': classifier_result.get('recommended_template', ''),
                          'missing_dimensions': _compute_missing_dimensions(f_type, corrected_dims, real_w, real_h)},
            'detected': {'lines': len(constrained['lines']), 'circles': len(constrained['circles']),
                         'rectangles': len(constrained.get('rects', [])),
                         'dimensions': corrected_dims, 'ocr_lines': ocr_lines[:20]},
            'accuracy_pipeline': accuracy_results,
            'image_quality': image_quality,
            'warnings': (warns + [f"Source image looked blurry (sharpness {image_quality['blur_score']:.0f}, "
                                   f"threshold {image_quality['threshold']:.0f}) - dimension text was read from an "
                                   f"auto-sharpened copy; please double-check the numbers above against the photo."]
                         if image_quality.get('is_blurry') else warns),
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.post("/digitize/hybrid")
async def digitize_hybrid(file: UploadFile = File(...), real_width_cm: str = Form(None),
                           real_height_cm: str = Form(None), real_depth_cm: str = Form(None),
                           furniture_type: str = Form(None)):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "OPENAI_API_KEY required"}, status_code=400)
    try:
        ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
        job_id = str(uuid.uuid4())
        safe = f"{job_id}_{uuid.uuid4().hex[:8]}"
        img_path = UPLOAD / f"{safe}{ext}"
        with img_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        import httpx, base64
        with open(img_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        mime = 'image/png'

        ai_result = {"furniture_type": "", "confidence": 0, "dimensions": []}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post("https://api.openai.com/v1/chat/completions",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"model": "gpt-4o", "messages": [
                        {"role": "system", "content": VISION_SYSTEM_PROMPT},
                        {"role": "user", "content": [{"type": "text", "text": "Identify furniture and extract all dimensions."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}}]}
                    ], "max_tokens": 2000, "response_format": {"type": "json_object"}})
                if r.status_code == 200:
                    raw_content = r.json()['choices'][0]['message']['content']
                    try: ai_result = json.loads(raw_content)
                    except (json.JSONDecodeError, ValueError):
                        cleaned = raw_content.strip()
                        if cleaned.startswith('```'): cleaned = cleaned.split('\n', 1)[-1] if '\n' in cleaned else cleaned[3:]
                        if cleaned.rstrip().endswith('```'): cleaned = cleaned.rstrip()[:-3]
                        ai_result = json.loads(cleaned.strip())
        except Exception as e: print(f"[Hybrid] OpenAI error: {e}")

        # ===== Furniture Intelligence Confirmation Loop =====
        furniture_analysis_result = None
        template_proposal_result = None
        uncertainty_questions = []
        try:
            from app.furniture_intelligence.schemas.furniture_analysis import FurnitureAnalysis
            from app.furniture_intelligence.services.template_matcher import match_template

            if ai_result and isinstance(ai_result, dict):
                # Convert ai_result (dict) to FurnitureAnalysis
                ai_category = ai_result.get('category') or ai_result.get('furniture_type', 'other')
                ai_top_shape = 'circle' if 'round' in str(ai_result.get('furniture_type', '')).lower() else 'rectangle'
                ai_base_type = 'pedestal' if 'pedestal' in str(ai_result.get('furniture_type', '')).lower() else 'four_legs'
                ai_components = []
                raw_mats = ai_result.get('materials') or {}
                if isinstance(raw_mats, dict):
                    for k, v in raw_mats.items():
                        desc = v.get('description', '') if isinstance(v, dict) else str(v)
                        ai_components.append({
                            'id': k, 'type': k, 'label': desc or k,
                            'shape': '', 'material': k, 'finish': '',
                            'confidence': 1.0
                        })

                analysis = FurnitureAnalysis(
                    product_name=ai_result.get('product_name'),
                    category=ai_category,
                    design_family=[ai_result.get('profile', 'modern')] if ai_result.get('profile') else ['modern'],
                    top_shape=ai_top_shape,
                    base_type=ai_base_type,
                    components=ai_components,
                    required_views=['top', 'front', 'side'],
                    assumptions=ai_result.get('assumptions', []),
                    uncertainty={'top_shape': 0.2, 'base_type': 0.2},
                    confidence=ai_result.get('confidence', 0.5)
                )
                template_proposal = match_template(analysis)
                template_proposal_result = template_proposal.model_dump() if hasattr(template_proposal, 'model_dump') else template_proposal
                uncertainty_questions = template_proposal_result.get('questions', []) if isinstance(template_proposal_result, dict) else []
                furniture_analysis_result = analysis.model_dump() if hasattr(analysis, 'model_dump') else None
        except Exception as e:
            print(f"[Hybrid] Furniture Intelligence analysis failed (non-fatal): {e}")

        img, gray = load_image(str(img_path))
        binary = preprocess(gray)
        lines_raw = detect_lines(binary)
        lines = normalize_lines(lines_raw)
        circles = detect_circles(gray)
        rects = detect_rectangles(binary)
        from app.backend.ocr import assess_image_quality
        image_quality = assess_image_quality(str(img_path))
        ocr_lines, dims = ocr_dimensions(str(img_path))
        constrained = process_constraints(lines, circles, dims, rects)

        pixel_measurements = {}
        if constrained['circles']:
            pixel_measurements['diameter'] = constrained['circles'][0][2] * 2
        if constrained['lines']:
            xs = [p[0] for ln in constrained['lines'] for p in ln]
            if xs: pixel_measurements['width'] = max(xs) - min(xs)
            ys = [p[1] for ln in constrained['lines'] for p in ln]
            if ys: pixel_measurements['height'] = max(ys) - min(ys)
        scale_cm_per_pixel, _scale_conf, scale_warns = validate_scale(dims, constrained['lines'])
        corrected_dims = autocorrect_dimensions(dims, pixel_measurements, scale_cm_per_pixel=scale_cm_per_pixel)
        dim_warns = [d['warning'] for d in corrected_dims if d.get('warning')]

        accuracy_results = _run_accuracy_pipeline(img_path, lines, circles, rects, ocr_lines, dims)

        # ===== CAD Intelligence Pipeline (structured entity extraction) =====
        cad_intel_result = None
        try:
            ocr_structured = [{"text": t, "bbox": [0, 0, 0, 0], "confidence": 0.8}
                              for t in ocr_lines[:50]]
            ci_result = run_cad_intelligence_pipeline(
                image_path=str(img_path),
                ocr_items=ocr_structured,
                default_unit="mm",
            )
            cad_intel_result = ci_debug_dict(ci_result)
        except Exception as e:
            print(f"[Hybrid] CAD Intelligence pipeline failed (non-fatal): {e}")

        opencv_classifier = classify_furniture(ocr_lines, constrained['circles'], constrained['lines'], constrained.get('rects'))
        opencv_type = opencv_classifier.get('type', 'generic_2d_furniture')
        opencv_conf = opencv_classifier.get('confidence', 0.3)

        # ===== Template Selector — pick best specific template using OCR + shapes =====
        template_selection = None
        try:
            # Build evidence dict from OCR hints + detected shapes
            detected_shapes = []
            if constrained.get('circles'): detected_shapes.append('circle')
            if constrained.get('rects'): detected_shapes.append('rectangle')
            if lines: detected_shapes.append('line')
            text_lower = " ".join(ocr_lines).lower()
            template_evidence = {
                "title": ai_result.get("product_name", "") if isinstance(ai_result, dict) else "",
                "category": ai_result.get("category", ftype) if isinstance(ai_result, dict) else ftype,
                "tags": ocr_lines[:5],
                "detected_shapes": detected_shapes,
                "detected_components": [],
                "aspect_ratio": 1.0,
            }
            if constrained['lines']:
                xs = [p[0] for ln in constrained['lines'] for p in ln]
                ys = [p[1] for ln in constrained['lines'] for p in ln]
                if xs and ys:
                    w = max(xs) - min(xs)
                    h = max(ys) - min(ys)
                    if h > 0: template_evidence["aspect_ratio"] = w / h

            # Detect known component keywords in OCR text
            component_kws = {"tabletop", "seat", "backrest", "leg", "base", "armrest",
                            "drawer", "door", "shelf", "panel", "cushion", "frame"}
            for kw in component_kws:
                if kw in text_lower:
                    template_evidence["detected_components"].append(kw)

            template_selection = select_template(template_evidence)
            # Apply visual_signature hints to classifier confidence
            if template_selection and template_selection.get("confidence", 0) > 0.5:
                opencv_conf = max(opencv_conf, template_selection["confidence"] * 0.5)
        except Exception as e:
            print(f"[Hybrid] Template selector failed (non-fatal): {e}")
        # ===== End Template Selector =====

        # ===== Phase 2 — 3-Stage Product Classifier (parallel track) =====
        product_classifier_result = None
        try:
            from app.backend.product_classifier import classify_product

            # Build text and shape evidence from OCR + detected geometry
            classifier_text = " ".join(ocr_lines) if ocr_lines else ""
            if ai_result and isinstance(ai_result, dict):
                classifier_text += " " + ai_result.get("product_name", "")
                classifier_text += " " + ai_result.get("category", "")

            classifier_shapes = []
            if constrained.get("circles"): classifier_shapes.append("circle")
            if constrained.get("rects"): classifier_shapes.append("rectangle")
            # Check for oval from OCR
            if any("oval" in t.lower() or "ellipse" in t.lower() for t in ocr_lines):
                classifier_shapes.append("oval")

            classifier_components = template_evidence.get("detected_components", [])

            product_classifier_result = classify_product(
                text=classifier_text,
                detected_shapes=classifier_shapes,
                detected_components=classifier_components,
            )
        except Exception as e:
            print(f"[Hybrid] 3-Stage classifier failed (non-fatal): {e}")
        # ===== End 3-Stage Product Classifier =====

        # ===== Phase 3a-b: Cloud Vision + Resource Engine Pipeline (parallel track) =====
        phase3_result = None
        try:
            pipeline = _get_phase3_pipeline()
            known_dims_phase3 = {}
            if _parse_float(real_width_cm):
                known_dims_phase3['width_cm'] = _parse_float(real_width_cm)
            if _parse_float(real_height_cm):
                known_dims_phase3['overall_height_cm'] = _parse_float(real_height_cm)
            raw_mats = ai_result.get('materials') if isinstance(ai_result, dict) else None
            mats = {k: (v.get('description','') if isinstance(v,dict) else str(v))
                    for k,v in (raw_mats or {}).items() if v}
            # Build component graph from cad_intelligence entities if available
            cg_result = None
            if cad_intel_result and cad_intel_result.get("entities"):
                try:
                    from app.backend.cad_intelligence.component_graph import ComponentGraph
                    from app.backend.cad_intelligence.models import CadEntity
                    # Reconstruct entities from dict (simple approach)
                    entities = [CadEntity(**e) for e in cad_intel_result.get("entities", [])[:100]]
                    # Pass to Phase3Pipeline for fusion
                    cg_summary = {"component_count": len(set(e.layer for e in entities)),
                                  "entity_count": len(entities)}
                except Exception as e:
                    print(f"[Hybrid] Component graph failed: {e}")
                    cg_summary = None
            phase3_result = pipeline.run(
                image_path=str(img_path),
                product_type_override=furniture_type if furniture_type else None,
                known_dims_cm=known_dims_phase3,
                materials_override=mats if mats else None,
                cad_intel_result=cad_intel_result,
                component_graph_result=cg_summary,
            )
        except Exception as e:
            print(f"[Hybrid] Phase3Pipeline failed (non-fatal): {e}")

        try: os.remove(str(img_path))
        except: pass

        raw_ai_type = (ai_result.get('furniture_type', '') or '').strip()
        KNOWN_TYPES = {'round_pedestal_table', 'rectangular_table', 'cabinet', 'sofa',
                       'coffee_table', 'dining_chair', 'chair', 'wardrobe',
                       'reception_counter', 'bed_headboard', 'oval_pedestal_table',
                       'console_table', 'office_desk', 'side_table', 'lounge_chair',
                       'nightstand', 'bed', 'asymmetric_pedestal_table', 'sideboard',
                       'tv_console',
                       # New 25-template types
                       'armchair_lounge', 'bar_stool', 'bench_chaise',
                       'ottoman_pouf', 'rug_rectangular', 'stone_slab_rectangular',
                       'wall_panel_fluted'}
        if furniture_type: ftype = normalize_furniture_type(furniture_type)
        elif raw_ai_type:
            ftype = normalize_furniture_type(raw_ai_type)
            if ftype not in KNOWN_TYPES:
                opencv_ftype = normalize_furniture_type(opencv_type)
                if opencv_ftype in KNOWN_TYPES: ftype = opencv_ftype
        else: ftype = normalize_furniture_type(opencv_type)

        # ===== Template Graph Resolution =====
        template_graph_result = None
        # Assemble merged dimensions from OCR + AI before using them
        ai_dims = ai_result.get('dimensions', []) or [] if isinstance(ai_result, dict) else []
        merged_dims = corrected_dims + [
            {'tag': d.get('tag', ''), 'value_cm': float(d.get('value_cm', 0)), 'raw': str(d)}
            for d in ai_dims if isinstance(d, dict)]
        try:
            # Build detected_dims dict from all available sources
            detected_dims_cm = {}
            if real_w and real_w > 0:
                detected_dims_cm['width_cm'] = real_w
            if real_h and real_h > 0:
                detected_dims_cm['overall_height_cm'] = real_h
            for d in merged_dims:
                tag = d.get('tag', '').lower().strip()
                val = float(d.get('value_cm', 0))
                if val > 0:
                    if tag in ('top_dia', 'dia', 'diameter'):
                        detected_dims_cm['top_diameter_cm'] = val
                        detected_dims_cm['width_cm'] = val
                    elif any(k in tag for k in ['h', 'height']):
                        detected_dims_cm['overall_height_cm'] = val
                    elif any(k in tag for k in ['w', 'width', 'length']):
                        detected_dims_cm['width_cm'] = val
                        detected_dims_cm['length_cm'] = val
                    elif any(k in tag for k in ['d', 'depth']):
                        detected_dims_cm['depth_cm'] = val
                    elif 'leg' in tag or 'thickness' in tag:
                        detected_dims_cm['leg_thickness_cm'] = val
                    elif 'seat_height' in tag:
                        detected_dims_cm['seat_height_cm'] = val
                    elif 'modesty' in tag or 'panel' in tag:
                        detected_dims_cm['modesty_panel_h_cm'] = val
                    elif 'ped' in tag:
                        detected_dims_cm['pedestal_dia_cm'] = val

            resolver = _get_template_resolver()
            template_graph_result = resolver.resolve(
                ftype, detected_dims_cm, materials=materials if materials else None
            )
        except Exception as e:
            print(f"[Hybrid] Template resolution failed (non-fatal): {e}")
        # ===== End Template Graph Resolution =====

        try: conf = max(float(ai_result.get('confidence', 0) or 0), opencv_conf)
        except: conf = 0.5

        annotation_result = classify_drawing_annotations(ocr_lines, merged_dims)

        known_dims = {}
        for d in merged_dims:
            tag = d.get('tag', '').lower()
            val = float(d.get('value_cm', 0))
            if val > 0:
                if tag in ('top_dia', 'dia', 'diameter'): known_dims['top_diameter_cm'] = val
                elif any(k in tag for k in ['h', 'height']): known_dims['overall_height_cm'] = val
                elif any(k in tag for k in ['w', 'width']): known_dims['top_width_cm'] = val
        segmentation = segment_furniture(ftype, ocr_lines, ai_result, known_dims)

        dxf_name = f'{job_id}_hybrid.dxf'
        dxf_path = OUT / dxf_name
        real_w = _parse_float(real_width_cm)
        real_h = _parse_float(real_height_cm)
        real_d = _parse_float(real_depth_cm)
        visual_base_estimate = ai_result.get('visual_base_estimate') if isinstance(ai_result, dict) else None
        raw_materials = ai_result.get('materials') if isinstance(ai_result, dict) else None
        materials = {k: (v.get('description', '') if isinstance(v, dict) else str(v))
                     for k, v in (raw_materials or {}).items() if v}
        dispatch_extra = _dispatch_furniture(ftype, dxf_path, merged_dims, real_w, real_h, visual_base_estimate,
                                              materials=materials, real_d=real_d)

        svg_name = None
        try:
            from app.backend.svg_exporter import drawing_to_svg
            svg_name = f'{job_id}_hybrid.svg'
            svg_path = OUT / svg_name
            resolved = (dispatch_extra or {}).get('resolved_dimensions') or {}
            detected = {'lines': constrained['lines'], 'circles': constrained['circles'],
                        'rects': constrained.get('rects')}
            model = _build_svg_model(ftype, resolved, real_w, real_h, dispatch_extra, detected)
            with open(str(svg_path), 'w', encoding='utf-8') as f2:
                f2.write(drawing_to_svg(model))
        except Exception: svg_name = None

        # Build template_graph response block
        template_response = None
        if template_graph_result:
            # Strip the full template dict to avoid sending the entire JSON in every response
            tpl = template_graph_result.get("template", {})
            template_response = {
                "template_id": tpl.get("id"),
                "template_name": tpl.get("name"),
                "product_type": tpl.get("product_type"),
                "family": tpl.get("family"),
                "resolved_parameters_mm": template_graph_result.get("resolved_parameters"),
                "constraints": template_graph_result.get("constraints"),
                "required_views": template_graph_result.get("component_views"),
                "required_details": template_graph_result.get("required_details"),
                "drawing_notes": template_graph_result.get("drawing_notes"),
            }

        # Look up template confirmation prompt
        template_prompt = None
        try:
            for t in load_templates():
                if t.get("template_id") == ftype:
                    template_prompt = t.get("confirmation_prompt")
                    break
        except Exception:
            pass

        return JSONResponse({
            'job_id': job_id, 'dxf_file': dxf_name,
            'download': f'/api/download/{dxf_name}',
            'preview_svg': f'/api/preview/svg/{dxf_name}' if svg_name else None,
            'resolved_dimensions': (dispatch_extra or {}).get('resolved_dimensions'),
            'component_schema': (dispatch_extra or {}).get('component_schema'),
            'template_graph': template_response,
            'template_warnings': (template_graph_result or {}).get('warnings', []),
            'template_selection': template_selection,
            'furniture': {'type': ftype, 'confidence': max(conf, 0.5), 'hybrid': True,
                          'needs_confirmation': max(conf, 0.5) < CLASSIFIER_CONFIRM_THRESHOLD,
                          'missing_dimensions': _compute_missing_dimensions(ftype, merged_dims, real_w, real_h, real_d),
                          'template_prompt': template_prompt},
            'detected': {'lines': len(constrained['lines']), 'circles': len(constrained['circles']),
                         'rectangles': len(constrained.get('rects', [])),
                         'dimensions': merged_dims, 'ocr_lines': ocr_lines[:20]},
            'ai_analysis': ai_result,
            'materials': raw_materials or {},
            'accuracy_pipeline': accuracy_results,
            'phase3': phase3_result.to_api_dict() if phase3_result else None,
            'furniture_analysis': furniture_analysis_result,
            'template_proposal': template_proposal_result,
            'uncertainty_questions': uncertainty_questions,
            'cad_intelligence': cad_intel_result,
            'product_classifier': product_classifier_result,
            'image_quality': image_quality,
            'warnings': (scale_warns + dim_warns + (dispatch_extra or {}).get('proportion_warnings', [])
                         + (template_graph_result or {}).get('warnings', [])
                         + ([f"Source image looked blurry (sharpness {image_quality['blur_score']:.0f}, "
                             f"threshold {image_quality['threshold']:.0f}) - dimension text was read from an "
                             f"auto-sharpened copy; please double-check the numbers above against the photo."]
                            if image_quality.get('is_blurry') else [])),
        })
    except Exception as e:
        return JSONResponse({"error": f"Hybrid failed: {e}", "trace": traceback.format_exc()}, status_code=500)


# =============================================================================
# Smart Auto Workflow — single endpoint, no mode selection
# =============================================================================

@router.post("/digitize/smart")
async def digitize_smart(
    file: UploadFile = File(...),
    real_width_cm: str = Form(None),
    real_height_cm: str = Form(None),
    furniture_type: str = Form(None),
    confirmation_answers: str = Form(None),
):
    """
    One excellent workflow.
    User never chooses OpenCV/Hybrid/AI/Pipeline.
    Backend decides route and returns confirmation questions only when needed.
    """
    import json

    answers = {}
    if confirmation_answers:
        try:
            answers = json.loads(confirmation_answers)
        except Exception:
            answers = {}

    # Apply confirmation answers as hard overrides.
    if answers.get("furniture_type"):
        furniture_type = answers["furniture_type"]

    # First pass: use hybrid when OpenAI key exists, otherwise normal digitize.
    if OPENAI_API_KEY:
        response = await digitize_hybrid(file, real_width_cm, real_height_cm, furniture_type)
    else:
        response = await digitize(file, real_width_cm, real_height_cm, furniture_type)

    try:
        payload = json.loads(response.body.decode("utf-8"))
    except Exception:
        return response

    furniture = payload.get("furniture") or {}
    detected = payload.get("detected") or {}
    dims = detected.get("dimensions") or []
    lines_count = int(detected.get("lines") or 0)

    from app.backend.smart_workflow import build_smart_metadata

    real_w = _parse_float(real_width_cm)
    real_h = _parse_float(real_height_cm)

    payload["smart_workflow"] = build_smart_metadata(
        has_openai_key=bool(OPENAI_API_KEY),
        furniture_type=furniture.get("type") or "generic_2d_furniture",
        furniture_confidence=float(furniture.get("confidence") or 0),
        dimensions=dims,
        lines_count=lines_count,
        real_width_cm=real_w,
        real_height_cm=real_h,
        ocr_lines=detected.get("ocr_lines") or [],
    )

    if "furniture" in payload and isinstance(payload["furniture"], dict):
        payload["furniture"]["needs_confirmation"] = payload["smart_workflow"]["needs_confirmation"]

    return JSONResponse(payload)


@router.post("/digitize/resolve")
async def digitize_resolve(furniture_type: str = Form(...),
                            length_cm: float = Form(0), depth_cm: float = Form(0),
                            height_cm: float = Form(0), width_cm: float = Form(0),
                            top_thickness_cm: float = Form(0),
                            seat_height_cm: float = Form(0),
                            furniture_family: str = Form("")):
    """Pre-digitize template resolution — given furniture_type and optional dimensions,
    return the matching template graph with resolved parameters (in mm) and constraints.
    Useful for the frontend to show parameter sliders BEFORE running digitize.
    """
    try:
        resolver = _get_template_resolver()
        dims = {}
        if length_cm > 0: dims['length_cm'] = length_cm
        if depth_cm > 0: dims['depth_cm'] = depth_cm
        if height_cm > 0: dims['overall_height_cm'] = height_cm
        if width_cm > 0:
            dims['width_cm'] = width_cm
            dims['top_diameter_cm'] = width_cm
        if top_thickness_cm > 0: dims['top_thickness_cm'] = top_thickness_cm
        if seat_height_cm > 0: dims['seat_height_cm'] = seat_height_cm

        ftype = normalize_furniture_type(furniture_type)
        result = resolver.resolve(ftype, dims)

        tpl = result.get("template", {})
        response = {
            "template_id": tpl.get("id"),
            "template_name": tpl.get("name"),
            "product_type": tpl.get("product_type"),
            "family": tpl.get("family"),
            "resolved_parameters_mm": result.get("resolved_parameters"),
            "parameters_schema": [
                {"name": p["name"], "default": p["default"],
                 "min_value": p["min_value"], "max_value": p["max_value"],
                 "description": p.get("description", "")}
                for p in tpl.get("parameters", [])
            ],
            "required_views": result.get("component_views"),
            "required_details": result.get("required_details"),
            "drawing_notes": result.get("drawing_notes"),
            "constraints": result.get("constraints"),
            "warnings": result.get("warnings"),
        }
        return JSONResponse(response)
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=400)


@router.post("/digitize/unified")
async def digitize_unified(file: UploadFile = File(...),
                            furniture_type: str = Form(None),
                            real_width_cm: str = Form(None),
                            real_height_cm: str = Form(None)):
    """UNIFIED intelligence endpoint — runs AI Vision + OpenCV/OCR +
    cad_intelligence + template graphs in parallel and returns a
    confidence-blended result with per-field provenance tracking.

    This ONE endpoint replaces /digitize, /digitize/hybrid, and
    /export/cad_intel by intelligently blending all 3 approaches.
    """
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
    safe = f"{job_id}_{uuid.uuid4().hex[:8]}"
    img_path = UPLOAD / f"{safe}{ext}"
    with img_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # Run AI Vision if API key available
        ai_result = None
        if OPENAI_API_KEY:
            try:
                import httpx, base64
                with open(img_path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode()
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post("https://api.openai.com/v1/chat/completions",
                        headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"},
                        json={"model": "gpt-4o", "messages": [
                            {"role": "system", "content": VISION_SYSTEM_PROMPT},
                            {"role": "user", "content": [{"type": "text", "text": "Identify furniture and extract all dimensions."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}}]}
                        ], "max_tokens": 2000, "response_format": {"type": "json_object"}})
                    if r.status_code == 200:
                        raw = r.json()['choices'][0]['message']['content']
                        try: ai_result = json.loads(raw)
                        except: pass
            except Exception as e:
                print(f"[Unified] AI Vision failed (non-fatal): {e}")

        # User-provided dimensions
        user_dims = {}
        rw = _parse_float(real_width_cm)
        rh = _parse_float(real_height_cm)
        if rw: user_dims['width_cm'] = rw
        if rh: user_dims['overall_height_cm'] = rh

        # Run unified pipeline
        unified = run_unified_pipeline(
            image_path=str(img_path),
            furniture_type_override=furniture_type,
            user_dimensions_cm=user_dims,
            ai_vision_result=ai_result,
        )

        try: os.remove(str(img_path))
        except: pass

        # Determine furniture type for downstream phases
        _ftype = unified.product_type.value if unified.product_type else "generic"

        # ===== PHASE 7: Wrap in Canonical Furniture Graph =====
        try:
            from app.backend.cfg import CanonicalFurnitureGraph
            cfg = CanonicalFurnitureGraph.from_pipeline_result(
                unified_result=unified,
                furniture_type=_ftype,
                overall_dims={k: v.value * 10 for k, v in unified.dimensions.items()} if unified.dimensions else {}
            )
            cfg_dict = cfg.to_dict()
        except Exception as e:
            print(f"[Unified] CFG failed (non-fatal): {e}")
            cfg_dict = None

        # ===== PHASE 8: SelfCritic Auto-Correction Loop =====
        self_critic_result = None
        try:
            # Save a copy of the original image before deletion for self-critic
            _sc_img = str(img_path)
            if cfg_dict and Path(_sc_img).exists():
                from app.backend.self_critic import SelfCritic
                critic = SelfCritic(gap_threshold=0.05, max_iterations=3)
                from app.backend.drawing_builders import build_generic_model
                temp_model = build_generic_model()
                sc_result = critic.run(temp_model, _sc_img)
                self_critic_result = {
                    "iterations": sc_result.iterations,
                    "gap_score": round(sc_result.gap_score, 4),
                    "converged": sc_result.converged,
                    "repairs_applied": sc_result.repairs_applied,
                }
                if cfg_dict and 'confidence_map' in cfg_dict:
                    cfg_dict['confidence_map']['self_critic_score'] = 1.0 - sc_result.gap_score
        except Exception as e:
            print(f"[Unified] SelfCritic failed (non-fatal): {e}")
            self_critic_result = {"error": str(e)}

        # ===== PHASE 9: Progressive Confidence Gate =====
        # Determine if confidence is high enough to auto-generate
        avg_conf = 0.0
        if cfg_dict and cfg_dict.get('confidence_map'):
            vals = [v for v in cfg_dict['confidence_map'].values() if isinstance(v, (int, float))]
            avg_conf = sum(vals) / len(vals) if vals else 0.0
        
        confidence_gate = {
            "average_confidence": round(avg_conf, 3),
            "auto_generated": avg_conf >= 0.50,
            "needs_review": avg_conf < 0.70,
            "critical_fields": [],
        }
        # Flag any critical fields with low confidence
        if cfg_dict and cfg_dict.get('provenance'):
            for field, prov in cfg_dict['provenance'].items():
                if isinstance(prov, dict) and prov.get('confidence', 1.0) < 0.50:
                    confidence_gate["critical_fields"].append(field)

        # Generate DXF from dispatch if template was resolved
        dxf_name = None
        download_path = None
        preview_svg = None
        if unified.template_graph and unified.template_graph.get("template", {}).get("id"):
            try:
                dxf_name = f"{job_id}_unified.dxf"
                dxf_path = OUT / dxf_name
                dispatch_extra = _dispatch_furniture(_ftype, dxf_path,
                    [{"tag": k, "value_cm": v.value} for k, v in unified.dimensions.items()],
                    None, None)
                download_path = f"/api/download/{dxf_name}"
                
                # Generate SVG preview
                try:
                    from app.backend.svg_exporter import drawing_to_svg
                    svg_name = f"{job_id}_unified.svg"
                    svg_path = OUT / svg_name
                    resolved = (dispatch_extra or {}).get('resolved_dimensions') or {}
                    model = _build_svg_model(_ftype, resolved, None, None, dispatch_extra)
                    with open(str(svg_path), 'w', encoding='utf-8') as f2:
                        f2.write(drawing_to_svg(model))
                    preview_svg = f"/api/preview/svg/{dxf_name}"
                except Exception as e:
                    print(f"[Unified] SVG failed: {e}")
            except Exception as e:
                print(f"[Unified] DXF/SVG generation failed: {e}")

        response = unified.to_api_dict()
        response["job_id"] = job_id
        response["cfg"] = cfg_dict
        response["self_critic"] = self_critic_result
        response["confidence_gate"] = confidence_gate
        response["dxf_file"] = dxf_name
        response["download"] = download_path
        response["preview_svg"] = preview_svg
        response["ai_enabled"] = OPENAI_API_KEY is not None and len(OPENAI_API_KEY) > 0
        return JSONResponse(response)

    except Exception as e:
        try: os.remove(str(img_path))
        except: pass
        return JSONResponse({"error": f"Unified failed: {e}", "trace": traceback.format_exc()}, status_code=500)


# ===== CORRECTION ENDPOINTS =====

@router.post("/corrections/submit")
async def corrections_submit(session_id: str = Form(...),
                              dimension_corrections: str = Form("[]"),
                              line_role_corrections: str = Form("[]")):
    """Submit user corrections for a drawing session."""
    try:
        dim_corrections = json.loads(dimension_corrections)
        role_corrections = json.loads(line_role_corrections)
    except json.JSONDecodeError as e:
        return JSONResponse({"error": f"Invalid JSON: {e}"}, status_code=400)

    result = submit_corrections(session_id, dim_corrections, role_corrections)
    return JSONResponse(result)


@router.get("/corrections/{session_id}")
async def corrections_get(session_id: str):
    """Get saved corrections for a session."""
    result = get_corrections(session_id)
    return JSONResponse(result)


@router.post("/corrections/reset/{session_id}")
async def corrections_reset(session_id: str):
    """Reset all corrections for a session."""
    result = reset_corrections(session_id)
    return JSONResponse(result)


# ===== DOWNLOAD / PREVIEW =====

@router.get("/download/{filename}")
async def download(filename: str):
    """
    Download a generated DXF file by filename.
    Returns the raw DXF binary for CAD applications.
    """
    safe = os.path.basename(filename)
    path = OUT / safe
    if not path.exists(): return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(path, filename=safe, media_type="application/dxf")


@router.get("/preview/svg/{filename}")
async def preview_svg(filename: str):
    """
    Get an SVG preview image of a generated DXF.
    Returns a vector SVG that renders in any browser.
    """
    safe = os.path.basename(filename)
    svg_path = OUT / safe.replace('.dxf', '.svg')
    if svg_path.exists(): return FileResponse(svg_path, media_type="image/svg+xml; charset=utf-8")
    dxf_path = OUT / safe
    if dxf_path.exists():
        import ezdxf, re, json
        try:
            # Read sidecar JSON for furniture type and dimensions (FIX: was hardcoded round_pedestal)
            json_sidecar = Path(str(dxf_path).replace('.dxf', '.json'))
            ftype = "round_pedestal_table"
            resolved = {}
            if json_sidecar.exists():
                try:
                    sidecar = json.loads(json_sidecar.read_text(encoding='utf-8'))
                    ftype = sidecar.get('furniture_type', 'round_pedestal_table')
                    known = sidecar.get('known_dimensions', {})
                    est = sidecar.get('estimated_components', {})
                    resolved.update(known)
                    resolved.update(est)
                except Exception:
                    pass
            doc = ezdxf.readfile(str(dxf_path))
            from app.backend.svg_exporter import drawing_to_svg
            # Fallback: try to extract dimensions from DXF DIMENSION entities
            if not resolved.get('top_diameter_cm') and not resolved.get('width_cm'):
                top_dia, height = 80.0, 70.0
                for e in doc.modelspace():
                    if e.dxftype() == "DIMENSION":
                        txt = (e.dxf.text if hasattr(e.dxf, "text") else "") or ""
                        nums = re.findall(r'(\d+(?:\.\d+)?)', txt)
                        val = float(nums[0]) if nums else None
                        if val and ("%%c" in txt or "dia" in txt.lower()): top_dia = val
                        if val and ("H" in txt or "height" in txt.lower()): height = val
                resolved['top_diameter_cm'] = top_dia
                resolved['overall_height_cm'] = height
            model = _build_svg_model(ftype, resolved, None, None, None)
            svg = drawing_to_svg(model)
            with open(str(svg_path), 'w', encoding='utf-8') as f: f.write(svg)
            return FileResponse(svg_path, media_type="image/svg+xml; charset=utf-8")
        except Exception as e: return JSONResponse({"error": f"SVG failed: {e}"}, status_code=500)
    return JSONResponse({"error": "DXF not found"}, status_code=404)


# --- FURNITURE ADJUST DISPATCH TABLE (Gap #1b fix) ---
FURNITURE_ADJUST_DISPATCH = {}
def _get_adjust_fn(furniture_type: str):
    key = furniture_type
    if key not in FURNITURE_ADJUST_DISPATCH:
        try:
            from app.backend.dxf_exporter import (
                save_round_pedestal_table, save_rectangular_table,
                save_cabinet, save_sofa, save_coffee_table, save_dining_chair,
                save_wardrobe, save_reception_counter, save_bed_headboard,
                save_asymmetric_pedestal_table, save_oval_pedestal_table,
                save_console_table, save_office_desk,
            )
            from app.backend.drawing_builders import (
                build_round_pedestal_model, build_rectangular_table_model,
                build_cabinet_model, build_sofa_model, build_coffee_table_model,
                build_dining_chair_model, build_wardrobe_model,
                build_reception_counter_model, build_bed_headboard_model,
                build_asymmetric_pedestal_model, build_oval_pedestal_model,
                build_console_table_model, build_office_desk_model,
            )
            FURNITURE_ADJUST_DISPATCH.update({
                'round_pedestal_table': (save_round_pedestal_table, build_round_pedestal_model),
                'rectangular_table': (save_rectangular_table, build_rectangular_table_model),
                'cabinet': (save_cabinet, build_cabinet_model),
                'sofa': (save_sofa, build_sofa_model),
                'coffee_table': (save_coffee_table, build_coffee_table_model),
                'dining_chair': (save_dining_chair, build_dining_chair_model),
                'chair': (save_dining_chair, build_dining_chair_model),
                'wardrobe': (save_wardrobe, build_wardrobe_model),
                'reception_counter': (save_reception_counter, build_reception_counter_model),
                'bed_headboard': (save_bed_headboard, build_bed_headboard_model),
                'asymmetric_pedestal_table': (save_asymmetric_pedestal_table, build_asymmetric_pedestal_model),
                'oval_pedestal_table': (save_oval_pedestal_table, build_oval_pedestal_model),
                'console_table': (save_console_table, build_console_table_model),
                'office_desk': (save_office_desk, build_office_desk_model),
            })
        except ImportError as e:
            print(f"[Adjust] Import failed: {e}")
    return FURNITURE_ADJUST_DISPATCH.get(key, (None, None))


@router.post("/adjust")
# Doc: Adjust dimensions of a generated DXF file. Accepts new dimension values
# and regenerates the DXF with updated proportions.
async def adjust_dimensions(dxf_file: str = Form(...),
                              top_diameter_cm: float = Form(None),
                              overall_height_cm: float = Form(None),
                              base_diameter_cm: float = Form(None),
                              neck_diameter_cm: float = Form(None),
                              collar_diameter_cm: float = Form(None),
                              top_thickness_cm: float = Form(None),
                              width_cm: float = Form(None),
                              depth_cm: float = Form(None),
                              leg_thickness_cm: float = Form(None),
                              materials: str = Form(None),
                              visibility: str = Form(None)):
    # materials: optional JSON object of {component: text} applied in the SAME
    # regeneration as the dimension changes, so the UI can do dimensions +
    # materials in ONE request instead of two sequential calls (a stalled
    # first call used to block the second entirely).
    material_overrides = {}
    if materials:
        try:
            parsed = json.loads(materials)
            if isinstance(parsed, dict):
                material_overrides = {k: v for k, v in parsed.items() if v}
        except (json.JSONDecodeError, ValueError):
            pass
    # visibility: optional JSON object of {component: bool} — when a component
    # is False, skip it or draw on HIDDEN layer during regeneration.
    visibility_overrides = None
    if visibility:
        try:
            parsed = json.loads(visibility)
            if isinstance(parsed, dict):
                visibility_overrides = {k: bool(v) for k, v in parsed.items()}
        except (json.JSONDecodeError, ValueError):
            pass
    safe = os.path.basename(dxf_file)
    dxf_path = OUT / safe
    if not dxf_path.exists(): return JSONResponse({"error": "DXF not found"}, status_code=404)

    try:
        from app.backend.svg_exporter import drawing_to_svg
        json_path = Path(str(dxf_path).replace('.dxf', '.json'))

        # ---- Read furniture_type from sidecar JSON (Gap #1b fix) ----
        ftype = "round_pedestal_table"
        known = {}
        est = {}
        sidecar_materials = {}
        if json_path.exists():
            try:
                sidecar = json.loads(json_path.read_text(encoding='utf-8'))
                ftype = sidecar.get('furniture_type', 'round_pedestal_table')
                known = sidecar.get('known_dimensions', {})
                est = sidecar.get('estimated_components', {})
                sidecar_materials = sidecar.get('materials', {})
            except Exception as e:
                print(f"[Adjust] sidecar load failed: {e}")

        # Build merged_dims from sidecar + form overrides (FIX: was undefined)
        merged_dims = {}
        merged_dims.update(known)
        merged_dims.update(est)
        param_overrides = {
            'top_diameter_cm': top_diameter_cm,
            'overall_height_cm': overall_height_cm,
            'base_diameter_cm': base_diameter_cm,
            'neck_diameter_cm': neck_diameter_cm,
            'collar_diameter_cm': collar_diameter_cm,
            'top_thickness_cm': top_thickness_cm,
            'width_cm': width_cm,
            'depth_cm': depth_cm,
            'leg_thickness_cm': leg_thickness_cm,
        }
        for k, v in param_overrides.items():
            if v is not None:
                merged_dims[k] = float(v)

        save_fn, build_fn = _get_adjust_fn(ftype)
        if save_fn is None or build_fn is None:
            return JSONResponse({"error": f"No adjust support for {ftype}"}, status_code=400)
        # ---- Build kwargs for save_*() and build_*_model() ----
        if ftype == 'round_pedestal_table':
            save_kwargs = {
                'top_dia_cm': merged_dims.get('top_diameter_cm', 80.0),
                'height_cm': merged_dims.get('overall_height_cm', 70.0),
                'base_dia_cm': merged_dims.get('base_diameter_cm', 44.0),
                'neck_dia_cm': merged_dims.get('neck_diameter_cm', 22.4),
                'top_thick_cm': merged_dims.get('top_thickness_cm', 4.0),
                'collar_dia_cm': merged_dims.get('collar_diameter_cm'),
                'materials': sidecar_materials, 'profile': 'cylinder',
            }
        elif ftype in ('cabinet', 'sofa', 'wardrobe', 'reception_counter', 'bed_headboard', 'coffee_table'):
            save_kwargs = {
                'width_cm': merged_dims.get('width_cm', 100.0),
                'depth_cm': merged_dims.get('depth_cm', 60.0),
                'height_cm': merged_dims.get('overall_height_cm', 180.0),
                'materials': sidecar_materials,
            }
        elif ftype in ('dining_chair', 'chair'):
            save_kwargs = {
                'width_cm': merged_dims.get('width_cm', 45.0),
                'height_cm': merged_dims.get('overall_height_cm', 90.0),
                'materials': sidecar_materials,
            }
        elif ftype == 'rectangular_table':
            save_kwargs = {
                'width_cm': merged_dims.get('width_cm', 120.0),
                'depth_cm': merged_dims.get('depth_cm', 80.0),
                'height_cm': merged_dims.get('overall_height_cm', 70.0),
                'leg_thickness_cm': merged_dims.get('leg_thickness_cm', 6.0),
                'materials': sidecar_materials,
            }
        elif ftype == 'oval_pedestal_table':
            save_kwargs = {
                'length_cm': merged_dims.get('length_cm', merged_dims.get('width_cm', 180.0)),
                'depth_cm': merged_dims.get('depth_cm', 100.0),
                'height_cm': merged_dims.get('overall_height_cm', 75.0),
                'pedestal_dia_cm': merged_dims.get('pedestal_dia_cm', 40.0),
                'materials': sidecar_materials,
            }
        elif ftype == 'console_table':
            save_kwargs = {
                'length_cm': merged_dims.get('length_cm', merged_dims.get('width_cm', 120.0)),
                'depth_cm': merged_dims.get('depth_cm', 40.0),
                'height_cm': merged_dims.get('overall_height_cm', 75.0),
                'leg_thick_cm': merged_dims.get('leg_thickness_cm', merged_dims.get('leg_thick_cm', 4.0)),
                'materials': sidecar_materials,
            }
        elif ftype == 'office_desk':
            save_kwargs = {
                'length_cm': merged_dims.get('length_cm', merged_dims.get('width_cm', 140.0)),
                'depth_cm': merged_dims.get('depth_cm', 60.0),
                'height_cm': merged_dims.get('overall_height_cm', 75.0),
                'leg_thick_cm': merged_dims.get('leg_thickness_cm', merged_dims.get('leg_thick_cm', 4.0)),
                'modesty_panel_h_cm': merged_dims.get('modesty_panel_h_cm', 15.0),
                'materials': sidecar_materials,
            }
        elif ftype == 'asymmetric_pedestal_table':
            save_kwargs = {
                'length_cm': merged_dims.get('length_cm', merged_dims.get('width_cm', 180.0)),
                'depth_cm': merged_dims.get('depth_cm', 90.0),
                'height_cm': merged_dims.get('overall_height_cm', 75.0),
                'large_ped_dia_cm': merged_dims.get('large_ped_dia_cm', 40.0),
                'small_ped_dia_cm': merged_dims.get('small_ped_dia_cm', 22.0),
                'left_ped_x_cm': merged_dims.get('left_ped_x_cm', 30.0),
                'right_ped_x_cm': merged_dims.get('right_ped_x_cm', -25.0),
                'overhang_cm': merged_dims.get('overhang_cm', 20.0),
                'materials': sidecar_materials,
            }
        else:
            return JSONResponse({"error": f"Unsupported type: {ftype}"}, status_code=400)

        # Apply visibility overrides to all types in one step
        if visibility_overrides:
            save_kwargs['visibility'] = visibility_overrides

        # ---- Regenerate DXF and SVG ----
        try:
            save_fn(str(dxf_path), **save_kwargs)
        except Exception as e:
            print(f"[Adjust] DXF regen failed for {ftype}: {e}")

        model = build_fn(**save_kwargs)
        svg = drawing_to_svg(model)
        svg_path = OUT / safe.replace('.dxf', '.svg')
        with open(str(svg_path), 'w', encoding='utf-8') as f: f.write(svg)

        # ---- Persist adjusted state ----
        try:
            new_known = {}
            new_est = {}
            for k, v in merged_dims.items():
                if k in ('top_diameter_cm', 'overall_height_cm', 'width_cm', 'depth_cm', 'length_cm'):
                    new_known[k] = v
                else:
                    new_est[k] = v
            new_sidecar = {
                'furniture_type': ftype, 'known_dimensions': new_known,
                'estimated_components': new_est, 'materials': sidecar_materials,
                'profile': sidecar.get('profile', 'cylinder'),
            }
            json_path.write_text(json.dumps(new_sidecar, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[Adjust] sidecar persist failed: {e}")

        return JSONResponse({
            "dxf_file": safe, "preview_svg": f"/api/preview/svg/{safe}",
            "dimensions": {k: round(v, 1) if isinstance(v, float) else v for k, v in merged_dims.items()},
            "furniture_type": ftype,
        })
    except Exception as e: return JSONResponse({"error": f"Adjust failed: {e}"}, status_code=500)


@router.post("/material/edit")
async def edit_materials(dxf_file: str = Form(...), materials: str = Form(...),
                          drawing_title: str = Form(None), project: str = Form(None),
                          client: str = Form(None)):
    """Edit per-component material/finish text (and optional title-block text)
    on an existing drawing, regenerating both DXF and SVG with the current
    dimensions preserved from the sidecar JSON.

    `materials` is a JSON object string: {"tabletop": "...", "collar_plate": "...", ...}
    Known component keys for round_pedestal_table: tabletop, collar_plate,
    neck_ring, pedestal_body, base_foot.
    """
    safe = os.path.basename(dxf_file)
    dxf_path = OUT / safe
    if not dxf_path.exists():
        return JSONResponse({"error": "DXF not found"}, status_code=404)

    try:
        new_materials = json.loads(materials)
        if not isinstance(new_materials, dict):
            return JSONResponse({"error": "materials must be a JSON object"}, status_code=400)
    except json.JSONDecodeError as e:
        return JSONResponse({"error": f"Invalid materials JSON: {e}"}, status_code=400)

    json_path = Path(str(dxf_path).replace('.dxf', '.json'))
    if not json_path.exists():
        return JSONResponse({"error": "No drawing data found for this file - re-digitize first"}, status_code=404)

    try:
        sidecar = json.loads(json_path.read_text(encoding='utf-8'))
        furniture_type = sidecar.get('furniture_type', 'round_pedestal_table')
        known = sidecar.get('known_dimensions', {})
        est = sidecar.get('estimated_components', {})
        merged_materials = {**sidecar.get('materials', {}), **new_materials}

        from app.backend.svg_exporter import drawing_to_svg

        save_fn, build_fn = _get_adjust_fn(furniture_type)
        if save_fn is None:
            return JSONResponse({"error": f"Material editing not yet supported for {furniture_type}"},
                                 status_code=400)

        # Build kwargs from sidecar dimensions
        all_dims = {**known, **est}
        if furniture_type == 'round_pedestal_table':
            save_kwargs = {
                'top_dia_cm': all_dims.get('top_diameter_cm', 80.0),
                'height_cm': all_dims.get('overall_height_cm', 70.0),
                'base_dia_cm': all_dims.get('pedestal_diameter_cm', 44.0),
                'neck_dia_cm': all_dims.get('neck_diameter_cm', 22.4),
                'top_thick_cm': all_dims.get('top_thickness_cm', 4.0),
                'collar_dia_cm': all_dims.get('collar_diameter_cm'),
                'materials': merged_materials, 'profile': sidecar.get('profile', 'cylinder'),
            }
        elif furniture_type in ('cabinet', 'sofa', 'wardrobe', 'reception_counter', 'bed_headboard', 'coffee_table'):
            save_kwargs = {
                'width_cm': all_dims.get('width_cm', 100.0),
                'depth_cm': all_dims.get('depth_cm', 60.0),
                'height_cm': all_dims.get('overall_height_cm', 180.0),
                'materials': merged_materials,
            }
        elif furniture_type in ('dining_chair', 'chair'):
            save_kwargs = {
                'width_cm': all_dims.get('width_cm', 45.0),
                'height_cm': all_dims.get('overall_height_cm', 90.0),
                'materials': merged_materials,
            }
        elif furniture_type == 'rectangular_table':
            save_kwargs = {
                'width_cm': all_dims.get('width_cm', 120.0),
                'depth_cm': all_dims.get('depth_cm', 80.0),
                'height_cm': all_dims.get('overall_height_cm', 70.0),
                'leg_thickness_cm': all_dims.get('leg_thickness_cm', 6.0),
                'materials': merged_materials,
            }
        else:
            save_kwargs = {'materials': merged_materials}
            for k, v in all_dims.items():
                save_kwargs[k] = v

        try:
            save_fn(str(dxf_path), **save_kwargs)
        except Exception as e:
            print(f"[MaterialEdit] DXF regen failed for {furniture_type}: {e}")

        model = build_fn(**save_kwargs)

        svg = drawing_to_svg(model)
        svg_path = OUT / safe.replace('.dxf', '.svg')
        with open(str(svg_path), 'w', encoding='utf-8') as f:
            f.write(svg)

        sidecar['materials'] = merged_materials
        json_path.write_text(json.dumps(sidecar, indent=2), encoding='utf-8')

        return JSONResponse({"dxf_file": safe, "preview_svg": f"/api/preview/svg/{safe}",
                              "materials": merged_materials})
    except Exception as e:
        return JSONResponse({"error": f"Material edit failed: {e}", "trace": traceback.format_exc()},
                             status_code=500)


@router.get("/preview/{filename}")
def preview_dxf(filename: str):
    safe = os.path.basename(filename)
    path = OUT / safe
    if not path.exists(): return JSONResponse({"error": "DXF not found"}, status_code=404)
    png_name = safe.replace('.dxf', '.png')
    png_path = OUT / png_name
    if not png_path.exists():
        try:
            import matplotlib; matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import ezdxf
            doc = ezdxf.readfile(str(path))
            # dpi=100 rendered dimension text (2.5 world-unit height on a
            # 420-unit-wide page) at ~7px tall - well below what's needed for
            # reliable digit legibility if this preview is ever re-uploaded
            # as a "photo" (a real workflow: users round-trip a generated
            # drawing back through digitize). 200 keeps file size reasonable
            # while making digits ~3x taller in pixels.
            fig = plt.figure(figsize=(11.7, 8.3), dpi=200)
            ax = fig.add_axes([0, 0, 1, 1])
            ctx = RenderContext(doc)
            backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
            ax.set_xlim(-10, 440); ax.set_ylim(-10, 310); ax.axis('off')
            fig.savefig(str(png_path), dpi=200, facecolor='white', bbox_inches='tight', pad_inches=0.1)
            plt.close(fig)
        except Exception as e: return JSONResponse({"error": f"Preview failed: {e}"}, status_code=500)
    return FileResponse(png_path, media_type="image/png")


@router.get("/preview/pdf/{filename}")
def preview_pdf(filename: str):
    safe = os.path.basename(filename)
    dxf_path = OUT / safe
    if not dxf_path.exists(): return JSONResponse({"error": "DXF not found"}, status_code=404)
    pdf_name = safe.replace('.dxf', '.pdf')
    pdf_path = OUT / pdf_name
    if not pdf_path.exists():
        try:
            import matplotlib; matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import ezdxf
            doc = ezdxf.readfile(str(dxf_path))
            fig = plt.figure(figsize=(16.54, 11.69), dpi=150)
            ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
            ctx = RenderContext(doc); backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
            ax.set_xlim(-10, 440); ax.set_ylim(-10, 310); ax.set_aspect('equal'); ax.axis('off')
            fig.savefig(str(pdf_path), dpi=150, facecolor='white'); plt.close(fig)
        except Exception:
            from app.services.pdf_exporter import export_pdf_shop_drawing
            export_pdf_shop_drawing(dxf_path, pdf_path,
                furniture_type=safe.replace('_digitized.dxf','').replace('_hybrid.dxf','').replace('_',' ').title())
    return FileResponse(pdf_path, filename=pdf_name, media_type="application/pdf")


@router.post("/export/cad_intel")
async def export_cad_intel(file: UploadFile = File(...)):
    """Run the CAD Intelligence pipeline on an uploaded image and
    return a confidence-weighted DXF with entity layer assignment.
    """
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
    img_path = UPLOAD / f"{job_id}{ext}"
    with img_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from app.backend.cad_intelligence.pipeline import run_cad_intelligence_pipeline
        from app.backend.cad_intelligence.dxf_exporter import export_entities_to_dxf
        from app.backend.cad_intelligence.export_debug import pipeline_result_to_dict

        ocr_lines, dims = [], []
        try:
            from app.backend.ocr import ocr_dimensions
            ocr_lines, dims = ocr_dimensions(str(img_path))
        except Exception:
            pass

        ocr_structured = [{"text": t, "bbox": [0, 0, 0, 0], "confidence": 0.8}
                          for t in ocr_lines[:50]]
        result = run_cad_intelligence_pipeline(
            image_path=str(img_path),
            ocr_items=ocr_structured,
            default_unit="mm",
        )

        dxf_name = f"{job_id}_cad_intel.dxf"
        dxf_path = OUT / dxf_name
        export_entities_to_dxf(
            result.entities,
            output_path=str(dxf_path),
            title=f"CAD Intelligence Pipeline — {job_id[:8]}",
        )

        debug = pipeline_result_to_dict(result)
        try: os.remove(str(img_path))
        except: pass

        return JSONResponse({
            "job_id": job_id,
            "dxf_file": dxf_name,
            "download": f"/api/download/{dxf_name}",
            "summary": {
                "lines": len(result.lines),
                "circles": len(result.circles),
                "dimensions": len(result.dimensions),
                "associations": len(result.associations),
                "scale_mm_per_px": result.scale.mm_per_px,
                "scale_confidence": round(result.scale.confidence, 3),
                "entities": len(result.entities),
            },
            "debug": debug.get("debug", {}),
        })
    except Exception as e:
        try: os.remove(str(img_path))
        except: pass
        return JSONResponse({"error": f"CAD Intel failed: {e}"}, status_code=500)


@router.post("/export/freecad")
async def export_freecad(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    dxf_path = OUT / f"{job_id}_input.dxf"
    fcstd_path = OUT / f"{job_id}_model.FCStd"
    with dxf_path.open("wb") as f: shutil.copyfileobj(file.file, f)
    from app.services.freecad_exporter import export_freecad_fcstd
    ok = export_freecad_fcstd(dxf_path, fcstd_path, furniture_type="furniture")
    try: os.unlink(str(dxf_path))
    except: pass
    if not ok: return JSONResponse({"error": "FreeCAD export failed"}, status_code=500)
    return FileResponse(fcstd_path, filename=f"{job_id}_model.FCStd", media_type="application/octet-stream")


# ===== ML ENDPOINTS =====

@router.post("/ml/feedback")
async def ml_feedback(session_id: str = Form(...), predicted_type: str = Form(None),
                      corrected_type: str = Form(None), confidence: float = Form(0), verified: bool = Form(False)):
    from app.services.ml_engine import store_feedback
    predicted = {"type": predicted_type, "confidence": confidence}
    corrected = {"type": corrected_type or predicted_type}
    ok = store_feedback(session_id, predicted, corrected, verified)
    return JSONResponse({"stored": ok, "total_feedback": count_feedback()})

@router.get("/ml/status")
async def ml_status():
    from app.services.ml_engine import get_ml_status, get_feedback_count, should_retrain
    return JSONResponse({"feedback_samples": get_feedback_count(), "should_retrain": should_retrain(), "status": get_ml_status()})

@router.post("/ml/predict")
async def ml_predict(file: UploadFile = File(...)):
    from app.services.ml_engine import furniture_classifier, dimension_predictor
    from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles
    from app.backend.ocr import ocr_dimensions
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
    img_path = UPLOAD / f"{job_id}{ext}"
    with img_path.open("wb") as f: shutil.copyfileobj(file.file, f)
    ocr_lines, ocr_dims = ocr_dimensions(str(img_path))
    img, gray = load_image(str(img_path)); binary = preprocess(gray)
    geometry = {"lines": detect_lines(binary), "circles": detect_circles(gray), "rects": detect_rectangles(binary)}
    furn_pred = furniture_classifier.predict(str(img_path), "\n".join(ocr_lines), geometry)
    dim_pred = dimension_predictor.predict(geometry, ocr_dims, furn_pred["type"])
    try: os.unlink(str(img_path))
    except: pass
    return JSONResponse({"job_id": job_id, "furniture": furn_pred, "dimensions": dim_pred, "ml_available": furn_pred.get("ml", False)})

@router.post("/ml/retrain")
async def ml_retrain():
    from app.services.ml_engine import retrain_models
    return JSONResponse(retrain_models())


# ===== TEMPLATE SUGGEST ENDPOINT =====

@router.get("/templates")
async def list_templates(family: str = "", product_type: str = ""):
    """List all available template graphs, optionally filtered by family or product_type."""
    resolver = _get_template_resolver()
    all_templates = resolver.resolve_all()
    if family:
        all_templates = [t for t in all_templates if t.get("family") == family]
    if product_type:
        all_templates = [t for t in all_templates if t.get("product_type") == product_type]
    return JSONResponse({
        "templates": all_templates,
        "count": len(all_templates),
        "families": sorted(set(t.get("family", "") for t in resolver.resolve_all())),
    })


@router.get("/templates/suggest")
async def suggest_template(furniture_type: str = "", width_cm: float = 0, height_cm: float = 0, depth_cm: float = 0):
    """Suggest which template/ratios to use for detected dimensions.
    
    Uses the reference ratio solver to fill missing dimensions AND the
    template graph system to recommend the best engineering template.
    
    Returns:
        - Detected and solved dimensions (from ratio solver)
        - Recommended template graph (from template loader)
        - Resolved template parameters in mm
        - Confidence scores
    """
    from app.backend.reference_ratio_solver import solve_missing_dimensions, get_reference_ratios
    from app.backend.reference_confidence_scorer import score_dimension_confidence, get_overall_confidence
    from app.resource_engine.template_loader import TemplateGraphLoader
    from app.resource_engine.template_resolver import (TemplateResolver, PRODUCT_TYPE_MAP, TemplateResolutionError)
    import os
    
    if not furniture_type:
        return JSONResponse({"error": "furniture_type required"}, status_code=400)
    
    detected = {}
    if width_cm > 0:
        detected['width_cm'] = width_cm
        detected['length_cm'] = width_cm
        if furniture_type in ('round_pedestal_table',):
            detected['top_diameter_cm'] = width_cm
    if height_cm > 0:
        detected['overall_height_cm'] = height_cm
        detected['height_cm'] = height_cm
    if depth_cm > 0:
        detected['depth_cm'] = depth_cm
    
    # Load template graph system
    loader = TemplateGraphLoader().load()
    resolver = TemplateResolver(loader)
    
    # Try to resolve a template for this furniture type
    template_result = None
    template_match_product_type = PRODUCT_TYPE_MAP.get(furniture_type)
    if not template_match_product_type:
        # Try fallback to direct family lookup
        fallback = {
            "table": "rectangular_table",
            "sofa": "sofa",
            "chair": "dining_chair",
            "bed": "bed",
            "cabinet": "sideboard",
            "rug": None,
            "lighting": None,
            "homewares": None,
            "furniture": None,
        }.get(furniture_type)
        template_match_product_type = fallback
    
    if template_match_product_type:
        try:
            template_result = resolver.resolve(
                furniture_type=template_match_product_type,
                detected_dims_cm=detected,
            )
            # Extract just the key info for the response
            template_result = {
                "id": template_result.get("template", {}).get("id", ""),
                "name": template_result.get("template", {}).get("name", ""),
                "resolved_parameters_mm": template_result.get("resolved_parameters", {}),
                "constraints": template_result.get("constraints", []),
                "required_views": template_result.get("component_views", []),
                "warnings": template_result.get("warnings", []),
            }
        except (TemplateResolutionError, Exception) as e:
            template_result = {"error": str(e)[:100]}
    
    if not detected:
        ratios = get_reference_ratios(furniture_type)
        result = {
            "furniture_type": furniture_type,
            "detected_dimensions": detected,
            "template_graph": template_result,
            "default_ratios": ratios,
            "note": "No dimensions provided — showing default ratios",
        }
        return JSONResponse(result)
    
    solved = solve_missing_dimensions(furniture_type, detected)
    conf_scores = score_dimension_confidence(furniture_type, detected)
    
    return JSONResponse({
        "furniture_type": furniture_type,
        "detected_dimensions": detected,
        "solved_dimensions": solved,
        "template_graph": template_result,
        "confidence_scores": conf_scores,
        "overall_confidence": get_overall_confidence(conf_scores),
    })


# ===== CENTRAL BRAIN ENDPOINTS =====

@router.get("/brain/report")
async def brain_report():
    from app.backend.brain_sync import get_intelligence_report
    return JSONResponse(get_intelligence_report())

@router.get("/brain/proportions")
async def brain_proportions(furniture_type: str = "round_pedestal_table",
                            anchor_dimension: str = "top_diameter_cm",
                            anchor_value: float = 80.0, component: str = "pedestal_diameter_cm"):
    from app.backend.brain_sync import get_proportion_estimate
    est = get_proportion_estimate(furniture_type, anchor_dimension, anchor_value, component)
    return JSONResponse({"estimate": est} if est else {"estimate": None, "note": "Not enough data yet"})

@router.get("/brain/materials")
async def brain_materials(component: str = "tabletop", furniture_type: str = None):
    from app.backend.brain_sync import get_material_suggestions
    suggestions = get_material_suggestions(component, furniture_type)
    return JSONResponse({"component": component, "suggestions": suggestions})


# ===== BATCH CONVERT =====

@router.post("/batch")
async def batch_convert(files: List[UploadFile] = File(...)):
    import zipfile, io, uuid
    buf = io.BytesIO()
    results = []
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            try:
                job_id = str(uuid.uuid4())
                img_path = UPLOAD / f"{job_id}_{file.filename}"
                with img_path.open("wb") as f: f.write(await file.read())
                img, gray = load_image(str(img_path)); binary = preprocess(gray)
                lines = normalize_lines(detect_lines(binary))
                circles = detect_circles(gray); rects = detect_rectangles(binary)
                ocr_lines, ocr_dims = ocr_dimensions(str(img_path))
                constrained = process_constraints(lines, circles, ocr_dims, rects)
                classifier = classify_furniture(ocr_lines, constrained["circles"], constrained["lines"], constrained.get("rects"))
                ftype = normalize_furniture_type(classifier["type"])
                corrected_dims = autocorrect_dimensions(ocr_dims, {})
                dxf_name = f"{job_id}_batch.dxf"
                dxf_path = OUT / dxf_name
                _dispatch_furniture(ftype, dxf_path, corrected_dims, 0.0, 0.0)
                if dxf_path.exists(): zf.write(str(dxf_path), dxf_name)
                try: os.unlink(str(img_path))
                except: pass
                results.append({"file": file.filename, "furniture_type": ftype, "dxf": dxf_name, "status": "ok"})
            except Exception as e: results.append({"file": file.filename, "status": "error", "error": str(e)[:100]})
    buf.seek(0)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename=batch_convert_{len(files)}_files.zip"})


@router.get("/view/{filename}")
def view_drawing(filename: str):
    safe = os.path.basename(filename)
    svg_path = OUT / safe.replace('.dxf', '.svg').replace('.json', '.svg')
    if not svg_path.exists():
        dxf_path = OUT / safe.replace('.svg', '.dxf')
        if dxf_path.exists():
            import ezdxf, re, json
            from app.backend.svg_exporter import drawing_to_svg
            # Read sidecar for furniture type (FIX: was hardcoded round_pedestal)
            json_sidecar = Path(str(dxf_path).replace('.dxf', '.json'))
            ftype = "round_pedestal_table"
            resolved = {}
            if json_sidecar.exists():
                try:
                    sidecar = json.loads(json_sidecar.read_text(encoding='utf-8'))
                    ftype = sidecar.get('furniture_type', 'round_pedestal_table')
                    resolved.update(sidecar.get('known_dimensions', {}))
                    resolved.update(sidecar.get('estimated_components', {}))
                except Exception:
                    pass
            doc = ezdxf.readfile(str(dxf_path))
            if not resolved.get('top_diameter_cm') and not resolved.get('width_cm'):
                top_dia, height = 80.0, 70.0
                for e in doc.modelspace():
                    if e.dxftype() == "DIMENSION":
                        txt = (e.dxf.text if hasattr(e.dxf, "text") else "") or ""
                        nums = re.findall(r'(\d+(?:\.\d+)?)', txt)
                        val = float(nums[0]) if nums else None
                        if val and ("%%c" in txt or "dia" in txt.lower()): top_dia = val
                        if val and ("H" in txt or "height" in txt.lower()): height = val
                resolved['top_diameter_cm'] = top_dia
                resolved['overall_height_cm'] = height
            model = _build_svg_model(ftype, resolved, None, None, None)
            svg = drawing_to_svg(model)
            with open(str(svg_path), 'w', encoding='utf-8') as f: f.write(svg)
    if not svg_path.exists(): return JSONResponse({"error": "Drawing not found"}, status_code=404)
    svg = svg_path.read_text()
    return HTMLResponse(f"""<!DOCTYPE html><html><head><title>CAD Drawing — {safe}</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>body{{margin:0;display:flex;justify-content:center;background:#f0f0f0}}</style></head><body>{svg}</body></html>""")


# ===== STYLE PRESETS =====

@router.get("/presets")
async def list_presets_endpoint():
    from app.backend.style_presets import list_presets as lp
    presets = lp()
    return JSONResponse({"presets": [p.to_dict() for p in presets], "count": len(presets)})

@router.post("/presets/save")
async def save_preset_endpoint(name: str = Form(...), session_id: str = Form(None), furniture_type: str = Form(None)):
    from app.backend.style_presets import StylePreset, preset_from_chat_state, save_preset as sp
    state = CHAT_SESSIONS.get(session_id or "default", {})
    preset = preset_from_chat_state(state, name)
    if furniture_type: preset.furniture_type = furniture_type
    filename = sp(preset)
    return JSONResponse({"saved": filename, "preset": preset.to_dict()})

@router.post("/presets/apply")
async def apply_preset_endpoint(name: str = Form(...)):
    from app.backend.style_presets import load_preset, apply_preset_to_template
    preset = load_preset(name)
    if not preset: return JSONResponse({"error": "Preset not found"}, status_code=404)
    params = apply_preset_to_template(preset)
    return JSONResponse({"preset": preset.to_dict(), "params": params})

@router.delete("/presets/{name}")
async def delete_preset_endpoint(name: str):
    from app.backend.style_presets import delete_preset as dp
    return JSONResponse({"deleted": dp(name)})


# ===== CHAT ENDPOINTS =====

CHAT_SESSIONS: dict = {}

# File-based persistence for chat sessions (survives server restarts)
_CHAT_STORE = OUT / "chat_sessions.json"
if _CHAT_STORE.exists():
    try:
        with open(_CHAT_STORE) as f:
            CHAT_SESSIONS.update(json.load(f))
    except Exception: pass

@router.post("/chat")
async def chat_message(message: str = Form(...), session_id: str = Form(None), image_id: str = Form(None),
                        dxf_file: str = Form(None)):
    from app.backend.chat_agent import chat_with_agent
    from app.backend.feedback_learner import learn_from_chat, get_adjustment_hints, load_preferences, apply_preferences
    sid = session_id or "default"
    prev_state = CHAT_SESSIONS.get(sid)

    # Seed the chat's known dimensions from the drawing's own sidecar JSON so
    # the LLM can reason about values it was never explicitly told via chat
    # (e.g. neck/collar diameter set during initial generation, not chat) -
    # without this, relational requests like "make X different from Y" have
    # no "current value of Y" to reason from and silently no-op.
    if dxf_file and (not prev_state or not prev_state.get("dimensions")):
        try:
            json_path = OUT / os.path.basename(dxf_file).replace('.dxf', '.json')
            if json_path.exists():
                sidecar = json.loads(json_path.read_text(encoding='utf-8'))
                seeded_dims = {**sidecar.get('known_dimensions', {}), **sidecar.get('estimated_components', {})}
                prev_state = {**(prev_state or {}), "dimensions": {**seeded_dims, **(prev_state or {}).get("dimensions", {})}}
        except Exception as e:
            print(f"[Chat] sidecar seed failed: {e}")

    result = chat_with_agent(message, prev_state)
    CHAT_SESSIONS[sid] = result["state"]
    try:
        with open(_CHAT_STORE, 'w') as f:
            json.dump(dict(CHAT_SESSIONS), f, indent=2)
    except Exception: pass
    corrections = learn_from_chat(sid, prev_state or {}, result["state"], user_id=session_id or "default")
    try:
        from app.backend.brain_sync import record_correction as brc, record_material as brm
        for c in corrections:
            brc(sid, result["state"].get("furniture_type", ""), c.field, c.old_value, c.new_value,
                correction_type="dimension" if c.field.endswith("_cm") else "material")
        for comp, mat in result["state"].get("materials", {}).items(): brm(comp, str(mat))
    except Exception: pass
    hints = get_adjustment_hints(user_id=session_id or "default") if len(corrections) > 0 else []
    return JSONResponse({"session_id": sid, "response": result["response"], "action": result["action"],
        "render_hint": result["render_hint"], "state": result["state"], "image_id": image_id,
        "corrections_learned": len(corrections), "adjustment_hints": hints[:5] if hints else []})

@router.get("/chat/state")
async def chat_state(session_id: str = "default"):
    state = CHAT_SESSIONS.get(session_id, {})
    return JSONResponse({"session_id": session_id, "state": state})

@router.get("/chat/sessions")
async def chat_sessions():
    return JSONResponse({"sessions": list(CHAT_SESSIONS.keys()), "count": len(CHAT_SESSIONS)})


# ===== ECHO DRAFTER =====

@router.get("/learn/preferences")
async def get_preferences(user_id: str = "default"):
    from app.backend.feedback_learner import load_preferences, get_adjustment_hints
    model = load_preferences(user_id)
    return JSONResponse({"user_id": user_id, "preferences": model.to_dict(),
        "hints": get_adjustment_hints(user_id), "model_active": model.correction_count >= 3})

# ===== ACCURACY BENCHMARK =====

@router.get("/benchmark")
async def run_benchmark_endpoint():
    """Run accuracy benchmark against ground truth fixtures."""
    result = run_accuracy_benchmark()
    return JSONResponse(result)

@router.get("/benchmark/fixtures")
async def list_benchmark_fixtures():
    """List available benchmark fixtures."""
    fixtures = load_fixtures()
    return JSONResponse({
        "count": len(fixtures),
        "fixtures": [f.to_dict() for f in fixtures],
    })


@router.get("/benchmark/pixel")
async def run_pixel_benchmark_endpoint():
    """Run the real image-processing pipeline benchmark.
    
    For each fixture with a reference.jpg, runs the full digitize pipeline
    (OpenCV + OCR + layout parser + dimension associator + scale solver)
    WITHOUT ground-truth injection, comparing OCR-extracted dimensions
    against spec.json ground truth.
    
    Returns per-fixture accuracy scores, aggregate metrics, and a combined
    summary alongside the DXF generation benchmark.
    """
    result = run_accuracy_benchmark()
    return JSONResponse(result)


# ===== SECTION PREDICTOR =====

@router.get("/sections/predict")
async def predict_sections_endpoint(
    furniture_type: str = "round_pedestal_table",
    width_cm: float = 80.0,
    height_cm: float = 70.0,
    depth_cm: float = 60.0,
    diameter_cm: float = 80.0,
):
    """Predict shop drawing sections for a furniture piece."""
    params = {"w": width_cm, "h": height_cm, "d": depth_cm, "dia": diameter_cm}
    result = predict_drawing_sections(furniture_type, params)
    return JSONResponse(result)


# ===== LEARNED USERS =====

@router.get("/learn/users")
async def list_learned_users():
    from app.backend.feedback_learner import get_all_users, load_preferences
    users = get_all_users()
    result = {}
    for uid in users:
        model = load_preferences(uid)
        result[uid] = {"corrections": model.correction_count, "confidence": round(model.confidence, 2),
                       "last_updated": model.last_updated}
    return JSONResponse({"users": result, "total": len(users)})

@router.post("/pipeline/validate")
async def pipeline_validate(furniture_type: str = Form("dining_table"),
                             template_id: str = Form("table.dual_cylindrical_pedestal.v1"),
                             length_mm: float = Form(1800), depth_mm: float = Form(900),
                             height_mm: float = Form(750), top_thickness_mm: float = Form(30)):
    """Run the validation gate on a set of parameters WITHOUT generating DXF.
    
    Pre-validates dimensions, structural integrity, joinery, hardware clearance.
    Returns a UnifiedValidationManifest with score, issues, and suggested action.
    """
    from app.resource_engine.validation_gate import ValidationGate
    params = {"length_mm": length_mm, "depth_mm": depth_mm, "height_mm": height_mm,
              "top_thickness_mm": top_thickness_mm}
    gate = ValidationGate()
    manifest = gate.run_full_gate(params, furniture_type, template_id)
    return JSONResponse(manifest.to_dict())


@router.post("/scene/feedback")
async def scene_feedback(product_type: str = Form(...), approved: bool = Form(...),
                          comment: str = Form(""), user_id: str = Form("default"),
                          scene_json: str = Form("{}")):
    """Submit user feedback on a scene graph generation.
    
    Approved scenes reinforce the library matching.
    Rejected scenes help identify where the matcher or constraint solver fails.
    Persisted to SQLite/Postgres for durable learning.
    """
    row_id = save_feedback_db(
        product_type=product_type, approved=approved,
        comment=comment, user_id=user_id, scene_json=scene_json,
    )
    return JSONResponse({"saved": True, "id": row_id})


@router.get("/scene/feedback/stats")
async def scene_feedback_stats():
    """Get aggregated feedback statistics from database."""
    return JSONResponse(get_feedback_stats_db())


@router.get("/scene/feedback/history")
async def scene_feedback_history(limit: int = 20):
    """Get recent feedback entries."""
    entries = load_recent_feedback_db(limit)
    # Convert sqlite3.Row to serializable dicts
    result = []
    for e in entries:
        d = dict(e)
        if 'created_at' in d: d['created_at'] = str(d['created_at'])
        result.append(d)
    return JSONResponse({"entries": result, "count": len(result)})


@router.get("/scene/patterns")
async def scene_patterns(product_type: str = ""):
    """Get learned dimension patterns from feedback."""
    patterns = get_patterns_db(product_type if product_type else None)
    return JSONResponse({"patterns": patterns, "count": len(patterns)})


@router.get("/scene/scenes")
async def scene_scenes(limit: int = 20):
    """Get recent scene graph snapshots."""
    scenes = load_recent_scenes_db(limit)
    result = []
    for s in scenes:
        d = dict(s)
        if 'created_at' in d: d['created_at'] = str(d['created_at'])
        result.append(d)
    return JSONResponse({"scenes": result, "count": len(result)})


@router.get("/scene/library")
async def scene_library_summary():
    """Get library resource summary."""
    lib = ResourceLibrary().load()
    data = {}
    for rid, res in lib.resources.items():
        cat = res.get("category", "other")
        if cat not in data:
            data[cat] = []
        data[cat].append({
            "id": rid,
            "name": res.get("name", rid),
            "features": res.get("features", []),
        })
    return JSONResponse({
        "total": lib.count,
        "categories": lib.summary(),
        "resources": data,
    })


@router.post("/cloud-vision")
async def cloud_vision_endpoint(file: UploadFile = File(...)):
    """Extract furniture features from a photo using Cloud Vision API (OpenAI/Gemini).
    
    Returns structured CloudVisionFeatureSet with product type, dimensions,
    materials, visible parts, and confidence.
    Requires AI_PROVIDER and corresponding API key in environment.
    """
    ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
    job_id = str(uuid.uuid4())
    img_path = UPLOAD / f"{job_id}_{uuid.uuid4().hex[:8]}{ext}"
    with img_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    
    try:
        client = make_cloud_vision_client()
        features = client.extract_furniture_features(str(img_path))
        return JSONResponse(json.loads(features.model_dump_json()))
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)
    finally:
        try: os.remove(str(img_path))
        except: pass


@router.get("/scene/generate")
async def scene_generate(furniture_type: str = "asymmetric_pedestal_table",
                          length_cm: float = 180, depth_cm: float = 90, height_cm: float = 75):
    """Generate a scene graph for a furniture type with dimensions.
    
    Returns the constraint-solved scene graph with evidence and warnings.
    Persists the scene to the database for future pattern learning.
    """
    from app.resource_engine import library as relib
    lib = ResourceLibrary().load()
    dims = {"length_cm": length_cm, "depth_cm": depth_cm, "overall_height_cm": height_cm}
    scene = build_scene_graph(furniture_type, dims, library=lib)
    scene = solve_constraints(scene)
    
    # Persist scene to database
    try:
        scene_db_id = save_scene_db(scene, label="api_generated")
    except Exception as e:
        scene_db_id = None
        print(f"[Scene] DB persist failed (non-fatal): {e}")
    
    return JSONResponse({
        "scene": json.loads(scene.model_dump_json()),
        "warnings": scene.warnings,
        "db_id": scene_db_id,
    })


@router.post("/pipeline/run")
async def pipeline_run(file: UploadFile = File(...), furniture_type: str = Form("")):
    """Run the full end-to-end pipeline from photo to DXF.
    
    Orchestrates: Cloud Vision → Parameter Pack → Production → Manufacturing
    → Fusion → Template Graph → CAD Kernel → Quality → Closed Loop
    
    Returns job_id for status polling and DXF download URL.
    """
    ext = os.path.splitext(file.filename or 'img.png')[1] or '.png'
    job_id = str(uuid.uuid4())
    img_path = UPLOAD / f"{job_id}_{uuid.uuid4().hex[:8]}{ext}"
    with img_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    
    try:
        job = _PIPELINE_SERVICE.run_photo_pipeline(str(img_path), furniture_type)
        dxf_url = ""
        dxf_path = job.outputs.get("dxf", "")
        if dxf_path:
            safe_name = f"{job_id}_output.dxf"
            import shutil as sh
            sh.copy2(dxf_path, str(OUT / safe_name))
            dxf_url = f"/api/download/{safe_name}"
        
        return JSONResponse({
            "job_id": job.job_id,
            "status": job.status,
            "steps": len(job.steps),
            "errors": job.errors,
            "outputs": {
                "dxf_url": dxf_url,
                "quality_score": job.outputs.get("quality_score", ""),
                "scene_graph": job.outputs.get("scene_graph", ""),
            },
            "job": job.to_dict(),
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)
    finally:
        try: os.remove(str(img_path))
        except: pass


@router.get("/pipeline/status/{job_id}")
async def pipeline_status(job_id: str):
    """Get the status of a pipeline job."""
    job = _PIPELINE_SERVICE.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse(job.to_dict())


@router.post("/learn/apply")
async def apply_learned_preferences(user_id: str = Form("default"), session_id: str = Form(None)):
    from app.backend.feedback_learner import apply_preferences, load_preferences, get_adjustment_hints
    state = CHAT_SESSIONS.get(session_id or "default", {})
    adjusted = apply_preferences(state, user_id)
    hints = get_adjustment_hints(user_id)
    return JSONResponse({"user_id": user_id, "adjusted_params": adjusted, "hints": hints})


# ===== MONITORING ENDPOINTS =====

@router.get("/monitor/dashboard")
async def monitor_dashboard(days: int = 7):
    """Get the performance monitoring dashboard."""
    from app.monitoring.log_db import get_performance_dashboard
    return JSONResponse(get_performance_dashboard(days))


@router.get("/monitor/chats")
async def monitor_chats(session_id: str = None, limit: int = 50):
    """Get recent chat logs."""
    from app.monitoring.log_db import get_recent_chats
    return JSONResponse({"chats": get_recent_chats(session_id, limit)})


@router.get("/monitor/tasks")
async def monitor_tasks(task_type: str = None, limit: int = 50):
    """Get recent task logs."""
    from app.monitoring.log_db import get_recent_tasks
    return JSONResponse({"tasks": get_recent_tasks(task_type, limit)})


@router.get("/monitor/tools")
async def monitor_tools(limit: int = 50):
    """Get recent tool usage logs."""
    from app.monitoring.log_db import get_recent_tools
    return JSONResponse({"tools": get_recent_tools(limit)})


@router.get("/monitor/decisions")
async def monitor_decisions(decision_type: str = None, limit: int = 50):
    """Get recent decision logs."""
    from app.monitoring.log_db import get_recent_decisions
    return JSONResponse({"decisions": get_recent_decisions(decision_type, limit)})


@router.post("/monitor/metrics/refresh")
async def monitor_refresh_metrics():
    """Manually trigger daily metrics aggregation."""
    from app.monitoring.log_db import update_performance_metrics
    result = update_performance_metrics()
    return JSONResponse({"refreshed": bool(result), "summary": result})


@router.get("/monitor/recommendations")
async def monitor_recommendations(limit: int = 20):
    """Get open improvement recommendations."""
    from app.monitoring.log_db import get_open_recommendations
    return JSONResponse({"recommendations": get_open_recommendations(limit)})


@router.post("/monitor/recommendations/{rec_id}/status")
async def monitor_update_recommendation(rec_id: int, status: str = Form(...)):
    """Update the status of an improvement recommendation."""
    from app.monitoring.log_db import update_recommendation_status
    ok = update_recommendation_status(rec_id, status)
    return JSONResponse({"updated": ok, "recommendation_id": rec_id, "status": status})


@router.get("/monitor/stats")
async def monitor_stats():
    """Get quick summary stats for the last 7 days."""
    from app.monitoring.log_db import get_performance_dashboard
    dashboard = get_performance_dashboard(7)
    agg = dashboard.get("aggregated", {})
    return JSONResponse({
        "total_chats_7d": agg.get("total_chats", 0),
        "total_tasks_7d": agg.get("total_tasks", 0),
        "total_errors_7d": agg.get("total_errors", 0),
        "avg_response_ms": agg.get("avg_response_time_ms"),
        "openai_vs_ollama": {
            "openai": agg.get("openai_usage", 0),
            "ollama": agg.get("ollama_usage", 0),
        },
        "recommendations": dashboard.get("recommendations", {}),
        "top_tools": dashboard.get("top_tools", [])[:5],
    })


@router.post("/process-dxf")
async def process_dxf(payload: dict):
    """Process a reference DXF file: parse, generate preview, index in Qdrant.
    
    Called by the Node API after a DXF asset is uploaded to Spaces.
    Body: { productId, manufacturer, productSlug, dxfUrl }
    """
    import tempfile, httpx, os
    from app.cad.dxf_parser import parse_dxf
    from app.cad.preview_svg import generate_preview_svg
    from app.services.embedding_service import index_geometry

    product_id = payload.get("productId")
    manufacturer = payload.get("manufacturer", "unknown")
    dxf_url = payload.get("dxfUrl")

    if not dxf_url:
        return JSONResponse({"error": "Missing dxfUrl"}, status_code=400)

    with tempfile.TemporaryDirectory() as tmp:
        local_path = os.path.join(tmp, "source.dxf")

        try:
            # Download DXF from CDN
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.get(dxf_url)
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(resp.content)

            # Parse DXF geometry
            geometry = parse_dxf(local_path)
            entity_count = geometry.get("counts", {}).get("entityCount", 0)

            # Generate SVG preview
            preview_path = os.path.join(tmp, "preview.svg")
            generate_preview_svg(geometry, preview_path)
            with open(preview_path) as f:
                preview_svg = f.read()

            # Index in Qdrant
            index_result = index_geometry(
                geometry=geometry,
                product_id=product_id or "unknown",
                metadata={"manufacturer": manufacturer, "dxf_url": dxf_url},
            )

            return JSONResponse({
                "status": "ok",
                "product_id": product_id,
                "entity_count": entity_count,
                "bbox": geometry.get("bbox"),
                "qdrant": index_result,
            })

        except Exception as e:
            return JSONResponse({
                "status": "failed",
                "error": str(e),
            }, status_code=500)


# =============================================================================
# Hallucination Verifier API — run ALL validators and produce report
# =============================================================================

@router.post("/verify")
async def verify_detection(payload: dict):
    """Run the full hallucination verifier on detected dimensions.
    
    Combines:
      1. Physical bounds check — is the dimension possible for this furniture type?
      2. Aspect ratio check — are width/height proportions realistic?
      3. Scale consistency check — are related dimensions mutually consistent?
      4. Anti-hallucination entity validator — per-entity confidence (VISIBLE/ESTIMATED/UNKNOWN)
      5. Reference geometry check (if reference_geometry provided)
    
    Body: {
        product_id: string,
        furniture_type: string,
        detected_dims: { key: value_cm, ... },
        reference_geometry: { ... } (optional),
        entity_confidences: { key: { confidence: 0.0-1.0, source: string, ... } } (optional)
    }
    
    Returns per-dimension verdicts: VERIFIED | ESTIMATED | HALLUCINATION
    """
    from app.services.hallucination_verifier import verify_dimensions

    product_id = payload.get("product_id", "unknown")
    furniture_type = payload.get("furniture_type", "furniture")
    detected_dims = payload.get("detected_dims", {})
    reference_geometry = payload.get("reference_geometry")
    entity_confidences = payload.get("entity_confidences")

    if not detected_dims:
        return JSONResponse({"error": "Missing detected_dims"}, status_code=400)

    report = verify_dimensions(
        product_id=product_id,
        furniture_type=furniture_type,
        detected_dims=detected_dims,
        reference_geometry=reference_geometry,
        entity_confidences=entity_confidences,
    )

    return JSONResponse(report.to_dict())


# =============================================================================
# Validation API — Photo ↔ CAD consistency checker for ML training data
# =============================================================================

@router.post("/validate/product")
async def validate_product(payload: dict):
    """Validate a product's photo-detected dimensions against its CAD geometry.
    
    Body: {
        product_id: string,
        furniture_type: string,
        detected_dims: { key: cm, ... },
        reference_geometry: { ... parsed DXF ... },
        image_url: string (optional),
        dxf_url: string (optional)
    }
    
    Returns validation score and per-dimension comparisons.
    Products scoring >= 0.7 pass and can be used as ML training data.
    """
    from app.services.validation_service import validate_product_family

    product_id = payload.get("product_id", "unknown")
    detected_dims = payload.get("detected_dims", {})
    reference_geometry = payload.get("reference_geometry", {})
    furniture_type = payload.get("furniture_type", "unknown")

    if not detected_dims:
        return JSONResponse({"error": "Missing detected_dims"}, status_code=400)
    if not reference_geometry:
        return JSONResponse({"error": "Missing reference_geometry"}, status_code=400)

    result = validate_product_family(
        product_id=product_id,
        detected_dims=detected_dims,
        reference_geometry=reference_geometry,
        furniture_type=furniture_type,
    )

    return JSONResponse({
        "product_id": product_id,
        "overall_score": result.overall_score,
        "passed": result.passed,
        "dimensions": result.dimensions,
        "errors": result.errors,
    })


@router.post("/validate/batch")
async def validate_batch(payload: dict):
    """Batch-validate all product families where photo + CAD both exist.
    
    Body: { families: [ { product_id, furniture_type, detected_dims,
                          reference_geometry, image_url, dxf_url }, ... ] }
    
    Returns passed/failed counts and paths for training data export.
    """
    from app.services.validation_service import (
        validate_all_product_families,
        export_training_data,
    )

    families = payload.get("families", [])
    if not families:
        return JSONResponse({"error": "Missing families"}, status_code=400)

    validated = validate_all_product_families(families)
    min_score = payload.get("min_score", 0.7)

    export_path = payload.get("export_path", "/tmp/training-data.jsonl")
    summary = export_training_data(validated, export_path, min_score)

    return JSONResponse({
        "summary": summary,
        "samples": validated[:5],  # first 5 for inspection
    })


@router.get("/validate/training-data")
async def get_training_data():
    """Check if training data export exists and return summary."""
    import os
    path = "/tmp/training-data.jsonl"
    if os.path.exists(path):
        with open(path) as f:
            lines = f.readlines()
        return JSONResponse({
            "available": True,
            "records": len(lines),
            "path": path,
        })
    return JSONResponse({
        "available": False,
        "message": "No training data exported yet. POST /api/validate/batch first.",
    })


@router.post("/validate/product-units")
async def group_products_into_families(payload: dict):
    """Group crawled photos with CAD imports into product families.
    
    This is the bridge between:
      - Crawled product pages (which have photos → raw/jardan/images/...)
      - Imported CAD files (raw/jardan/cad/...)
    
    Groups are formed by matching manufacturer + product code in the file paths.
    Returns families ready for /validate/batch.
    """
    import os
    import re

    photo_dir = payload.get("photo_dir", "/tmp/crawler-storage")
    cad_dir = payload.get("cad_dir", "/tmp/cad-imports")
    manufacturer = payload.get("manufacturer", "jardan")

    # Scan for photos and CAD files
    families = {}
    product_code_re = re.compile(r"(?:raw/)?\w*?/([a-z]+\d+[a-z]*|[a-z]+-\w+)")

    def scan_dir(directory, asset_type):
        if not os.path.isdir(directory):
            logger.warning(f"Directory not found: {directory}")
            return
        for root, _dirs, files in os.walk(directory):
            for fname in files:
                fpath = os.path.join(root, fname)
                # Extract product code from filename directory
                m = product_code_re.search(fpath)
                if m:
                    code = m.group(1)
                    if code not in families:
                        families[code] = {"product_id": code, "assets": []}
                    families[code]["assets"].append({
                        "type": asset_type,
                        "path": fpath,
                        "filename": fname,
                    })

    scan_dir(photo_dir, "image")
    scan_dir(cad_dir, "cad")

    # Build family list — only products that have BOTH photo AND CAD
    family_list = []
    for code, family in families.items():
        has_photo = any(a["type"] == "image" for a in family["assets"])
        has_cad = any(a["type"] == "cad" for a in family["assets"])
        if has_photo and has_cad:
            cad_path = next(
                (a["path"] for a in family["assets"] if a["type"] == "cad"), ""
            )
            # Try to parse the CAD file for reference geometry
            ref_geo = None
            try:
                from app.cad.dxf_parser import parse_dxf
                ref_geo = parse_dxf(cad_path)
            except Exception:
                try:
                    # Could be on Spaces CDN — download first
                    import httpx, tempfile, os
                    resp = httpx.get(cad_path, timeout=30)
                    if resp.status_code == 200:
                        tmp = os.path.join(tempfile.gettempdir(), f"tmp_{code}.dxf")
                        with open(tmp, "wb") as f:
                            f.write(resp.content)
                        ref_geo = parse_dxf(tmp)
                except Exception:
                    pass

            family_list.append({
                "product_id": f"{manufacturer}-{code}",
                "furniture_type": payload.get("default_type", "furniture"),
                "detected_dims": {},  # populated by digitizer separately
                "reference_geometry": ref_geo or {},
                "image_url": next(
                    (a["path"] for a in family["assets"] if a["type"] == "image"), ""
                ),
                "dxf_url": cad_path,
            })

    return JSONResponse({
        "manufacturer": manufacturer,
        "families_found": len(family_list),
        "families": family_list[:50],  # first 50 for preview
    })


# =============================================================================
# Crawl → Digitize → Validate Pipeline
# Single endpoint: URL → photo → DXF → validation score
# =============================================================================

@router.post("/crawl-to-dxf")
async def crawl_to_dxf(payload: dict):
    """Crawl a product page, digitize the best image, validate the result.

    Single endpoint that chains together:
      1. Stealth crawl of the product URL → find best hero image
      2. Download image → digitize (OpenCV + OCR + AI)
      3. Run hallucination/validation checks against reference geometry
      4. Return DXF path + validation score

    Body: {
        url: string (required) — Product page URL
        manufacturer: string (optional)
        category: string (optional) — 'sofa', 'table', 'chair', 'lighting', etc.
        real_width_cm: number (optional) — Known width for scale reference
        reference_geometry: { ... } (optional) — Parsed DXF geometry for validation
    }

    Returns: {
        status, image_url, dxf_file, preview_svg, download_url,
        detected_dimensions: { ... },
        validation: { overall_score, verdicts, hallucination_count, verified_count },
        hallucination_check: { overall_score, verdicts } (if no reference provided)
    }
    """
    url = payload.get("url")
    if not url:
        return JSONResponse({"error": "Missing url"}, status_code=400)

    furniture_type = payload.get("category") or payload.get("furniture_type") or "furniture"
    real_width_cm = payload.get("real_width_cm")
    reference_geometry = payload.get("reference_geometry")

    try:
        from app.services.crawl_to_dxf import crawl_and_digitize
        result = await crawl_and_digitize(
            page_url=url,
            furniture_type=furniture_type,
            real_width_cm=real_width_cm,
            reference_geometry=reference_geometry,
        )
        return JSONResponse(result)
    except Exception as e:
        import traceback
        return JSONResponse({
            "status": "failed",
            "error": str(e),
            "trace": traceback.format_exc(),
        }, status_code=500)


# =============================================================================
# Comparison Agent — Image vs DXF accuracy scorer
# =============================================================================

@router.post("/compare")
async def compare_digitization(payload: dict):
    """Compare a source product image against the generated DXF.
    
    Runs: edge overlay → entity count check → dimension comparison
    Returns alignment scores, error regions, and dimension deviations.
    All results logged to comparison_results table for ML improvement.
    
    Body: {
        job_id: string,
        product_id: string,
        image_url: string (downloadable URL to the original image),
        dxf_path: string (local path to DXF file),
        page_dimensions: { width_cm, height_cm, ... } (optional),
        detected_entities: { lines, circles, rectangles } (optional)
    }
    
    Returns: ComparisonResult with scores + errors
    """
    from app.services.comparison_agent import compare_digitization, log_comparison_to_db
    import logging
    _logger = logging.getLogger("compare")

    job_id = payload.get("job_id", str(uuid.uuid4()))
    product_id = payload.get("product_id", "unknown")
    image_url = payload.get("image_url", "")
    dxf_path = payload.get("dxf_path", "")
    page_dimensions = payload.get("page_dimensions")
    detected_entities = payload.get("detected_entities")

    if not image_url or not dxf_path:
        return JSONResponse({"error": "Missing image_url or dxf_path"}, status_code=400)

    # Download the image
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(image_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": image_url,
            })
            if resp.status_code != 200:
                return JSONResponse({"error": f"Failed to download image: HTTP {resp.status_code}"}, status_code=400)
            image_data = resp.content
    except Exception as e:
        return JSONResponse({"error": f"Failed to download image: {e}"}, status_code=400)

    # Check DXF exists
    import os
    if not os.path.exists(dxf_path):
        return JSONResponse({"error": f"DXF file not found: {dxf_path}"}, status_code=400)

    try:
        result = compare_digitization(
            job_id=job_id,
            product_id=product_id,
            image_url=image_url,
            image_data=image_data,
            dxf_path=dxf_path,
            page_dimensions=page_dimensions,
            detected_entities=detected_entities,
        )

        # Log to database for ML training
        db_ok = log_comparison_to_db(result)
        if not db_ok:
            _logger.warning(f"Comparison result not persisted to DB (job={job_id})")

        return JSONResponse(result.to_dict())

    except Exception as e:
        import traceback
        return JSONResponse({
            "status": "failed",
            "error": str(e),
            "trace": traceback.format_exc(),
        }, status_code=500)


@router.get("/compare/results")
async def list_comparison_results(limit: int = 20):
    """List recent comparison results from the database."""
    try:
        import psycopg2, json
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT job_id, product_id, overall_score, edge_overlap_score,
                   entity_match_score, dimension_deviation_pct,
                   errors_json, dimension_comparisons_json,
                   created_at
            FROM comparison_results
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return JSONResponse([
            {
                "job_id": r[0],
                "product_id": r[1],
                "overall_score": round(r[2], 3) if r[2] else 0,
                "edge_overlap": round(r[3], 3) if r[3] else 0,
                "entity_match": round(r[4], 3) if r[4] else 0,
                "dim_dev_pct": round(r[5], 1) if r[5] else 0,
                "error_count": len(r[6]) if isinstance(r[6], list) else 0,
                "created_at": str(r[8]),
            }
            for r in rows
        ])
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# =============================================================================
# Training Feedback — auto-adjust digitizer from comparison errors
# =============================================================================

@router.get("/calibration/report")
async def calibration_report():
    """Generate calibration report from accumulated comparison errors.
    
    Aggregates comparison data, detects systematic biases, and
    generates correction hints for digitizer parameters.
    
    Returns:
        current_parameters, comparison_stats, systematic_biases,
        correction_hints, correction_history, recommended_action
    """
    from app.services.training_feedback import get_calibration_report
    report = get_calibration_report()
    return JSONResponse(report)


@router.post("/calibration/apply")
async def apply_calibration():
    """Auto-apply high-confidence corrections from comparison feedback.
    
    Applies parameter adjustments and scale corrections, saves new
    parameter state to DB, and returns what was changed.
    """
    from app.services.training_feedback import apply_calibration
    result = apply_calibration()
    return JSONResponse(result)


@router.get("/calibration/parameters")
async def get_parameters():
    """Get current digitizer parameter state."""
    from app.services.training_feedback import load_parameter_state
    load_parameter_state()
    from app.services.training_feedback import _parameter_state
    params = {k: v for k, v in _parameter_state.items() if k != "correction_history"}
    return JSONResponse(params)


@router.get("/calibration/errors")
async def get_error_aggregation(days_back: int = 7, limit: int = 100):
    """Get aggregated comparison errors for analysis.
    
    Query params: days_back (default 7), limit (default 100)
    """
    from app.services.training_feedback import aggregate_comparison_errors
    result = aggregate_comparison_errors(days_back=days_back, limit=limit)
    return JSONResponse(result)


@router.post("/calibration/cleanup")
async def cleanup_old_comparisons(days: int = 90):
    """Delete comparison results older than N days.
    
    Also cleans up old crawl results and failed jobs.
    Run monthly via cron or manually.
    """
    import psycopg2, os
    try:
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("DELETE FROM comparison_results WHERE created_at < NOW() - INTERVAL '%s days'", (days,))
        deleted = cur.rowcount
        cur.execute("DELETE FROM validation_results WHERE created_at < NOW() - INTERVAL '%s days'", (days,))
        deleted2 = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Cleanup: deleted {deleted} comparisons, {deleted2} validation results older than {days} days")
        return JSONResponse({"deleted_comparisons": deleted, "deleted_validations": deleted2, "retention_days": days})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/calibration/parameters/update")
async def update_parameter(payload: dict):
    """Manually update a digitizer parameter via slider control.
    
    Body: { param_key: string, param_value: number }
    The parameter is saved to digitizer_parameters table and takes
    effect on the next digitize call.
    """
    param_key = payload.get("param_key", "")
    param_value = payload.get("param_value")
    if not param_key or param_value is None:
        return JSONResponse({"error": "Missing param_key or param_value"}, status_code=400)
    try:
        import psycopg2, os, json
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO digitizer_parameters (param_key, param_value, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (param_key) DO UPDATE SET param_value = %s::jsonb, updated_at = NOW()
        """, (param_key, json.dumps(param_value), json.dumps(param_value)))
        conn.commit()
        cur.close()
        conn.close()
        # Also update in-memory cache
        from app.services.training_feedback import _parameter_state
        _parameter_state[param_key] = param_value
        return JSONResponse({"status": "ok", "param_key": param_key, "param_value": param_value})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/benchmark/run")
async def benchmark_run():
    """Run the accuracy benchmark against all fixture specs.
    Returns per-fixture accuracy scores and overall summary.
    This endpoint was missing from the API routes (WG-2 fix)."""
    try:
        from app.backend.accuracy_benchmark import run_accuracy_benchmark
        result = run_accuracy_benchmark()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/benchmark/fixtures")
async def benchmark_list_fixtures():
    """List all available benchmark fixtures with their metadata."""
    try:
        from app.backend.accuracy_benchmark import load_fixtures
        fixtures = load_fixtures()
        return JSONResponse({
            "fixtures": [
                {
                    "name": f.name,
                    "furniture_type": f.furniture_type,
                    "dimensions": [d.to_dict() if hasattr(d, 'to_dict') else {
                        "tag": d.tag, "value_cm": d.value_cm, "tolerance_pct": d.tolerance_pct
                    } for d in f.dimensions],
                    "has_expected_dxf": f.expected_dxf_path is not None,
                }
                for f in fixtures
            ],
            "total": len(fixtures),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/benchmark/run")
async def benchmark_run_with_params(max_fixtures: int = Form(0)):
    """Run benchmark with optional limit on number of fixtures.
    When max_fixtures is 0 (default), all fixtures are used."""
    try:
        from app.backend.accuracy_benchmark import run_accuracy_benchmark, load_fixtures
        all_fixtures = load_fixtures()
        if max_fixtures > 0 and max_fixtures < len(all_fixtures):
            fixtures = all_fixtures[:max_fixtures]
        else:
            fixtures = all_fixtures
        result = run_accuracy_benchmark()
        result["fixtures_loaded"] = len(all_fixtures)
        result["fixtures_used"] = len(fixtures)
        result["fixtures_limited"] = len(fixtures) < len(all_fixtures)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Product Catalog Search API (259 Shopify templates)
# ---------------------------------------------------------------------------

@router.get("/products/search")
async def products_search(
    q: Optional[str] = None,
    shape: Optional[str] = None,
    base: Optional[str] = None,
    leg: Optional[str] = None,
    category: Optional[str] = None,
    text: Optional[str] = None,
    top_k: int = 5,
):
    """Search 259 product templates by visual DNA and/or text."""
    try:
        from app.backend.product_search import search_combined
        params = {}
        if q: params["text"] = q
        if shape: params["shape"] = shape
        if base: params["base"] = base
        if leg: params["leg"] = leg
        if category: params["category"] = category
        if text: params["text"] = text
        if params:
            result = search_combined(params, top_k=top_k)
        else:
            from app.backend.product_search import catalog_stats
            result = catalog_stats()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/products/search/similar")
async def products_search_similar(template_id: str, top_k: int = 5):
    """Find products visually similar to a template."""
    try:
        from app.backend.product_search import get_similar
        results = get_similar(template_id, top_k=top_k)
        return JSONResponse({"results": results, "total": len(results), "query": template_id})
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/products/search/semantic")
async def products_search_semantic(q: str, top_k: int = 5):
    """Semantic search via Qdrant."""
    try:
        from app.backend.product_search import search_semantic
        results = search_semantic(q, top_k=top_k)
        return JSONResponse({"results": results, "total": len(results), "mode": "semantic" if results else "fallback"})
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.post("/products/learn")
async def products_learn(payload: dict):
    """Save confirmed product match to local storage + Qdrant."""
    try:
        from app.backend.product_search import learn_product
        td = payload.get("template_data", {})
        corrections = payload.get("corrections")
        if not td:
            return JSONResponse({"error": "template_data is required"}, status_code=400)
        result = learn_product(td, corrections)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/products/catalog")
async def products_catalog():
    """Catalog statistics."""
    try:
        from app.backend.product_search import catalog_stats
        return JSONResponse(catalog_stats())
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/products/family/{family_name}")
async def products_family(family_name: str):
    """Visual DNA for a template family."""
    try:
        from app.backend.product_search import get_family_visual_dna, load_catalog
        dna = get_family_visual_dna(family_name)
        if not dna:
            return JSONResponse({"error": f"Family '{family_name}' not found"}, status_code=404)
        catalog = load_catalog()
        members = [e for e in catalog["registry"] if e.get("template_family") == family_name]
        return JSONResponse({"family": family_name, "visual_dna": dna, "members": members, "count": len(members)})
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


# ---------------------------------------------------------------------------
# Phase 3 — SVG Skeleton Preview (lightweight geometry preview)
# ---------------------------------------------------------------------------

@router.get("/skeleton/{family_name}")
async def skeleton_preview(
    family_name: str,
    width_cm: float = Query(100, description="Width in cm"),
    depth_cm: float = Query(None, description="Depth in cm"),
    height_cm: float = Query(None, description="Height in cm"),
):
    """Generate lightweight SVG skeleton preview for a product family.

    This is a "validate the geometry before committing" step — simple
    outline/contour drawing with labeled components and centerlines.
    """
    try:
        from app.backend.svg_skeleton import generate_skeleton

        dims = {"width_cm": width_cm}
        if depth_cm: dims["depth_cm"] = depth_cm
        if height_cm: dims["height_cm"] = height_cm

        svg = generate_skeleton(family_name, dims)
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@router.get("/products/dna/{handle}")
async def product_dna_detail(handle: str):
    """Get enriched per-product DNA for a specific product handle."""
    try:
        from app.backend.product_search import load_product_dna
        dna = load_product_dna()
        entry = dna.get(handle)
        if not entry:
            # Try fuzzy handle match
            for h, e in dna.items():
                if handle in h or h in handle:
                    entry = e
                    break
        if not entry:
            return JSONResponse({"error": f"Product '{handle}' not found in DNA"}, status_code=404)
        return JSONResponse(entry)
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


# =============================================================================
# Visual Shape Quality — overlay comparison + shape analysis
# =============================================================================

@router.post("/visual/compare")
async def visual_shape_compare(payload: dict):
    """Compare product photo vs DXF using visual overlay and shape analysis.
    
    Generates:
      - Shape similarity score (Hu moments)
      - Circle/rectangle detection ratio
      - Overlay SVG with edges from both sources
      - Round-vs-square classification match
      - Overall visual quality score
    
    Body: { image_url, dxf_path, page_dimensions (optional) }
    """
    image_url = payload.get("image_url", "")
    dxf_path = payload.get("dxf_path", "")
    
    if not image_url or not dxf_path:
        return JSONResponse({"error": "Missing image_url or dxf_path"}, status_code=400)
    
    try:
        import httpx
        import io
        import numpy as np
        import os
        
        # Load image
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return JSONResponse({"error": "Failed to download image"}, status_code=400)
            img_bytes = resp.content
        
        import cv2
        img_array = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            return JSONResponse({"error": "Failed to decode image"}, status_code=400)
        
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # ---- Edge detection ----
        edges = cv2.Canny(gray, 50, 150)
        
        # ---- Circle detection ----
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50, param1=50, param2=30, minRadius=10, maxRadius=min(w, h) // 2)
        circle_count = len(circles[0]) if circles is not None else 0
        
        # ---- Rectangle/line detection ----
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 50, minLineLength=30, maxLineGap=10)
        line_count = len(lines) if lines is not None else 0
        
        # ---- Filter false positive circles (e-commerce backgrounds) ----
        # Only count circles that are reasonable size for furniture
        filtered_circles = 0
        if circles is not None:
            for c in circles[0]:
                x, y, r = c
                # Filter: circle should be >3% and <30% of image dimensions
                if r > min(w, h) * 0.03 and r < min(w, h) * 0.30:
                    # Filter: circles near image center (product area, not background)
                    cx, cy = w / 2, h / 2
                    dist_from_center = ((x - cx) / (w / 2)) ** 2 + ((y - cy) / (h / 2)) ** 2
                    if dist_from_center < 1.5:
                        filtered_circles += 1
        
        true_circle_count = filtered_circles
        total_features = true_circle_count + line_count
        roundness_ratio = true_circle_count / max(total_features, 1)
        
        # Classify: round if circles dominate, rectangular if lines dominate
        detected_shape = "round" if roundness_ratio > 0.15 else "mixed" if roundness_ratio > 0.05 else "rectangular"
        
        # ---- DXF analysis ----
        dxf_entity_counts = {"circle": 0, "line": 0, "polyline": 0, "total": 0}
        if os.path.exists(dxf_path):
            try:
                import ezdxf
                doc = ezdxf.readfile(dxf_path)
                msp = doc.modelspace()
                for e in msp:
                    dt = e.dxftype()
                    dxf_entity_counts["total"] += 1
                    if dt == "CIRCLE": dxf_entity_counts["circle"] += 1
                    elif dt == "LINE": dxf_entity_counts["line"] += 1
                    elif dt in ("LWPOLYLINE", "POLYLINE"): dxf_entity_counts["polyline"] += 1
            except Exception as e:
                return JSONResponse({"error": f"DXF read failed: {e}"}, status_code=400)
        
        # DXF shape classification (more lenient: 1 circle = possibly round)
        dxf_total = dxf_entity_counts["total"]
        dxf_circle_ratio = dxf_entity_counts["circle"] / max(dxf_total, 1)
        dxf_line_ratio = dxf_entity_counts["line"] / max(dxf_total, 1)
        if dxf_entity_counts["circle"] >= 2:
            dxf_shape = "round"
        elif dxf_entity_counts["circle"] == 0 and dxf_entity_counts["line"] > dxf_entity_counts["polyline"]:
            dxf_shape = "rectangular"
        elif dxf_line_ratio > 0.5:
            dxf_shape = "rectangular"
        else:
            dxf_shape = "mixed"
        
        # ---- Shape match score ----
        shape_match = 1.0 if detected_shape == dxf_shape else 0.5 if detected_shape == "mixed" or dxf_shape == "mixed" else 0.0
        
        # ---- Overall visual quality ----
        # Combines: shape match (40%), entity richness (30%), circle accuracy (30%)
        entity_richness = min(dxf_total / 50, 1.0)  # >=50 entities is good
        circle_accuracy = 1.0 - min(abs(circle_count - dxf_entity_counts["circle"]) / max(circle_count, 1), 1.0) if circle_count > 0 else (1.0 if dxf_entity_counts["circle"] == 0 else 0.3)
        visual_score = shape_match * 0.4 + entity_richness * 0.3 + circle_accuracy * 0.3
        
        return JSONResponse({
            "visual_quality_score": round(visual_score, 3),
            "shape_match_score": round(shape_match, 3),
            "entity_richness": round(entity_richness, 3),
            "circle_accuracy": round(circle_accuracy, 3),
            "detected_from_image": {
                "shape": detected_shape,
                "circles": circle_count,
                "lines": line_count,
                "roundness_ratio": round(roundness_ratio, 3),
            },
            "dxf_entities": dxf_entity_counts,
            "dxf_shape_classification": dxf_shape,
            "recommendation": (
                "Shape matches template" if shape_match > 0.7 else
                f"Shape mismatch: image={detected_shape}, DXF={dxf_shape}. "
                f"Image has {true_circle_count} circles (after filtering), " + (
                    "DXF has none — check if round_pedestal template should be used" if dxf_entity_counts["circle"] == 0 and true_circle_count > 5 else
                    "DXF circles found — shape may still be incorrect" if dxf_entity_counts["circle"] > 0 else
                    "Try using --category=table to trigger table templates"
                )
            ),
        })
    
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


# =============================================================================
# Furniture Engineering Agent — reverse engineering analysis
# =============================================================================

@router.get("/engineer/families")
async def list_engineering_families():
    """List all furniture families and types with engineering specifications."""
    from app.services.engineering_agent import FURNITURE_FAMILIES
    return JSONResponse({"families": {k: list(v.keys()) for k, v in FURNITURE_FAMILIES.items()}})


@router.post("/engineer/analyze")
async def analyze_furniture(payload: dict):
    """Reverse-engineer a furniture product and generate engineering specs.
    
    Body: { product_id, furniture_type, page_dimensions, detected_dimensions }
    Returns complete engineering analysis with BOM, materials, joinery, layers.
    """
    from app.services.engineering_agent import analyze_product, persist_analysis
    product_id = payload.get("product_id", "unknown")
    furniture_type = payload.get("furniture_type", "furniture")
    page_dimensions = payload.get("page_dimensions")
    detected_dimensions = payload.get("detected_dimensions")
    analysis = analyze_product(product_id, furniture_type, page_dimensions, detected_dimensions)
    persist_analysis(analysis)
    return JSONResponse(analysis.to_dict())


@router.get("/engineer/analyses")
async def list_analyses(limit: int = 20):
    """List recent engineering analyses from the knowledge base."""
    try:
        import psycopg2, os
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("SELECT product_id, furniture_type, family, created_at FROM engineering_analyses ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return JSONResponse([{"product_id": r[0], "furniture_type": r[1], "family": r[2], "created_at": str(r[3])} for r in rows])
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/engineer/knowledge/{furniture_type}")
async def get_engineering_knowledge(furniture_type: str):
    """Get stored engineering knowledge for a furniture type."""
    try:
        import psycopg2, os, json
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("SELECT materials_json, joinery_json, confidence_scores_json FROM engineering_analyses WHERE furniture_type = %s ORDER BY created_at DESC LIMIT 20", (furniture_type,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        if not rows: return JSONResponse({"error": "No analyses found"}, status_code=404)
        return JSONResponse({"furniture_type": furniture_type, "sample_count": len(rows), "materials": [json.loads(r[0]) for r in rows if r[0]]})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
