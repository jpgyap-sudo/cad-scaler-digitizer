"""Crawl a product and verify DNA enrichment + gallery populating"""
import httpx, asyncio, json

async def test():
    c = httpx.AsyncClient(timeout=180)
    r = await c.post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": "https://homeu.ph/products/glenn-modern-sofa", "category": "sofa"})
    d = r.json()
    print(f"SK source: {d.get('skeleton_source')}")
    print(f"Hero: {d.get('hero_view_added')}")

    # Check DNA files exist
    import os
    for path in ["/app/resources/product_catalog/product_dna.json",
                  "/app/resources/product_catalog/visual_dna_index.json"]:
        exists = os.path.exists(path)
        print(f"DNA ({os.path.basename(path)}): {'EXISTS' if exists else 'MISSING'}")
        if exists:
            data = json.loads(open(path).read())
            if "glenn-modern-sofa" in data or path.endswith("index.json"):
                print(f"  Contains glenn-modern-sofa? {'glenn-modern-sofa' in str(data)}")
                print(f"  Keys: {list(data.keys())[:5]}")

    # Test the classifier now has data
    from app.backend.product_classifier import classify_product
    result = classify_product("modern sofa with cushions", ["rectangle"], ["seat", "backrest"])
    print(f"\nClassifier test:")
    print(f"  Family: {result.get('family')} (conf={result.get('family_confidence')})")
    print(f"  Subtypes: {len(result.get('subtypes', []))}")
    print(f"  Matches: {len(result.get('matches', []))}")
    for m in result.get('matches', [])[:2]:
        print(f"    {m.get('family')} score={m.get('score')}")

    await c.aclose()

asyncio.run(test())
