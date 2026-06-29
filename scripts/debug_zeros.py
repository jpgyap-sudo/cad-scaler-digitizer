import httpx, asyncio, sys

async def test_product(handle, category):
    url = f"https://homeu.ph/products/{handle}"
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post("http://localhost:8001/api/crawl-to-dxf", json={"url": url, "category": category})
        d = r.json()
        rd = d.get("resolved_dimensions", {})
        pd = d.get("page_dimensions", {})
        dd = d.get("detected_dimensions", {})
        comp = d.get("comparison", {})
        print(f"\n=== {handle} ({category}) ===")
        print(f"  resolved_dimensions: {rd}")
        print(f"  page_dimensions: {pd}")
        print(f"  detected_dimensions: {dd}")
        print(f"  comparison score: {comp.get('overall_score')}")
        print(f"  dev: {comp.get('dimension_deviation_pct')}")
        print(f"  entity: {comp.get('entity_match_score')}")

async def main():
    for handle, cat in [("vivaldi-dining-table", "table"), ("mallow-sofa", "sofa"),
                         ("ember-modern-sofa", "sofa"), ("aeris-console-table", "table")]:
        await test_product(handle, cat)

asyncio.run(main())
