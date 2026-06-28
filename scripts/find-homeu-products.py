"""Find HomeU products across all available categories."""
import httpx, asyncio

API = "http://python-worker:8001"
COLLECTIONS = {
    "dining-table": "table",
    "sofas": "sofa",
    "sofa": "sofa",
    "living-room": "sofa",
    "lighting": "lighting",
    "bed": "bed",
    "dining-chair": "chair",
    "stools": "chair",
    "cabinet": "cabinet",
    "cabinets": "cabinet",
    "desk": "desk",
    "bedroom": "bed",
    "center-table": "table",
    "bench-chaises": "chair",
    "console-table": "table",
}

async def get_handles(col):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://homeu.ph/collections/{col}/products.json?limit=4")
            if r.status_code == 200:
                return [p["handle"] for p in r.json().get("products", [])]
    except: pass
    return []

async def digitize(url, cat):
    try:
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post(f"{API}/api/crawl-to-dxf", json={"url": url, "category": cat})
            return r.json()
    except Exception as exc: return {"status": "error", "error": str(exc)}

async def main():
    all_products = []
    for col, cat in COLLECTIONS.items():
        handles = await get_handles(col)
        for h in handles:
            url = f"https://homeu.ph/products/{h}"
            if url not in [p["url"] for p in all_products]:
                all_products.append({"url": url, "cat": cat, "handle": h})

    print(f"Testing {len(all_products)} products across {len(set(p['cat'] for p in all_products))} categories\n")

    for i, p in enumerate(all_products):
        print(f"{i+1}. [{p['cat']}] {p['handle']}")
        result = await digitize(p["url"], p["cat"])
        dims = result.get("page_dimensions", {}) or {}
        comp = result.get("comparison", {}) or {}
        w = dims.get("width_cm", "?")
        h = dims.get("overall_height_cm", "?")
        sizes = len(dims.get("sizes", []))
        score = comp.get("overall_score", "N/A")
        dxf = result.get("dxf_file", False)
        error = result.get("error", "")
        print(f"   DXF={bool(dxf)} Dims={w}x{h} ({sizes}sizes) Score={score}")
        if error: print(f"   Error: {error[:80]}")
        print()

    print("=== All iterations complete ===")

asyncio.run(main())
