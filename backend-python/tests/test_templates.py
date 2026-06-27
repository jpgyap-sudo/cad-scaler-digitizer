"""Tests for TemplateGraphLoader and TemplateResolver."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.resource_engine.template_loader import TemplateGraphLoader
from app.resource_engine.template_resolver import TemplateResolver, PRODUCT_TYPE_MAP, DIMENSION_CM_TO_MM_MAP

PASS = 0
FAIL = 0
TOTAL = 0


def check(name, condition):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def test_loader():
    loader = TemplateGraphLoader().load()
    check("loads 18 templates", loader.count == 18)

    # Indexing
    tables = loader.find_by_family("table")
    check("table family count", len(tables) == 7)

    cabinets = loader.find_by_family("cabinet")
    check("cabinet family count", len(cabinets) == 4)

    seating = loader.find_by_family("seating")
    check("seating family count", len(seating) == 3)

    # Lookup by ID
    tpl = loader.get("bed.standard.v1")
    check("get by id", tpl is not None and tpl["name"] == "Standard platform bed")

    # Lookup by product_type
    matches = loader.find_by_product_type("rectangular_table")
    check("find_by_product_type rectangular_table", len(matches) == 1)

    # get_default
    default = loader.get_default("sofa")
    check("get_default sofa", default is not None and default["name"] == "Standard sofa / couch")

    # get_parameter
    param = loader.get_parameter("chair.standard.v1", "seat_height_mm")
    check("get_parameter seat_height_mm", param is not None and param["default"] == 450)

    # Missing lookup
    missing = loader.get("nonexistent.v1")
    check("get nonexistent returns None", missing is None)

    # resolve_and_override
    resolved = loader.resolve_and_override("round_pedestal_table", {"diameter_mm": 1200.0})
    check("resolve_and_override", resolved is not None)
    if resolved:
        check("  diameter overridden", resolved["resolved_parameters"].get("diameter_mm") == 1200)

    return loader


def test_resolver(loader):
    resolver = TemplateResolver(loader)

    # Resolve with dimension overrides
    r = resolver.resolve("round_pedestal_table", {"top_diameter_cm": 120.0, "overall_height_cm": 75.0})
    check("resolve round table", r["template"]["name"] == "Round table with single pedestal")
    rp = r["resolved_parameters"]
    check("  diameter_mm = 1200 (from 120cm)", rp.get("diameter_mm") == 1200)
    check("  height_mm = 750 (from 75cm)", rp.get("height_mm") == 750)

    # Resolve rectangular table
    r2 = resolver.resolve("rectangular_table", {"width_cm": 180, "depth_cm": 90, "overall_height_cm": 75})
    check("resolve rect table", r2["template"]["name"] == "Rectangular table with four legs")
    check("  length_mm = 1800", r2["resolved_parameters"].get("length_mm") == 1800)

    # Constraint evaluation: bed with valid dims
    r3 = resolver.resolve("bed", {"width_cm": 200, "depth_cm": 190})
    bed_ok = [c for c in r3["constraints"] if c["id"] == "bed_min_size" and c["passed"]]
    check("bed_min_size passes with valid dims", len(bed_ok) == 1)

    # Constraint evaluation: bed with too-small dims
    r4 = resolver.resolve("bed", {"width_cm": 150, "depth_cm": 100})
    bed_fail = [c for c in r4["constraints"] if c["id"] == "bed_min_size" and not c["passed"]]
    check("bed_min_size fails with tiny dims", len(bed_fail) == 1)

    # Constraint: height range — 99cm * 10 = 990mm should FAIL 720<=height_mm<=780
    r5 = resolver.resolve("round_pedestal_table", {"top_diameter_cm": 100, "overall_height_cm": 99})
    height_fail = [c for c in r5["constraints"] if c["id"] == "height_range" and not c["passed"]]
    check("height_range fails with height_mm=990 (>780mm max)", len(height_fail) == 1)

    # Desk: depth constraint
    r6 = resolver.resolve("office_desk", {"length_cm": 140, "depth_cm": 40})  # too shallow
    depth_fail = [c for c in r6["constraints"] if c["id"] == "depth_min" and not c["passed"]]
    check("office_desk depth_min fires at 40cm (needs >= 50cm)", len(depth_fail) == 1)

    # Resolve all
    summaries = resolver.resolve_all()
    check("resolve_all returns 18 summaries", len(summaries) == 18)

    # Required views
    r7 = resolver.resolve("sofa", {"width_cm": 220})
    views = r7.get("component_views", [])
    check("sofa has required views", len(views) >= 3)


def test_product_type_mapping():
    # Every template product_type should have an entry in PRODUCT_TYPE_MAP
    actual_pts = {"rectangular_table", "round_pedestal_table", "oval_pedestal_table",
                  "console_table", "coffee_table", "side_table", "office_desk",
                  "sideboard", "tv_console", "nightstand", "wardrobe",
                  "bed", "bed_headboard", "sofa", "lounge_chair", "dining_chair",
                  "reception_counter", "asymmetric_pedestal_table"}
    for pt in actual_pts:
        check(f"PRODUCT_TYPE_MAP covers {pt}", pt in PRODUCT_TYPE_MAP.values())

    mapped_pts = set(PRODUCT_TYPE_MAP.values())
    for pt in actual_pts:
        check(f"  {pt} mapped via some normal form", pt in mapped_pts)

    # Every template product_type has a dimension map
    for pt in actual_pts:
        check(f"DIMENSION_CM_TO_MM_MAP covers {pt}", pt in DIMENSION_CM_TO_MM_MAP)


def test_parameter_defaults():
    loader = TemplateGraphLoader().load()
    for tpl in loader.list_all():
        for p in tpl.get("parameters", []):
            check(f"{tpl['id']}.{p['name']} has default", "default" in p)
            check(f"{tpl['id']}.{p['name']} has min_value", "min_value" in p)
            check(f"{tpl['id']}.{p['name']} has max_value", "max_value" in p)
            check(f"  default is number", isinstance(p["default"], (int, float)))
            check(f"  min <= default", p.get("min_value", 0) <= p["default"])
            check(f"  default <= max", p["default"] <= p.get("max_value", 99999))


if __name__ == "__main__":
    print("=" * 60)
    print("Template Engine Tests")
    print("=" * 60)

    test_parameter_defaults()

    loader = test_loader()
    test_resolver(loader)
    test_product_type_mapping()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS}/{TOTAL} passed, {FAIL} failed")
    print(f"{'=' * 60}")
    sys.exit(0 if FAIL == 0 else 1)
