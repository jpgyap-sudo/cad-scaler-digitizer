"""Find 5 HomeU dining table products and run crawl-to-dxf on each."""
import httpx, re, asyncio, json, sys

API = "http://python-worker:8001"
COLLECTION = "https://homeu.ph/collections/dining-table"

async def find_products():
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        r = await c.get(COLLECTION, headers={"User-Agent": "Mozilla/5.0"})
        html = r.text
    slugs = sorted(set(re.findall(r'href=["\']/products/([^"\'?]+)["\']', html)))
    return [f"https://homeu.ph/products/{s}" for s in slugs if not s.endswith(".webp") and not s.endswith(".jpg") and not s.endswith(".png")][:5]

async def digitize(url):
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            f"{API}/api/crawl-to-dxf",
            json={"url": url, "category": "table"},
        )
        return r.json()

async def main():
    products = await find_products()
    print(f"Testing {len(products)} products:\n")

    for i, url in enumerate(products):
        slug = url.split("/")[-1]
        print(f"{i+1}. {slug}")
        print(f"   URL: {url}")
        try:
            result = await digitize(url)
            status = result.get("status", "failed")
            dims = result.get("page_dimensions", {})
            comp = result.get("comparison", {})
            dxf = result.get("dxf_file", "N/A")[:30]
            w = dims.get("width_cm", "?")
            h = dims.get("overall_height_cm", "?")
            score = comp.get("overall_score", "N/A")
            errors = comp.get("error_count", 0)
            print(f"   Status: {status}")
            if status == "completed":
                print(f"   Dims: {w}cm x {h}cm  |  DXF: {dxf}")
                if score != "N/A":
                    print(f"   Comparison score: {score}  |  Errors: {errors}")
            else:
                err = result.get("error", "unknown")
                print(f"   Error: {err[:80]}")
        except Exception as e:
            print(f"   Error: {e}")
        print()

    print("=== Done ===")

asyncio.run(main())
