"""Test cad_intelligence pipeline against a real fixture image."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from app.backend.cad_intelligence.pipeline import run_cad_intelligence_pipeline
from app.backend.cad_intelligence.component_graph import ComponentGraph

# Find a fixture
fixtures_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'fixtures')
test_fixtures = [
    ('round_table', 'reference.jpg'),
    ('rectangular_table', 'reference.jpg'),
    ('sofa', 'reference.jpg'),
    ('cabinet', 'reference.jpg'),
]

for fname, fimg in test_fixtures:
    fpath = os.path.join(fixtures_dir, fname, fimg)
    if os.path.exists(fpath):
        print(f"=== Testing: {fname} ({fpath}) ===")
        result = run_cad_intelligence_pipeline(fpath, [], 'mm')
        
        print(f"  Lines detected: {len(result.lines)}")
        print(f"  Circles detected: {len(result.circles)}")
        print(f"  OCR dimensions parsed: {len(result.dimensions)}")
        print(f"  Dimension associations: {len(result.associations)}")
        print(f"  Scale mm_per_px: {result.scale.mm_per_px} (conf: {result.scale.confidence:.2f})")
        print(f"  Entities reconstructed: {len(result.entities)}")
        
        roles = {}
        for line in result.lines:
            roles[line.role] = roles.get(line.role, 0) + 1
        print(f"  Line roles: {roles}")
        
        # Show first few associations
        for i, assoc in enumerate(result.associations[:3]):
            print(f"  Assoc {i}: '{assoc.dimension.raw_text}' -> {assoc.target_type}:{assoc.target_id} conf={assoc.confidence:.2f}")
        
        # Component graph
        cg = ComponentGraph(result)
        print(f"  Component graph: {cg.summary()['component_count']} components")
        print()

print("DONE")
