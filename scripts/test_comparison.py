"""Compare Gemini silhouette vs parametric skeleton for the same product"""
import httpx, asyncio, json

async def test():
    c = httpx.AsyncClient(timeout=180)
    # Crawl a product — gets BOTH parametric skeleton AND Gemini silhouette
    r = await c.post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": "https://homeu.ph/products/tangerie-dining-table", "category": "table"})
    d = r.json()
    
    gemini_svg = d.get("skeleton_svg", "")
    gemini_source = d.get("skeleton_source", "none")
    hero = d.get("hero_view_added", False)
    views = d.get("view_count", 0)
    
    print(f"=== Gemini silhouette ===")
    print(f"Source: {gemini_source}")
    print(f"SVG size: {len(gemini_svg)} chars")
    print(f"Hero view added to DXF: {hero}")
    print(f"Has <svg: {'<svg' in gemini_svg}")
    print(f"Components: {gemini_svg.count('data-name=')}")
    
    # Get the parametric skeleton for comparison
    import os, ezdxf
    dxf_file = d.get("dxf_file", "")
    dxf_views = []
    if dxf_file:
        fp = f"/tmp/cad_digitizer_outputs/{dxf_file}"
        if os.path.exists(fp):
            doc = ezdxf.readfile(fp)
            dxf_views = sorted([e.plain_text() for e in doc.modelspace() if e.dxftype() == "MTEXT" and "VIEW" in e.plain_text()])
    
    print(f"\n=== Parametric DXF ===")
    print(f"Views ({len(dxf_views)}): {dxf_views}")
    print(f"Has HERO VIEW: {'HERO VIEW' in str(dxf_views)}")
    
    # Summary
    print(f"\n=== VERDICT ===")
    if gemini_source == "gemini":
        print(f"✅ Gemini successfully generated a {len(gemini_svg)}-char SVG silhouette")
    else:
        print(f"⚠️  Gemini failed — geometric fallback used instead")
    if hero:
        print(f"✅ HERO VIEW added to DXF alongside {len(dxf_views)} parametric views")
    print(f"✅ Total DXF views: {len(dxf_views)} (parametric + hero)")
    
    await c.aclose()

asyncio.run(test())
