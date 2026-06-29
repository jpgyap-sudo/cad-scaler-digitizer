"""Iteration 2: Check polyline quality and SVG structure"""
import httpx, asyncio, json, os

async def test():
    c = httpx.AsyncClient(timeout=60)
    img_r = await c.get(
        "https://cdn.shopify.com/s/files/1/0559/7377/3476/files/tangeri_05-600x400_480x480.jpg?v=1663649294")
    img_bytes = img_r.content

    from app.agents.dxf_verifier_agent import generate_silhouette_svg
    result = await generate_silhouette_svg(img_bytes, "rectangular_table", 100, 75)
    svg = result.get("svg", "")
    views = result.get("views", {})
    props = result.get("estimated_proportions", {})

    print(f"SVG ({len(svg)} chars):")
    vbox = 'viewBox="0 0 900 300"'
    print(f"  Has 900x300 viewBox: {vbox in svg}")
    dv = 'data-view'
    print(f"  Has data-view attributes: {dv in svg}")
    dc = 'data-confidence'
    print(f"  Has data-confidence attributes: {dc in svg}")
    dash = 'stroke-dasharray'
    print(f"  Has dashed stroke for estimated: {dash in svg}")
    print(f"  Component count: {svg.count('data-name=')}")

    print(f"\nViews:")
    for v in ["front", "side", "top"]:
        pts = views.get(v, [])
        print(f"  {v}: {len(pts)} points")
        if pts:
            xs = [pts[i] for i in range(0, len(pts), 2)]
            ys = [pts[i+1] for i in range(0, len(pts), 2)]
            print(f"    x range: {min(xs):.0f}-{max(xs):.0f}, y range: {min(ys):.0f}-{max(ys):.0f}")

    print(f"\nEstimated proportions: {props}")

    # Check if DXF coords are usable
    dxf = result.get("dxf_coords", "[]")
    dxf_parsed = json.loads(dxf)
    print(f"\nDXF coords: {len(dxf_parsed)} total vertices")
    if dxf_parsed:
        xs = [p[0] for p in dxf_parsed if isinstance(p, list) and len(p) >= 2]
        ys = [p[1] for p in dxf_parsed if isinstance(p, list) and len(p) >= 2]
        print(f"  x range: {min(xs):.0f}-{max(xs):.0f}, y range: {min(ys):.0f}-{max(ys):.0f}")

    await c.aclose()

asyncio.run(test())
