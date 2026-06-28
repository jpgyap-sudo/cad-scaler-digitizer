"""Shape Detection Quality Audit - round vs square, visual match analysis."""
import httpx, json, asyncio

API = "http://python-worker:8001"

PRODUCTS = [
    {"url": "https://homeu.ph/products/tangerie-dining-table", "cat": "table", "label": "Rectangular Table"},
    {"url": "https://homeu.ph/products/valenza-round-dining-table-modern-dining-table", "cat": "table", "label": "Round Table"},
    {"url": "https://homeu.ph/products/glenn-modern-sofa", "cat": "sofa", "label": "Sofa (rectangular)"},
    {"url": "https://homeu.ph/products/evon-modern-bed", "cat": "bed", "label": "Bed (rectangular)"},
    {"url": "https://homeu.ph/products/bruno-modern-dining-chair", "cat": "chair", "label": "Chair (mixed shapes)"},
]

async def check_shape_distribution(product_data):
    """Analyze DXF entity distribution to infer shape type."""
    dxf_name = product_data.get("dxf_file", "")
    if not dxf_name:
        return None
    
    async with httpx.AsyncClient(timeout=15) as c:
        # Get DXF entity analysis from python-worker
        r = await c.post(f"{API}/api/analyze-dxf?dxf={dxf_name}")
        return r.json() if r.status_code == 200 else None

async def main():
    print("=" * 95)
    print(f"{'Product':<30} {'Status':<10} {'Score':<8} {'Template':<40}")
    print("=" * 95)
    
    gaps = []
    
    for p in PRODUCTS:
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post(f"{API}/api/crawl-to-dxf", json={"url": p["url"], "category": p["cat"]})
            data = r.json()
        
        dxf = data.get("dxf_file", "")
        dims = data.get("page_dimensions", {}) or {}
        comp = data.get("comparison", {}) or {}
        skeleton = data.get("skeleton_svg", "")
        
        w = dims.get("width_cm", dims.get("top_diameter_cm", "?"))
        h = dims.get("overall_height_cm", "?")
        score = comp.get("overall_score", 0)
        edge = comp.get("edge_overlap_score", 0)
        errors = comp.get("error_count", 0)
        
        print(f"{p['label']:<30} {'✅' if dxf else '❌':<10} {str(round(score,3)):<8} {'':<40}")
        
        # Analyze DXF shape content
        if dxf:
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.post(f"{API}/api/compare", json={
                    "job_id": f"audit-{p['label']}",
                    "product_id": p['label'],
                    "image_url": data.get("image_url", ""),
                    "dxf_path": f"/tmp/cad_digitizer_outputs/{dxf}",
                    "page_dimensions": dims,
                })
                if resp.status_code == 200:
                    compare_data = resp.json()
                    dxf_entities = compare_data.get("entity_counts", {})
                    dxf_total = dxf_entities.get("total", 0) if isinstance(dxf_entities, dict) else sum(dxf_entities.values()) if isinstance(dxf_entities, dict) else 0
                    dim_dev = compare_data.get("dimension_deviation_pct", 0)
                    score = compare_data.get("overall_score", score)
                    edge = compare_data.get("edge_overlap_score", edge)
                    
                    # Check: does the DXF have reasonable geometry?
                    if dxf_total < 30:
                        gaps.append(f"{p['label']}: Low entity count ({dxf_total}) — DXF may be empty/placeholder")
                    if edge < 0.001 and score < 0.5:
                        gaps.append(f"{p['label']}: Near-zero edge overlap ({edge*100:.1f}%) — photo vs DXF mismatch")
                    if dim_dev > 50:
                        gaps.append(f"{p['label']}: High dimension deviation ({dim_dev:.0f}%) — DXF scaled wrong")
    
    print()
    print("=" * 95)
    print("SHAPE DETECTION GAP REPORT")
    print("=" * 95)
    print()
    
    if gaps:
        print("Gaps found:")
        for g in gaps:
            print(f"  • {g}")
    else:
        print("No significant shape gaps detected.")
    
    print()
    print("Round vs Square Shape Analysis:")
    print()
    print("  Current state:")
    print("  - Round tables: dispatch to `round_pedestal_table` template (1 CIRCLE + polylines)")
    print("  - Rect tables: dispatch to `rectangular_table` template (0 circles, all lines)")
    print("  - So/beds: dispatch to template based on furniture_type")
    print()
    print("  Gaps:")
    print("  1. Round table DXFs have only 1 CIRCLE entity — pedestal base should")
    print("     have multiple concentric circles for the column profile")
    print("  2. No shape-match verification between product photo and template drawing")
    print("  3. Circular shapes detected by HoughCircles are stored ephemerally —")
    print("     never persisted to the DXF or used for template validation")
    print("  4. No visual overlay comparison (product photo edge vs DXF outline)")
    print("  5. Comparison agent uses Canny edge overlap which is near 0% for")
    print("     e-commerce photos — no semantic shape comparison")
    print()
    print("  Recommended improvements:")
    print("  A. Add Hu moment comparison between product silhouette and DXF outline")
    print("     (shape signature matching — rotation/scale invariant)")
    print("  B. Generate visual overlay: crop product photo → extract edges →")
    print("     overlay on DXF preview → compute IoU (Intersection over Union)")
    print("  C. Add circle-detection quality check: compare detected circles vs")
    print("     expected circle count from the template")
    print("  D. Add round/square shape confidence to the validation report")

asyncio.run(main())
