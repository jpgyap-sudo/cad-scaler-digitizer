import httpx, asyncio, os

async def test():
    url = "https://homeu.ph/products/vivaldi-dining-table"
    c = httpx.AsyncClient(timeout=120)
    r = await c.post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": url, "category": "table"})
    d = r.json()
    comp = d.get("comparison", {})
    dxf = d.get("dxf_file")
    print(f"comp keys: {list(comp.keys()) if comp else 'EMPTY'}")
    print(f"comp: {comp}")
    if dxf:
        fp = os.path.join("/tmp/cad_digitizer_outputs", dxf)
        print(f"dxf exists: {os.path.exists(fp)}")
    # Also call comparison directly
    if dxf and os.path.exists(f"/tmp/cad_digitizer_outputs/{dxf}"):
        from app.services.comparison_agent import compare_digitization
        import urllib.request
        image_resp = urllib.request.urlopen(url.replace("/products/", "/cdn/shop/files/") + ".png", timeout=30)
        # Actually just check if the comparison runs
        print("would call compare_digitization")
    await c.aclose()

asyncio.run(test())
