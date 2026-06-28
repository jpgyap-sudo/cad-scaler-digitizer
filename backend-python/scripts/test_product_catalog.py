"""Quick test of product catalog search functionality."""
import sys, json, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from app.backend.product_search import (
        load_catalog, search_by_visual_dna, search_by_text,
        search_combined, catalog_stats, get_family_visual_dna,
        get_similar, learn_product, build_visual_dna_vector,
    )

    # Test 1: Load catalog
    catalog = load_catalog()
    assert catalog["count"] == 259, f"Expected 259, got {catalog['count']}"
    assert len(catalog["dna_index"]) == 101
    print(f"1. Catalog OK: {catalog['count']} templates, {len(catalog['dna_index'])} families")

    # Test 2: Visual DNA vector building
    vec = build_visual_dna_vector({"top_shape": "rectangular", "base_type": "legs", "category_hint": "sofa"})
    assert len(vec) == 26, f"Expected 26D vector, got {len(vec)}D"
    print(f"2. Vector OK: {len(vec)}D")
    
    # Test 3: Visual DNA search - sofa
    results = search_by_visual_dna({"top_shape": "rectangular", "base_type": "legs", "category_hint": "sofa"}, top_k=3)
    assert len(results) <= 3
    if results:
        print(f"3. Visual sofa: {results[0]['family']} score={results[0]['score']:.3f}")
    else:
        print("3. Visual sofa: no results (low scores)")
    
    # Test 4: Visual DNA search - round table
    results = search_by_visual_dna({"top_shape": "round", "base_type": "pedestal", "category_hint": "table"}, top_k=3)
    if results:
        print(f"4. Visual table: {results[0]['family']} score={results[0]['score']:.3f}")
    else:
        print("4. Visual table: no results")
    
    # Test 5: Text search
    results = search_by_text("modern sofa", top_k=2)
    print(f"5. Text search: {len(results)} results")
    if results:
        print(f"   Top: {results[0]['family']} score={results[0]['score']:.1f}")
    
    # Test 6: Combined search
    combined = search_combined({"text": "coffee", "shape": "round", "category": "table"}, top_k=3)
    print(f"6. Combined: {combined['total']} results, mode={combined['mode']}")
    
    # Test 7: Stats
    stats = catalog_stats()
    print(f"7. Stats: {stats['total_templates']} templates, {stats['total_families']} families")
    print(f"   Categories: {stats['categories']}")
    
    # Test 8: Family DNA lookup
    dna = get_family_visual_dna("straight_sofa")
    print(f"8. Family DNA: top={dna.get('top_shape')}, base={dna.get('base_type')}, items={len(dna.get('items', []))}")
    
    # Test 9: Similar products
    similar = get_similar("straight_sofa", top_k=3)
    print(f"9. Similar: {len(similar)} results")
    if similar:
        for r in similar:
            print(f"   {r['family']}: score={r['score']:.3f}")
    
    # Test 10: Learn product
    result = learn_product({
        "title": "Test Product", "handle": "test-product",
        "template_family": "straight_sofa", "tags": ["sofa", "modern"],
    })
    print(f"10. Learn: status={result['status']}, local={result.get('local')}")
    
    # Test 11: Registry JSON validity
    reg_path = Path(__file__).resolve().parent.parent.parent / "resources" / "product_catalog" / "_registry.json"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    assert len(reg) == 259
    print(f"11. Registry file OK: {len(reg)} entries")
    
    # Test 12: Visual DNA JSON validity
    dna_path = Path(__file__).resolve().parent.parent.parent / "resources" / "product_catalog" / "visual_dna_index.json"
    dna = json.loads(dna_path.read_text(encoding="utf-8"))
    print(f"12. DNA index file OK: {len(dna)} families")
    
    print("\n=== ALL TESTS PASSED ===")
    
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
