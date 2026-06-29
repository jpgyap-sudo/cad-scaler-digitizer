"""Debug: run the exact same generate_silhouette_svg call the crawl would make"""
import httpx, asyncio, json

async def test():
    # Simulate what crawl_to_dxf does
    c = httpx.AsyncClient(timeout=60)
    img_r = await c.get(
        "https://cdn.shopify.com/s/files/1/0559/7377/3476/files/tangeri_05-600x400_480x480.jpg?v=1663649294")
    img_bytes = img_r.content
    print(f"Image: {len(img_bytes)} bytes")

    from app.agents.dxf_verifier_agent import generate_silhouette_svg
    result = await generate_silhouette_svg(
        image_data=img_bytes,
        furniture_type="rectangular_table",
        width_cm=100,
        height_cm=75)
    print(f"Result keys: {list(result.keys())}")
    print(f"SVG: {len(result.get('svg',''))} chars")
    print(f"Error: {result.get('error')}")
    print(f"Has svg: {'<svg' in result.get('svg','')}")
    
    # This is the check the crawl uses
    if result.get("svg"):
        print("Crawl would use Gemini silhouette ✅")
    else:
        print("Crawl would use geometric fallback ❌")
    await c.aclose()

asyncio.run(test())
