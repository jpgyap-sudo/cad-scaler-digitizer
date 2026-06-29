"""Test the new multi-view Gemini prompt"""
import httpx, asyncio, json, os

async def test():
    # Download a product image
    c = httpx.AsyncClient(timeout=60)
    img_r = await c.get(
        "https://cdn.shopify.com/s/files/1/0559/7377/3476/files/tangeri_05-600x400_480x480.jpg?v=1663649294")
    img_bytes = img_r.content
    print(f"Image: {len(img_bytes)} bytes")

    from app.agents.dxf_verifier_agent import generate_silhouette_svg
    result = await generate_silhouette_svg(img_bytes, "rectangular_table", 100, 75)
    print(f"SVG: {len(result.get('svg',''))} chars")
    views = result.get('views', {})
    print(f"Views: front={len(views.get('front',[]))}pts, side={len(views.get('side',[]))}pts, top={len(views.get('top',[]))}pts")
    print(f"Estimated proportions: {result.get('estimated_proportions')}")
    print(f"Has svg tag: {'<svg' in result.get('svg','')}")
    await c.aclose()

asyncio.run(test())
