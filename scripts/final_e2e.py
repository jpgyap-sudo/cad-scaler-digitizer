import asyncio, httpx, json

async def test():
    c = httpx.AsyncClient(timeout=300)
    r = await c.post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": "https://homeu.ph/products/tangerie-dining-table", "category": "table"})
    d = r.json()
    sk = d.get("skeleton_source", "none")
    hero = d.get("hero_view_added", False)
    dxf = d.get("dxf_file", "")
    print(f"SK source: {sk}")
    print(f"Hero added: {hero}")
    if dxf:
        fp = f"/tmp/cad_digitizer_outputs/{dxf}"
        import os, ezdxf
        if os.path.exists(fp):
            doc = ezdxf.readfile(fp)
            views = [e.plain_text() for e in doc.modelspace() if e.dxftype() == "MTEXT" and "VIEW" in e.plain_text()]
            print(f"Views ({len(views)}): {sorted(views)}")
            polys = sum(1 for e in doc.modelspace() if e.dxftype() == "LWPOLYLINE")
            print(f"Polylines: {polys}")
    await c.aclose()

asyncio.run(test())
