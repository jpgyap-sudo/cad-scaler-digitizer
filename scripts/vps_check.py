import httpx, asyncio, os
async def test():
    # 1. Check templates loaded
    t = await httpx.AsyncClient(timeout=10).get("http://localhost:8001/api/templates")
    td = t.json()
    print(f"Templates: {len(td.get('templates',[]))}")
    # 2. Crawl a product and check views in DXF
    c = httpx.AsyncClient(timeout=180)
    r = await c.post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": "https://homeu.ph/products/tangerie-dining-table", "category": "table"})
    d = r.json()
    dxf = d.get("dxf_file","")
    print(f"SK source: {d.get('skeleton_source')}, Hero: {d.get('hero_view_added')}")
    if dxf:
        import ezdxf
        fp = f"/tmp/cad_digitizer_outputs/{dxf}"
        if os.path.exists(fp):
            doc = ezdxf.readfile(fp)
            views = sorted([e.plain_text() for e in doc.modelspace() if e.dxftype() == "MTEXT" and "VIEW" in e.plain_text()])
            print(f"DXF views ({len(views)}): {views}")
    await c.aclose()
asyncio.run(test())
