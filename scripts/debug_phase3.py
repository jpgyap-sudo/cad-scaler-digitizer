"""Debug: check if Gemini call is being made in Phase 3 of crawl_to_dxf"""
import httpx, asyncio, json

async def test():
    c = httpx.AsyncClient(timeout=180)
    r = await c.post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": "https://homeu.ph/products/tangerie-dining-table", "category": "table"})
    d = r.json()
    print("Status:", d.get("status"))
    print("SK source:", d.get("skeleton_source"))
    print("Hero added:", d.get("hero_view_added"))
    print("DXF:", d.get("dxf_file", "")[:50])

    # Also test Gemini directly via the endpoint
    import os
    img_urls = [
        "https://cdn.shopify.com/s/files/1/0559/7377/3476/files/tangeri_05-600x400_480x480.jpg?v=1663649294",
    ]
    for img_url in img_urls:
        img_r = await c.get(img_url)
        if img_r.status_code == 200:
            files = {"file": ("test.jpg", img_r.content, "image/jpeg")}
            params = {"furniture_type": "rectangular_table", "width_cm": 100, "height_cm": 75}
            r2 = await c.post("http://localhost:8001/api/skeleton/gemini", data=params, files=files)
            print(f"\nDirect Gemini skeleton test:")
            print(f"  Status: {r2.status_code}")
            if r2.status_code == 200:
                svg = await r2.aread()
                print(f"  SVG: {len(svg)} bytes, Has svg: {b'<svg' in svg}")
            else:
                print(f"  Error: {r2.text[:200]}")
            break
    await c.aclose()

asyncio.run(test())
