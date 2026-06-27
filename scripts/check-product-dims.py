"""Check Shopify product JSON for dimension data in ALL fields."""
import httpx, json, re, asyncio

URLS = [
    "https://homeu.ph/products/tangerie-dining-table.json",
    "https://www.jardan.com.au/products/nk198.json",
]

async def check(url):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url)
        if r.status_code != 200:
            print(f"{url}: HTTP {r.status_code}")
            return
        d = r.json()
        p = d["product"]
        print(f"\n=== {p['title']} ===")

        # Check ALL fields for dimension-like data
        for key, val in p.items():
            sv = str(val)
            if any(kw in sv.lower() for kw in ["cm", "mm", "inch", "size", "wide", "depth", "height", "weight", "dimension"]):
                if len(sv) < 500:
                    print(f"  {key}: {sv[:200]}")

        # Check options for size references
        print("\n  Options:")
        for o in p.get("options", []):
            print(f"    {o['name']}: {o['values']}")

        # Check first variant for dimension data
        if p.get("variants"):
            v = p["variants"][0]
            print("\n  First variant keys with dim data:")
            for k in v:
                if any(kw in k.lower() for kw in ["weight", "dim", "size", "option"]):
                    print(f"    {k}: {v[k]}")

        # Extract all numbers near measurement words in body_html
        html = p.get("body_html", "") or ""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"&[a-z]+;", " ", text)
        print("\n  Dimension mentions in description:")
        for m in re.findall(r"[^.]{0,40}(?:\d+[\.]?\d*\s*(?:cm|mm|in|\"|inch|m|ft))[^.]{0,40}\.", text, re.I):
            print(f"    ...{m.strip()}...")

        # Check all variant options for size patterns
        print("\n  All variant size options:")
        seen = set()
        for v in p.get("variants", []):
            for opt_key in ["option1", "option2", "option3"]:
                opt_val = v.get(opt_key, "")
                if opt_val and opt_val not in seen:
                    seen.add(opt_val)
                    if any(c.isdigit() for c in opt_val):
                        print(f"    {opt_key}: {opt_val}")

asyncio.run(check(URLS[0]))
