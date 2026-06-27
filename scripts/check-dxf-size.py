"""Check the bounding box of the most recent digitized DXF."""
import ezdxf, glob, os, math

outputs = "/tmp/cad_digitizer_outputs"
files = sorted(glob.glob(os.path.join(outputs, "*_digitized.dxf")), key=os.path.getmtime, reverse=True)

for fpath in files[:3]:
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    for e in msp:
        try:
            if e.dxftype() == "LINE":
                s, en = e.dxf.start, e.dxf.end
                minx = min(minx, s.x, en.x)
                maxx = max(maxx, s.x, en.x)
                miny = min(miny, s.y, en.y)
                maxy = max(maxy, s.y, en.y)
            elif e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                pts = e.get_points() if hasattr(e, "get_points") else []
                for p in pts:
                    minx = min(minx, p[0]); maxx = max(maxx, p[0])
                    miny = min(miny, p[1]); maxy = max(maxy, p[1])
            elif e.dxftype() == "CIRCLE":
                cx, cy = e.dxf.center.x, e.dxf.center.y
                r = float(e.dxf.radius)
                minx = min(minx, cx - r); maxx = max(maxx, cx + r)
                miny = min(miny, cy - r); maxy = max(maxy, cy + r)
        except: pass
    
    name = os.path.basename(fpath)
    w = maxx - minx if not math.isinf(minx) else 0
    h = maxy - miny if not math.isinf(miny) else 0
    print(f"{name}: {int(w)} x {int(h)} units, {sum(1 for _ in msp)} entities")
