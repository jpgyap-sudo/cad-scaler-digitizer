import httpx, asyncio, os, sys

async def test():
    c = httpx.AsyncClient(timeout=120)
    r = await c.post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": "https://homeu.ph/products/vivaldi-dining-table", "category": "table"})
    d = r.json()
    comp = d.get("comparison", {})
    dxf = d.get("dxf_file")
    det = d.get("detected_dimensions", {})
    res = d.get("resolved_dimensions", {})
    print(f"dxf_file: {dxf}")
    print(f"detected_dimensions: {det}")
    print(f"resolved_dimensions: {res}")
    print(f"comparison: {comp}")
    # Check DXF on disk
    if dxf:
        fp = os.path.join("/tmp/cad_digitizer_outputs", dxf)
        print(f"dxf exists: {os.path.exists(fp)}")
    await c.aclose()

asyncio.run(test())
