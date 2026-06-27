"""Find Jardan dining table product URLs and test 5 of them."""
import httpx, re, asyncio, json

API = "http://python-worker:8001"
BASE = "https://www.jardan.com.au"

async def find_products():
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        r = await c.get(BASE + "/pages/dining-tables", headers={"User-Agent": "Mozilla/5.0"})
        html = r.text
    urls = sorted(set(re.findall(r'href=["\'](https://www.jardan.com.au/products/[^"\']+)["\']', html)))
    return urls[:8]

async def digitize(url):
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(f"{API}/api/crawl-to-dxf", json={"url": url, "category": "table"})
        return r.json()

async def main():
    urls = await find_products()
    print(f"Found {len(urls)} dining table products\n")

    for i, url in enumerate(urls[:5]):
        slug = url.split("/")[-1]
        print(f"{i+1}. {slug}")
        try:
            result = await digitize(url)
            dims = result.get("page_dimensions", {}) or {}
            cmp = result.get("comparison", {}) or {}
            dxf = result.get("dxf_file", "")
            w = dims.get("width_cm", "?")
            h = dims.get("overall_height_cm", "?")
            score = cmp.get("overall_score", "N/A")
            sizes = dims.get("sizes", [])
            sz = f", {len(sizes)} sizes" if sizes else ""
            print(f"   DXF: {bool(dxf)} | Dims: {w}x{h}{sz} | Score: {score}")
            if isinstance(score, (int, float)) and score >= 0.9:
                print("   🎯 REACHED")
            elif isinstance(score, (int, float)):
                print(f"   Gap: {(0.9 - score) * 100:.1f}%")
        except Exception as e:
            print(f"   ERROR: {e}")
        print()

    print("Done")

asyncio.run(main())
