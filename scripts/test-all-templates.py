"""Test template matching across all HomeU product categories.
For each category, tests 2-3 products and reports template match accuracy."""
import httpx, re, json, asyncio

API = "http://python-worker:8001"
BASE = "https://homeu.ph"

# Categories to test with their expected template family
CATEGORIES = {
    "dining-table": {"family": "table", "product_type": "rectangular_table"},
    "sofas": {"family": "seating", "product_type": "sofa"},
    "cabinet": {"family": "cabinet", "product_type": "sideboard"},
    "dining-chair": {"family": "seating", "product_type": "dining_chair"},
    "bed": {"family": "bed", "product_type": "bed"},
    "desk": {"family": "desk", "product_type": "office_desk"},
    "lighting": {"family": None, "product_type": None},
    "console-table": {"family": "table", "product_type": "console_table"},
    "center-table": {"family": "table", "product_type": "rectangular_table"},
    "bench-chaises": {"family": "seating", "product_type": "lounge_chair"},
    "stools": {"family": "seating", "product_type": "dining_chair"},
}

async def find_products(collection, limit=3):
    url = f"{BASE}/collections/{collection}"
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []
        slugs = sorted(set(re.findall(r'href=["\']/products/([^"\'?]+)["\']', r.text)))
        return [f"{BASE}/products/{s}" for s in slugs if "?" not in s and "jpg" not in s and "webp" not in s][:limit]

async def crawl_to_dxf(url, category):
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{API}/api/crawl-to-dxf", json={"url": url, "category": category})
        return r.json()

async def suggest_template(ft, w=0, h=0, d=0):
    params = {"furniture_type": ft}
    if w: params["width_cm"] = w
    if h: params["height_cm"] = h
    if d: params["depth_cm"] = d
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{API}/api/templates/suggest", params=params)
        return r.json()

async def main():
    print("=" * 90)
    print(f"{'Category':<18} {'Product':<35} {'Template Graph':<35} {'Match':<8} {'Conf':<6}")
    print("=" * 90)

    total = 0
    correct = 0
    no_dims = 0
    no_template = 0

    for category, config in CATEGORIES.items():
        urls = await find_products(category, limit=2)
        if not urls:
            print(f"{category:<18} {'No products found':<35}")
            continue

        for url in urls:
            slug = url.split("/")[-1][:33]
            result = await crawl_to_dxf(url, category)
            dims = result.get("page_dimensions", {}) or {}
            comparison = result.get("comparison", {}) or {}
            dxf = result.get("dxf_file")
            total += 1

            w = dims.get("width_cm", 0) or 0
            h = dims.get("overall_height_cm", 0) or 0
            d = dims.get("depth_cm", 0) or 0
            l = dims.get("length_cm", 0) or 0

            # Determine which furniture_type to suggest
            ft = config["product_type"] or category

            if w == 0 and h == 0:
                no_dims += 1
                ft_result = await suggest_template(ft)
                tpl = ft_result.get("template_graph", {}) or {}
                tpl_name = tpl.get("name", "")[:33] if tpl.get("name") else "N/A"
                match = "SKIP"
                conf = ft_result.get("overall_confidence", " -")
                print(f"{category:<18} {slug:<35} {tpl_name:<35} {match:<8} {str(conf)[:5]:<6}")
            else:
                ft_result = await suggest_template(ft, w, h or d or l)
                tpl = ft_result.get("template_graph", {}) or {}
                tpl_name = tpl.get("name", "")[:33] if tpl.get("name") else "NONE"
                tpl_id = tpl.get("id", "") if tpl.get("id") else "none"
                solved = ft_result.get("solved_dimensions", {}) or {}
                conf = ft_result.get("overall_confidence", 0) or 0

                # Check if template family matches expected
                expected_family = config["family"]
                actual_family = tpl_id.split(".")[0] if tpl_id and tpl_id != "none" else ""
                if expected_family and actual_family and actual_family in expected_family:
                    match = "PASS"
                    correct += 1
                elif expected_family and actual_family:
                    match = "WRONG"
                elif not tpl_id or tpl_id == "none":
                    match = "NONE"
                    no_template += 1
                else:
                    match = "PASS"
                    correct += 1

                print(f"{category:<18} {slug:<35} {tpl_name:<35} {match:<8} {str(conf)[:5]:<6}")

            await asyncio.sleep(0.5)

    print("=" * 90)
    tested = total - no_dims
    if tested > 0:
        acc = correct / tested * 100
    else:
        acc = 0
    print(f"Tested: {tested} with dims | Correct match: {correct}/{tested} ({acc:.0f}%)")
    print(f"Skipped (no dims): {no_dims} | No template found: {no_template}")

asyncio.run(main())
