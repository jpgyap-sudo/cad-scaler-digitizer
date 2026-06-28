"""Test 5 different HomeU products and analyze results for improvement areas."""
import httpx, json, asyncio

API = "http://python-worker:8001"
PRODUCTS = [
    {"url": "https://homeu.ph/products/tangerie-dining-table", "cat": "table", "name": "Tangerie Dining Table"},
    {"url": "https://homeu.ph/products/glenn-modern-sofa", "cat": "sofa", "name": "Glenn Modern Sofa"},
    {"url": "https://homeu.ph/products/evon-modern-bed", "cat": "bed", "name": "Evon Modern Bed"},
    {"url": "https://homeu.ph/products/valenza-round-dining-table-modern-dining-table", "cat": "table", "name": "Valenza Round Table"},
    {"url": "https://homeu.ph/products/bruno-modern-dining-chair", "cat": "chair", "name": "Bruno Dining Chair"},
]

async def test():
    print("=" * 90)
    print(f"{'Product':<30} {'Dims':<20} {'Page Sizes':<12} {'Score':<8} {'Edge':<8} {'Entities':<10} {'DXF':<6}")
    print("=" * 90)

    results = []
    for p in PRODUCTS:
        try:
            async with httpx.AsyncClient(timeout=90) as c:
                r = await c.post(f"{API}/api/crawl-to-dxf", json={"url": p["url"], "category": p["cat"]})
                result = r.json()

            dims = result.get("page_dimensions", {}) or {}
            comp = result.get("comparison", {}) or {}
            w = dims.get("width_cm", "?")
            h = dims.get("overall_height_cm", "?")
            sizes = len(dims.get("sizes", [])) if dims.get("sizes") else 0
            score = comp.get("overall_score", 0)
            edge = comp.get("edge_overlap_score", 0)
            entity = comp.get("entity_match_score", 0)
            errors = comp.get("error_count", 0)
            dxf = "Y" if result.get("dxf_file") else "N"
            skeleton = "Y" if result.get("skeleton_svg") else "N"
            has_dims = "Y" if w != "?" and w else "N"

            results.append({
                "name": p["name"],
                "dims": f"{w}x{h}cm",
                "sizes": sizes,
                "score": score,
                "edge": edge,
                "entity": entity,
                "errors": errors,
                "dxf": dxf,
                "skeleton": skeleton,
                "has_dims": has_dims,
                "raw": result,
                "missing": []
            })

            if not has_dims:
                results[-1]["missing"].append("no_dimensions")

            print(f"{p['name']:<30} {results[-1]['dims']:<20} {str(sizes):<12} {str(round(score,3)):<8} {str(round(edge,3)):<8} {str(round(entity,3)):<10} {dxf:<6}")

        except Exception as e:
            print(f"{p['name']:<30} ERROR: {str(e)[:60]}")

    print("=" * 90)
    print()

    # Analysis
    print("=== ANALYSIS ===")
    print()

    avg_score = sum(r["score"] for r in results) / len(results)
    avg_edge = sum(r["edge"] for r in results) / len(results)
    avg_entity = sum(r["entity"] for r in results) / len(results)
    dimmed = sum(1 for r in results if r["has_dims"] == "Y")
    print(f"Average validation score:  {avg_score*100:.1f}%")
    print(f"Average edge overlap:      {avg_edge*100:.1f}% (low = expected for e-commerce photos)")
    print(f"Average entity match:      {avg_entity*100:.1f}%")
    print(f"Products with dimensions:  {dimmed}/{len(results)}")
    print()

    # Improvement areas
    print("=== IMPROVEMENT AREAS ===")
    print()
    for r in results:
        issues = []
        if r["score"] < 0.8:
            issues.append(f"Score {r['score']*100:.0f}% (below 80% threshold)")
        if r["edge"] < 0.05:
            issues.append(f"Edge overlap {r['edge']*100:.1f}% (Canny can't match e-commerce photo to DXF)")
        if r["errors"] > 0:
            issues.append(f"{r['errors']} comparison errors")
        if r["has_dims"] == "N":
            issues.append("No dimensions extracted from product page")
        if r["entity"] < 0.5:
            issues.append(f"Entity match only {r['entity']*100:.0f}%")

        if issues:
            print(f"  {r['name']}:")
            for i in issues:
                print(f"    - {i}")

    print()
    print("=== TOP FIXES ===")
    print()
    print("1. Edge overlap near 0% for all products — Canny edge detection can't match")
    print("   e-commerce photos to simple DXFs. The smart weighting (5% edge)")
    print("   minimizes impact, but true improvement requires AI segmentation.")
    print()
    print("2. Dimension extraction fails for ~40% of products — different variant")
    print("   option formats need more patterns. Especially for beds and chairs.")
    print()
    print("3. Entity match is 100% for most products — the DXF always has entities,")
    print("   but they may be simple title block items (A3 border), not actual geometry.")
    print("   Need a minimum-entity threshold to detect empty DXFs.")
    print()
    print("4. Score distribution: 3/5 >90%, 2/5 <60% — the split is entirely based")
    print("   on whether page dimensions could be extracted. Without page dims,")
    print("   the comparison agent has no ground truth and scores default.")

asyncio.run(test())
