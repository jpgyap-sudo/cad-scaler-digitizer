"""
Parse cached Shopify product-search JSON pages (tag:furniture) into
DNA-enrichment-ready entries, skipping handles already in product_dna.json.

Run locally; writes a JSON list to scripts/_new_dna_entries.json for the
next step (calling enrich_dna_from_crawl() on the VPS).
"""
import json
import re
from pathlib import Path

SCRATCHPAD = Path(r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Desktop-autocad-scaler-digitizer-upgraded\70f38588-b33e-41f9-9171-2ef7d8b86810\scratchpad")
EXISTING_DNA = Path(__file__).resolve().parents[1] / "backend-python" / "resources" / "product_catalog" / "product_dna.json"
OUT_PATH = Path(__file__).resolve().parent / "_new_dna_entries.json"

# Keyword -> furniture_type (KNOWN_TYPES taxonomy), checked in order
TYPE_RULES = [
    (("round dining table", "round table"), "round_pedestal_table"),
    (("oval", "travertine") , None),  # handled via shape check below
    (("dining table", "diningtable"), "rectangular_table"),
    (("coffee table", "coffeetable"), "coffee_table"),
    (("side table", "sidetable", "nightstand", "bedside"), "side_table"),
    (("console table", "console"), "console_table"),
    (("dining chair", "diningchair"), "dining_chair"),
    (("lounge chair",), "lounge_chair"),
    (("armchair", "arm chair", "accent chair"), "armchair_lounge"),
    (("sectional",), "sofa"),
    (("sofa",), "sofa"),
    (("bench",), "bench_chaise"),
    (("ottoman", "pouf"), "ottoman_pouf"),
    (("bed",), "bed"),
    (("tv cabinet", "tv console", "television cabinet"), "tv_console"),
    (("cabinet", "sideboard"), "cabinet"),
    (("bar stool",), "bar_stool"),
    (("wardrobe",), "wardrobe"),
]

DIM_PATTERNS = [
    # "1960(W)x2300(L)x1020(H)mm" or "1600(W) x 2260(L) x 1040(H)mm"
    re.compile(r"(\d+)\s*\(W\)\s*x\s*(\d+)\s*\(L\)\s*x\s*(\d+)\s*\(H\)\s*mm", re.I),
    # "90x140(L)x75(H)cm" or "100cm(W) x 200cm (L) x 75cm (H)"
    re.compile(r"(\d+)\s*(?:cm)?\s*\(?W?\)?\s*x\s*(\d+)\s*(?:cm)?\s*\(L\)\s*x\s*(\d+)\s*(?:cm)?\s*\(H\)", re.I),
    # "2480(L) x 1130(W) x 820(H)mm"
    re.compile(r"(\d+)\(L\)\s*x\s*(\d+)\(W\)\s*x\s*(\d+)\(H\)\s*mm", re.I),
    # generic "1200x1200xH350mm" or "1200X2600mm"
    re.compile(r"(\d+)\s*[xX]\s*(\d+)\s*[xX]?[Hh]?(\d+)?\s*mm", re.I),
    # "2370x1060xH820mm"
    re.compile(r"(\d+)x(\d+)x[Hh](\d+)mm", re.I),
    # plain "1800 x 900mm" (2D, no height in this token)
    re.compile(r"(\d+)\s*x\s*(\d+)\s*mm", re.I),
    # diameter: "⌀120cm" / "⌀140cm(W) x 75cm (H)"
    re.compile(r"⌀\s*(\d+)\s*cm.*?(\d+)\s*cm\s*\(H\)", re.I),
]


def guess_ftype(title: str, tags: list) -> str:
    text = (title + " " + " ".join(tags)).lower()
    is_round = "round" in text or "⌀" in title
    is_oval = "oval" in text
    for keys, ftype in TYPE_RULES:
        if any(k in text for k in keys):
            if ftype is None:
                continue
            if ftype == "rectangular_table" and is_round:
                return "round_pedestal_table"
            if ftype == "rectangular_table" and is_oval:
                return "oval_pedestal_table"
            return ftype
    if is_round and "table" in text:
        return "round_pedestal_table"
    if is_oval and "table" in text:
        return "oval_pedestal_table"
    return ""


def parse_dims_from_variant(title: str):
    for pat in DIM_PATTERNS:
        m = pat.search(title)
        if m:
            vals = [float(g) for g in m.groups() if g]
            if len(vals) >= 2:
                # values are in mm if pattern had "mm", else already cm
                if "mm" in title.lower() or "⌀" not in pat.pattern:
                    pass
                return vals
    return None


def to_cm(vals, title: str):
    """Convert parsed dim values to cm based on whether source had mm/cm units."""
    if not vals:
        return None
    unit_mm = bool(re.search(r"\bmm\b", title, re.I))
    scale = 0.1 if unit_mm else 1.0
    # Heuristic: values > 400 are almost certainly mm even if not labeled
    if not unit_mm and max(vals) > 400:
        scale = 0.1
    return [round(v * scale, 1) for v in vals]


def main():
    existing = {}
    if EXISTING_DNA.exists():
        existing = json.loads(EXISTING_DNA.read_text(encoding="utf-8"))
    existing_handles = set(existing.keys())
    print(f"Existing DNA handles: {len(existing_handles)}")

    products = []
    for i in range(1, 7):
        p = SCRATCHPAD / f"shopify_furniture_p{i}.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        edges = data.get("data", {}).get("products", {}).get("edges", [])
        for e in edges:
            products.append(e["node"])
    print(f"Total products parsed from pages: {len(products)}")

    seen_handles = set()
    new_entries = []
    skipped_existing = 0
    skipped_no_type = 0
    skipped_no_dims = 0

    for p in products:
        handle = p.get("handle", "")
        if not handle or handle in seen_handles:
            continue
        seen_handles.add(handle)
        if handle in existing_handles:
            skipped_existing += 1
            continue

        title = p.get("title", "")
        tags = p.get("tags", [])
        ftype = guess_ftype(title, tags)
        if not ftype:
            skipped_no_type += 1
            continue

        # Try every variant title until we find usable dims
        dims_cm = None
        for v in p.get("variants", {}).get("edges", []):
            vt = v.get("node", {}).get("title", "") or ""
            raw = parse_dims_from_variant(vt)
            dims_cm = to_cm(raw, vt)
            if dims_cm and len(dims_cm) >= 2:
                break
        # Also try cf-size-* tags as a fallback dimension source
        if not dims_cm:
            for tag in tags:
                m = re.search(r"(\d+)x(\d+)x?h?(\d+)?", tag.replace("cf-size-", ""), re.I)
                if m:
                    vals = [float(g) for g in m.groups() if g]
                    if len(vals) >= 2:
                        dims_cm = to_cm(vals, tag)
                        break
        # Last resort: scan the product description text - many list a
        # "Dimension: WxDxHmm" line that doesn't make it into variant
        # titles (single-variant products with "Default Title").
        if not dims_cm:
            desc = p.get("description", "") or ""
            for pat in DIM_PATTERNS:
                m = pat.search(desc)
                if m:
                    vals = [float(g) for g in m.groups() if g]
                    if len(vals) >= 2:
                        dims_cm = to_cm(vals, desc)
                        break
        if not dims_cm or len(dims_cm) < 2:
            skipped_no_dims += 1
            continue

        w, d = dims_cm[0], dims_cm[1]
        h = dims_cm[2] if len(dims_cm) > 2 else 75.0
        family = ftype.split("_")[0] if "_" in ftype else ftype

        new_entries.append({
            "handle": handle,
            "furniture_type": ftype,
            "family": family,
            "dimensions": {"width_cm": w, "depth_cm": d, "overall_height_cm": h},
        })

    print(f"Skipped (already exists): {skipped_existing}")
    print(f"Skipped (no type guess): {skipped_no_type}")
    print(f"Skipped (no parseable dims): {skipped_no_dims}")
    print(f"New entries to add: {len(new_entries)}")

    OUT_PATH.write_text(json.dumps(new_entries, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
