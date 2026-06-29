import httpx, asyncio, ezdxf, os, json

async def test():
    url = "https://homeu.ph/products/tangerie-dining-table"
    r = await httpx.AsyncClient(timeout=180).post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": url, "category": "table"})
    d = r.json()
    dxf = d.get("dxf_file", "")
    if not dxf:
        print("No DXF generated")
        return
    fp = f"/tmp/cad_digitizer_outputs/{dxf}"
    if not os.path.exists(fp):
        print(f"DXF not found: {fp}")
        return
    doc = ezdxf.readfile(fp)
    msp = doc.modelspace()
    # Count all views
    texts = [e.plain_text() for e in msp if e.dxftype() == "MTEXT"]
    views = [t for t in texts if "VIEW" in t]
    polylines = sum(1 for e in msp if e.dxftype() == "LWPOLYLINE")
    print("Views in DXF:")
    for v in sorted(views):
        print(f"  {v}")
    print(f"Total polylines: {polylines}")
    print(f"Hero view added: {d.get('hero_view_added', False)}")
    print(f"SK source: {d.get('skeleton_source')}")
    print(f"DXF score: {d.get('comparison', {}).get('overall_score')}")

asyncio.run(test())
