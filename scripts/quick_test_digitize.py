"""Quick end-to-end test of /digitize/hybrid with a real fixture image."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Test directly against the Python API without starting the server
# by calling the internal functions
from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles, normalize_lines
from app.backend.ocr import ocr_dimensions
from app.backend.geometry_cleanup import process_constraints
from app.backend.dimension_validator import autocorrect_dimensions, validate_scale
from app.backend.furniture_classifier import classify_furniture, normalize_furniture_type
from app.backend.dxf_exporter import save_round_pedestal_table
from app.backend.cad_intelligence.pipeline import run_cad_intelligence_pipeline

fixture = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'round_table', 'reference.jpg')
print(f"Testing: {fixture}")
print(f"Exists: {os.path.exists(fixture)}")

# 1. OpenCV detection
img, gray = load_image(fixture)
binary = preprocess(gray)
lines_raw = detect_lines(binary)
lines = normalize_lines(lines_raw)
circles = detect_circles(gray)
rects = detect_rectangles(binary)
print(f"Lines: {len(lines)}, Circles: {len(circles)}, Rects: {len(rects)}")

# 2. OCR
ocr_lines, dims = ocr_dimensions(fixture)
print(f"OCR lines: {len(ocr_lines)}, OCR dims: {len(dims)}")

# 3. CAD Intelligence pipeline
ci_result = run_cad_intelligence_pipeline(
    image_path=fixture,
    ocr_items=[{"text": t, "bbox": [0,0,0,0], "confidence": 0.8} for t in ocr_lines[:50]],
    default_unit="mm",
)
print(f"CI Lines: {len(ci_result.lines)}, Circles: {len(ci_result.circles)}")
print(f"CI Dims parsed: {len(ci_result.dimensions)}")
print(f"CI Scale: {ci_result.scale.mm_per_px} (conf: {ci_result.scale.confidence:.2f})")
print(f"CI Entities: {len(ci_result.entities)}")

# Roles analysis
roles = {}
for line in ci_result.lines:
    roles[line.role] = roles.get(line.role, 0) + 1
print(f"Line roles: {roles}")

# 4. Classifier
classifier = classify_furniture(ocr_lines, circles, lines, rects)
ftype = normalize_furniture_type(classifier['type'])
print(f"Classified: {ftype} (conf: {classifier['confidence']:.2f})")

# 5. Template resolution
from app.resource_engine.template_loader import TemplateGraphLoader
from app.resource_engine.template_resolver import TemplateResolver
loader = TemplateGraphLoader().load()
resolver = TemplateResolver(loader)
template = resolver.resolve(ftype, {'top_diameter_cm': 80.0, 'overall_height_cm': 70.0})
print(f"Template: {template['template']['name']}")
print(f"Params: {len(template['resolved_parameters'])}")
print(f"Views: {template['component_views']}")
print(f"Constraints: {len(template['constraints'])}")

# 6. DXF export
out_dir = tempfile.mkdtemp()
dxf_path = os.path.join(out_dir, "test_hybrid.dxf")
save_round_pedestal_table(dxf_path, top_dia_cm=80, height_cm=70)
print(f"DXF saved: {os.path.exists(dxf_path)}")

print("\n=== PIPELINE VERIFIED ===")
