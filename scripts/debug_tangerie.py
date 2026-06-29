import httpx, asyncio, os, json

async def test():
    url = "https://homeu.ph/products/tangerie-dining-table"
    c = httpx.AsyncClient(timeout=120)
    r = await c.post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": url, "category": "table"})
    d = r.json()
    comp = d.get("comparison", {})
    rd = d.get("resolved_dimensions", {})
    detected = d.get("detected_dimensions", {})
    pd = d.get("page_dimensions", {})
    ftype = d.get("furniture", {}).get("type", "N/A")
    print(f"furniture type: {ftype}")
    print(f"resolved: {json.dumps(rd, indent=2)}")
    print(f"page_dims: {json.dumps(pd, indent=2)}")
    print(f"comparison: {json.dumps(comp, indent=2)}")
    print(f"dxf_file: {d.get('dxf_file')}")
    await c.aclose()

asyncio.run(test())
