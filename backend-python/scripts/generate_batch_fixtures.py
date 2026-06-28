"""Generate batch fixture spec for product catalog verification.

This script creates a comprehensive fixture specs JSON that the benchmark
system can use to verify product catalog search accuracy.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend-python
CATALOG = ROOT.parent / "resources" / "product_catalog"
REGISTRY = CATALOG / "_registry.json"
DNA_INDEX = CATALOG / "visual_dna_index.json"

registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
dna_index = json.loads(DNA_INDEX.read_text(encoding="utf-8"))

fixtures = []

# Create search test cases per category
test_cases = [
    {"query": "modern sofa", "expected_families": ["straight_sofa", "club_sofa", "modular_sofa"], "mode": "text"},
    {"query": "round coffee table", "expected_families": ["round_coffee_table", "round_nested_coffee_table"], "mode": "text"},
    {"query": "dining chair", "expected_families": ["upholstered_dining_chair", "dining_armchair"], "mode": "text"},
    {"query": "sintered stone slab", "expected_families": ["stone_slab_swatch", "sintered_stone_swatch"], "mode": "text"},
]

# Visual DNA test cases
dna_test_cases = [
    {
        "name": "straight sofa visual",
        "features": {"top_shape": "rectangular", "base_type": "legs", "category_hint": "sofa", "symmetry": "symmetric"},
        "top_expected_family": ["straight_sofa", "classic_straight_sofa", "club_sofa", "modular_sofa"],
    },
    {
        "name": "round table visual",
        "features": {"top_shape": "round", "base_type": "pedestal", "leg_type": "single_pedestal", "category_hint": "table"},
        "top_expected_family": ["round_dining_table", "round_coffee_table", "round_nested_coffee_table"],
    },
    {
        "name": "ceiling fan visual",
        "features": {"top_shape": "round", "base_type": "ceiling", "category_hint": "fan"},
        "top_expected_family": ["ceiling_fan", "ceiling_fan_3_blade_light"],
    },
    {
        "name": "wall panel visual",
        "features": {"top_shape": "rectangular", "base_type": "wall_mounted", "category_hint": "panel"},
        "top_expected_family": ["wall_panel", "fluted_wall_panel"],
    },
]

# Per-batch family counts
batch_families = {}
for entry in registry:
    b = entry.get("batch", 0)
    f = entry.get("template_family", "unknown")
    if b not in batch_families:
        batch_families[b] = set()
    batch_families[b].add(f)

fixture = {
    "schema_version": "fixture-v1",
    "name": "batch_4_product_catalog_verification",
    "description": "Verification of 259 Shopify product templates integrated in resources/product_catalog",
    "total_templates": len(registry),
    "total_families": len(dna_index),
    "batches": {
        str(b): {"count": sum(1 for e in registry if e.get("batch") == b), "families": sorted(fs)}
        for b, fs in batch_families.items()
    },
    "text_search_tests": test_cases,
    "visual_dna_tests": dna_test_cases,
    "families": {
        fam: {
            "count": sum(1 for e in registry if e.get("template_family") == fam),
            "visual_dna": {
                "top_shape": info.get("top_shape"),
                "base_type": info.get("base_type"),
                "leg_type": info.get("leg_type"),
                "category_hint": info.get("category_hint"),
                "archetype_score": info.get("archetype_score"),
            },
        }
        for fam, info in sorted(dna_index.items())
    },
}

output = CATALOG / "_fixture_spec.json"
output.write_text(json.dumps(fixture, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Fixture spec written: {output}")
print(f"Templates: {len(registry)}, Families: {len(dna_index)}, Batches: {len(batch_families)}")
