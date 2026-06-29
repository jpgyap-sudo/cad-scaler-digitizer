"""Crawl JUST table and check everything"""
import httpx, asyncio, json, os

async def crawl(url, category):
    r = await httpx.AsyncClient(timeout=180).post(
        "http://localhost:8001/api/crawl-to-dxf",
        json={"url": url, "category": category})
    d = r.json()
    dxf = d.get("dxf_file", "")
    views, polys = [], 0
    if dxf:
        import ezdxf
        fp = f"/tmp/cad_digitizer_outputs/{dxf}"
        if os.path.exists(fp):
            doc = ezdxf.readfile(fp)
            views = sorted([e.plain_text() for e in doc.modelspace() if e.dxftype() == "MTEXT" and "VIEW" in e.plain_text()])
            polys = sum(1 for e in doc.modelspace() if e.dxftype() == "LWPOLYLINE")
    return d.get("skeleton_source"), d.get("hero_view_added"), views, polys

async def main():
    print("Crawling TABLE...")
    sk, hero, views, polys = await crawl("https://homeu.ph/products/tangerie-dining-table", "table")
    print(f"SK: {sk}, Hero: {hero}, Views: {len(views)}, Polys: {polys}")
    for v in views:
        print(f"  {v}")
    if hero:
        print("✅ ALL GOOD")
    else:
        print("❌ Hero view missing")
        # Check gallery
        g = await httpx.AsyncClient(timeout=10).get("http://localhost:8001/api/silhouette/gallery")
        d = g.json()
        print(f"Gallery: {len(d.get('silhouettes',{}))} items")

asyncio.run(main())
