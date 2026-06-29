import httpx, asyncio, json, os

async def check(handle, cat):
    r = await httpx.AsyncClient(timeout=120).post("http://localhost:8001/api/crawl-to-dxf",
        json={"url": f"https://homeu.ph/products/{handle}", "category": cat})
    d = r.json()
    rd = d.get("resolved_dimensions", {})
    pd = d.get("page_dimensions", {})
    dxf = d.get("dxf_file", "")
    views = []
    if dxf:
        import ezdxf
        fp = os.path.join("/tmp/cad_digitizer_outputs", dxf)
        if os.path.exists(fp):
            doc = ezdxf.readfile(fp)
            views = [e.plain_text() for e in doc.modelspace() if e.dxftype() == "MTEXT" and "VIEW" in e.plain_text()]
    print(f"Product: {handle}")
    print(f"  page_dims:  w={pd.get('width_cm','?')} d={pd.get('depth_cm',pd.get('length_cm','?'))} h={pd.get('overall_height_cm','?')}")
    print(f"  resolved:   w={rd.get('width_cm','?')} d={rd.get('depth_cm',rd.get('length_cm','?'))} h={rd.get('overall_height_cm','?')}")
    if pd.get("width_cm") and rd.get("width_cm"):
        w_dev = abs(rd["width_cm"] - pd["width_cm"]) / pd["width_cm"] * 100
        if w_dev > 15:
            print(f"  !! WRONG WIDTH: page={pd['width_cm']}cm resolved={rd['width_cm']}cm ({w_dev:.0f}% dev)")
    print(f"  views: {views}")
    errors = []
    for rv in ["FRONT VIEW", "TOP VIEW", "SIDE VIEW"]:
        if rv not in str(views):
            errors.append(rv)
    if errors:
        print(f"  !! MISSING VIEWS: {errors}")

async def main():
    items = [("tangerie-dining-table", "table"), ("vivaldi-dining-table", "table"),
             ("glenn-modern-sofa", "sofa"), ("evon-modern-bed", "bed"),
             ("valenza-round-dining-table-modern-dining-table", "table"),
             ("bruno-modern-dining-chair", "chair"),
             ("fatima-modern-sofa", "sofa"), ("mallow-sofa", "sofa"),
             ("ember-modern-sofa", "sofa"), ("aeris-console-table", "table")]
    for h, c in items:
        await check(h, c)

asyncio.run(main())
