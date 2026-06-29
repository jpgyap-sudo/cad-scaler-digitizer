import httpx, asyncio

async def test():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = await httpx.AsyncClient(timeout=30, follow_redirects=True).get(
        "https://homeu.ph/cdn/shop/files/Tangerie.jpg?v=1736149321&width=1000",
        headers=headers)
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type')}")
    print(f"Length: {len(r.content)}")
    print(f"First 50 bytes: {r.content[:50]}")
    print(f"Content-Disposition: {r.headers.get('content-disposition', 'N/A')}")
    # Check if it's an image
    if r.content[:4] == b'\xff\xd8\xff\xe0' or r.content[:4] == b'\x89PNG':
        print("Actual image data confirmed")
    else:
        print("Not image data — possible redirect or error page")

asyncio.run(test())
