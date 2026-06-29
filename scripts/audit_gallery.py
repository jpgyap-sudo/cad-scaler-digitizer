"""Audit: crawl table, check gallery, crawl sofa, check gallery again"""
import httpx, asyncio, json, os

async def crawl(url, category):
    r = await httpx.AsyncClient(timeout=180).post(
        "http://localhost:8001/api/crawl-to-dxf",
        json={"url": url, "category": category})
    d = r.json()
    dxf = d.get("dxf_file", "")
    views, polys = [], 0
    if dxf:
        import ezdxf
        fp = f"/tmp/cad_digitizer_outputs/{dxf}"
        if os.path.exists(fp):
            doc = ezdxf.readfile(fp)
            views = sorted([e.plain_text() for e in doc.modelspace() if e.dxftype() == "MTEXT" and "VIEW" in e.plain_text()])
            polys = sum(1 for e in doc.modelspace() if e.dxftype() == "LWPOLYLINE")
    return {
        "sk_source": d.get("skeleton_source"),
        "hero": d.get("hero_view_added"),
        "views": views,
        "polys": polys,
        "dxf": dxf,
    }

async def gallery():
    r = await httpx.AsyncClient(timeout=10).get("http://localhost:8001/api/silhouette/gallery")
    d = r.json()
    sil = d.get("silhouettes", {})
    return {k: {"name": v.get("product_name","?"), "svg_len": len(v.get("svg",""))} for k,v in sil.items()}

async def main():
    print("=== 1. Crawl TABLE ===")
    t = await crawl("https://homeu.ph/products/tangerie-dining-table", "table")
    print(f"  SK source: {t['sk_source']}, Hero: {t['hero']}, Views: {t['views']}")
    print(f"  Polylines: {t['polys']}")
    g = await gallery()
    print(f"  Gallery: {len(g)} items — {json.dumps(g)}")

    print("\n=== 2. Audit errors ===")
    # Check DXF has hero view
    if "HERO VIEW" not in str(t.get("views", [])):
        print("  !! HERO VIEW MISSING from DXF")
    if t.get("sk_source") != "gemini":
        print("  !! Gemini silhouette NOT generated")
    if t.get("hero") != True:
        print("  !! Hero view NOT added to DXF")
    print("  All checks passed" if t["hero"] and t["sk_source"] == "gemini" and "HERO VIEW" in str(t["views"]) else "  Some checks failed")

    print("\n=== 3. Crawl SOFA ===")
    s = await crawl("https://homeu.ph/products/glenn-modern-sofa", "sofa")
    print(f"  SK source: {s['sk_source']}, Hero: {s['hero']}, Views: {s['views']}")
    g2 = await gallery()
    print(f"  Gallery: {len(g2)} items — {json.dumps(g2)}")
    print(f"\n=== 4. Final audit ===")
    print(f"  Table:  views={len(t['views'])}, hero={t['hero']}, sk={t['sk_source']} {'✅' if t['hero'] else '❌'}")
    print(f"  Sofa:   views={len(s['views'])}, hero={s['hero']}, sk={s['sk_source']} {'✅' if s['hero'] else '❌'}")
    print(f"  Gallery accumulation: {len(g2)} types {'✅' if len(g2) >= 2 else '❌'}")

asyncio.run(main())
