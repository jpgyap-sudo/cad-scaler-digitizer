import asyncio, httpx

async def test():
    c = httpx.AsyncClient(timeout=60)
    r = await c.get("https://cdn.shopify.com/s/files/1/0559/7377/3476/files/tangeri_05-600x400_480x480.jpg?v=1663649294")
    
    from app.agents.dxf_verifier_agent import generate_silhouette_svg
    res = await generate_silhouette_svg(r.content, "rectangular_table", 100, 75)
    
    svg = res.get("svg", "")
    views = res.get("views", {})
    print(f"SVG: {len(svg)} chars")
    print(f"Has 1200x300: {'1200 300' in svg}")
    for v in ["front", "side", "top", "isometric"]:
        pts = views.get(v, [])
        n = len(pts) // 2
        print(f"  {v}: {n} pts" if n > 0 else f"  {v}: EMPTY")
    print(f"Proportions: {res.get('estimated_proportions')}")
    print("---SVG START---")
    print(svg[:500])
    print("---SVG END---")
    await c.aclose()

asyncio.run(test())
