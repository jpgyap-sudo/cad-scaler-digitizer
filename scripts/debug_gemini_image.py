"""Debug: check the actual image downloaded during crawl and why Gemini returns 400"""
import httpx, asyncio, json, base64, os

async def test():
    # Step 1: crawl for the product page and image
    c = httpx.AsyncClient(timeout=60)
    page_r = await c.get("https://homeu.ph/products/tangerie-dining-table",
        headers={"User-Agent": "Mozilla/5.0"})
    html = page_r.text

    # Find image URL from the page
    import re
    img_urls = re.findall(r'(?:https?:)?//[^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?', html)
    img_urls = [u for u in img_urls if "cdn.shopify" in u or "cdn.shop" in u]
    print(f"Found {len(img_urls)} image URLs")
    if img_urls:
        img_url = img_urls[0]
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        print(f"Using: {img_url}")
        img_r = await c.get(img_url, headers={"User-Agent": "Mozilla/5.0"})
        print(f"Image status: {img_r.status_code}")
        print(f"Content-Type: {img_r.headers.get('content-type')}")
        print(f"Image size: {len(img_r.content)} bytes")
        print(f"First 4 bytes: {img_r.content[:4]}")

        # Check if valid image
        if img_r.content[:4] in (b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\x89PNG', b'RIFF'):
            print("Valid image data confirmed")
            # Try Gemini with this image
            b64 = base64.b64encode(img_r.content).decode()
            prompt = 'Return ONLY a JSON with "svg" and "dxf_polylines" fields describing a simple rectangle.'
            gemini_r = await c.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                params={"key": os.environ["GEMINI_API_KEY"]},
                json={"contents": [{"parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}}
                ]}]},
                timeout=30)
            print(f"Gemini status: {gemini_r.status_code}")
            if gemini_r.status_code != 200:
                print(f"Gemini error: {gemini_r.text[:500]}")
            else:
                text = gemini_r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[{}])[0].get("text","")
                print(f"Gemini response: {text[:200]}")
        else:
            print("Not valid image data")
            print(f"Content preview: {img_r.content[:200]}")
    await c.aclose()

asyncio.run(test())
