"""Deep search for product dimensions in HomeU page - all sources."""
import httpx, re, json, asyncio

async def extract():
    url = "https://homeu.ph/products/tangerie-dining-table"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
        html = r.text

    # 1. Check ALL script tags for product data
    print("=== Script tags with product/size data ===")
    for script in re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
        content = script.strip()
        # Check for Shopify product JSON, dimensions, sizes
        if any(kw in content.lower() for kw in ["product", "variant", "dimension", "size", "inch", "cm", "\"width\"", "\"height\"", "\"depth\""]):
            # Extract just the relevant parts to keep output manageable
            matches = re.findall(r'[^.]{0,50}(?:dimension|size|width|height|depth|inch|cm|variant)[^.]{0,50}\.', content, re.I)[:5]
            if matches:
                for m in matches:
                    print(f"  ...{m.strip()}...")
            # Also check for JSON
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    for key in data:
                        if any(k in key.lower() for k in ["dim", "size", "width", "height", "variant"]):
                            print(f"  JSON key '{key}': {str(data[key])[:200]}")
            except:
                pass

    # 2. Check ALL HTML for dimension-ish numbers near size-related words
    print("\n=== Numbers near size/dim words ===")
    for m in re.findall(r'[^.]{0,30}(?:size|dimension|measurement|width|height|depth)[^.]{0,40}\.', html, re.I):
        m = m.strip()
        if any(c.isdigit() for c in m):
            print(f"  {m}")

    # 3. Check HTML for any W:xxx H:xxx D:xxx or similar
    print("\n=== All structured dimension patterns ===")
    for m in re.findall(r'(?:W|H|D|L|Width|Height|Depth|Length)\s*[:\s=]\s*\d+[\.]?\d*\s*(?:cm|in|mm|\")?', html):
        print(f"  {m.strip()}")

    # 4. Check for any inch or cm patterns 
    print("\n=== All measurements (numbers followed by in/cm) ===")
    for m in re.findall(r'\d+[\.]?\d*\s*(?:cm|in|mm|\")\s*(?:W|H|D|L|x\s*\d)?', html, re.I):
        print(f"  {m.strip()}")

asyncio.run(extract())
