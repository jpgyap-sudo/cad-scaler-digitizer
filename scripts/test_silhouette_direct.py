import asyncio, httpx, json

async def test():
    # Download an image
    r = await httpx.AsyncClient(timeout=30).get(
        "https://homeu.ph/cdn/shop/files/Tangerie.jpg?v=1736149321&width=1000",
        headers={"User-Agent": "Mozilla/5.0"})
    img_bytes = r.content
    print(f"Downloaded {len(img_bytes)} bytes")

    from app.agents.dxf_verifier_agent import generate_silhouette_svg
    result = await generate_silhouette_svg(
        image_data=img_bytes,
        furniture_type="rectangular_table",
        width_cm=100,
        height_cm=75)
    print(f"SVG: {len(result.get('svg',''))} chars")
    print(f"Coords: {len(result.get('dxf_coords',''))} chars")
    print(f"Error: {result.get('error')}")
    print(f"Has svg tag: {'<svg' in result.get('svg','')}")

asyncio.run(test())
