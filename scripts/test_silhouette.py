import httpx, asyncio, json

async def test():
    url = "https://homeu.ph/products/tangerie-dining-table"
    r = await httpx.AsyncClient(timeout=180).post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": url, "category": "table"})
    d = r.json()
    svg = d.get("skeleton_svg", "")
    source = d.get("skeleton_source", "none")
    print(f"Skeleton source: {source}")
    print(f"SVG length: {len(svg)}")
    print(f"Has <svg tag: {'<svg' in svg}")
    print(f"First 200 chars: {svg[:200]}")
    print(f"Overall score: {d.get('comparison', {}).get('overall_score')}")

asyncio.run(test())
