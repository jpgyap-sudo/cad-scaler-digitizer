import httpx, asyncio, json

async def test():
    r = await httpx.AsyncClient(timeout=180).post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": "https://homeu.ph/products/tangerie-dining-table", "category": "table"})
    d = r.json()
    comp = d.get("comparison", {})
    print("Gemini verification results:")
    print(f"  cloud_verified: {comp.get('cloud_verified')}")
    print(f"  cloud_shape_match: {comp.get('cloud_shape_match')}")
    print(f"  cloud_issues: {json.dumps(comp.get('cloud_issues', []), indent=2)}")
    print(f"  overall_score: {comp.get('overall_score')}")
    print(f"  shape_class_score: {comp.get('shape_class_score')}")
    print(f"  dimension_deviation_pct: {comp.get('dimension_deviation_pct')}")

asyncio.run(test())
