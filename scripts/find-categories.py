"""Find all HomeU product categories."""
import httpx, re, asyncio

async def main():
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        r = await c.get("https://homeu.ph", headers={"User-Agent": "Mozilla/5.0"})
        html = r.text

    # Find collection links
    collections = sorted(set(
        m for m in re.findall(r'href=[\'"/]collections/([^\'"?]+)[\'"]?', html)
        if m and m.strip()
    ))
    print("All collections found:", collections)
    print()

    # Check each for products
    for col in collections:
        try:
            r = await c.get(f"https://homeu.ph/collections/{col}", headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                slugs = sorted(set(
                    m for m in re.findall(r'href=[\'"/]products/([^\'"\?]+)[\/"\']', r.text)
                    if "jpg" not in m and "webp" not in m and "png" not in m
                ))
                print(f"  {col}: {len(slugs)} products -> {slugs[:2]}")
            else:
                print(f"  {col}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {col}: {e}")

asyncio.run(main())
