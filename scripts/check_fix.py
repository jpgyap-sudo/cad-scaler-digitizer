import httpx, asyncio, ezdxf, os

async def test():
    items = [
        ("tangerie-dining-table", "table"),
        ("vivaldi-dining-table", "table"),
        ("glenn-modern-sofa", "sofa"),
        ("valenza-round-dining-table-modern-dining-table", "table"),
    ]
    for h, c in items:
        r = await httpx.AsyncClient(timeout=180).post("http://localhost:8001/api/crawl-to-dxf",
            json={"url": f"https://homeu.ph/products/{h}", "category": c})
        d = r.json()
        rd = d.get("resolved_dimensions", {})
        dxf = d.get("dxf_file", "")
        views = []
        if dxf:
            fp = f"/tmp/cad_digitizer_outputs/{dxf}"
            if os.path.exists(fp):
                doc = ezdxf.readfile(fp)
                views = [e.plain_text() for e in doc.modelspace() if e.dxftype() == "MTEXT" and "VIEW" in e.plain_text()]
        missing = [v for v in ["FRONT VIEW", "TOP VIEW", "SIDE VIEW"] if v not in str(views)]
        print(f"{h}: resolved={list(rd.keys())} views={views}  missing={missing}")

asyncio.run(test())
