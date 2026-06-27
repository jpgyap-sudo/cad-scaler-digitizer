"""Extract product dimensions from HomeU product page."""
import httpx, re, json, asyncio

async def extract():
    url = "https://homeu.ph/products/tangerie-dining-table"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
        html = r.text

    print(f"HTML size: {len(html)} bytes")
    print("")

    # 1. JSON-LD (product structured data)
    print("=== JSON-LD ===")
    for ld in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.I):
        try:
            data = json.loads(ld)
            # Print relevant product fields
            if isinstance(data, dict):
                name = data.get("name", "")
                desc = data.get("description", "")[:200]
                offers = data.get("offers", {})
                gtin = data.get("gtin", "")
                brand = data.get("brand", {})
                print(f"  Name: {name}")
                print(f"  Desc: {desc}")
                print(f"  Sku: {data.get('sku','')}")
                if isinstance(brand, dict):
                    print(f"  Brand: {brand.get('name','')}")
                # Check for dimension-related fields
                for key in data:
                    if any(kw in key.lower() for kw in ["dim", "width", "height", "depth", "size", "weight"]):
                        print(f"  {key}: {data[key]}")
        except json.JSONDecodeError as e:
            print(f"  Parse error: {e}")

    # 2. All meta tags
    print("\n=== Dimension Meta Tags ===")
    for m in re.findall(r'<meta[^>]*(?:width|height|depth|size|dimension)[^>]*>', html, re.I):
        print(f"  {m.strip()}")

    # 3. Text patterns containing dimensions
    print("\n=== Dimension Text Patterns ===")
    for pattern_name, pattern in [
        ("W x D x H", r'(\d+[\.]?\d*)\s*x\s*(\d+[\.]?\d*)\s*x\s*(\d+[\.]?\d*)\s*(?:cm|mm|CM)?'),
        ("W/H/D labels", r'(?:W|Width|width|H|Height|height|D|Depth|depth|L|Length|length)[:\s]*(\d+[\.]?\d*)\s*(?:cm|mm|CM)?'),
        ("Number+cm", r'(\d+[\.]?\d*)\s*(?:cm|mm)\s*(?:W|H|D|L|width|height|depth|length)?',),
    ]:
        matches = re.findall(pattern, html)
        if matches:
            print(f"  {pattern_name}: {matches[:10]}")

    # 4. Text near "cm" mentions
    print("\n=== 'cm' Context ===")
    cm_bits = re.findall(r'>([^<]*\d+[\.]?\d*\s*cm[^<]*)<', html, re.I)
    seen = set()
    for b in cm_bits:
        b = b.strip()
        if b and b not in seen and len(b) < 100:
            seen.add(b)
            print(f"  {b}")

asyncio.run(extract())
