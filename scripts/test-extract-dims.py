"""Test dimension extraction from HomeU product page."""
import asyncio
from app.services.crawl_to_dxf import extract_dimensions_from_page

async def test():
    dims = await extract_dimensions_from_page("https://homeu.ph/products/tangerie-dining-table")
    print("Extracted dimensions:")
    for k, v in dims.items():
        print(f"  {k}: {v}")

asyncio.run(test())
