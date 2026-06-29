import httpx, asyncio
async def test():
    r = await httpx.AsyncClient(timeout=15).get("http://localhost:8001/api/silhouette/gallery")
    d = r.json()
    sil = d.get("silhouettes", {})
    print(f"Gallery count: {len(sil)}")
    for k, v in sil.items():
        print(f"  {k}: {v.get('product_name','?')} ({len(v.get('svg',''))} chars svg)")
asyncio.run(test())
