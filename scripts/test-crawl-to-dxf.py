"""Test crawl-to-dxf pipeline on a real Jardan product."""
import asyncio
from app.services.crawl_to_dxf import crawl_and_digitize

async def test():
    result = await crawl_and_digitize(
        page_url="https://www.jardan.com.au/products/nk198",
        furniture_type="sofa",
    )
    print("Status:", result.get("status"))
    print("Image:", (result.get("image_url") or "")[:100])
    print("DXF:", result.get("dxf_file"))
    print("Dims:", result.get("detected_dimensions"))
    hc = result.get("hallucination_check")
    if hc:
        print("Hallucination score:", hc.get("overall_score"))
        for k, v in hc.get("verdicts", {}).items():
            print(f"  {k}: {v.get('verdict')} conf={v.get('confidence')}")
    if result.get("error"):
        print("Error:", result["error"])

asyncio.run(test())
