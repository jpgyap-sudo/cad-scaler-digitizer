#!/usr/bin/env python3
"""
Accuracy Benchmark — Product Digitization Quality Report
==========================================================
Runs a batch of known HomeU products through the full pipeline and
measures accuracy of dimension extraction, DXF generation, and
validation scoring. Designed to run on VPS via cron.

Usage:
    python accuracy-benchmark.py [--json] [--csv] [--days N]
"""
import httpx, json, sys, os, asyncio, datetime, statistics

API = os.environ.get("PYTHON_WORKER_URL", "http://python-worker:8001")

# Ground truth for known products (manually verified dimensions from product pages)
GROUND_TRUTH = {
    "tangerie-dining-table": {"width_cm": 100, "depth_cm": 100, "overall_height_cm": 75},
    "vivaldi-dining-table": {"width_cm": 80, "depth_cm": 140, "overall_height_cm": 75},
    "glenn-modern-sofa": {"width_cm": 250, "depth_cm": 95, "overall_height_cm": 82},
    "evon-modern-bed": {"width_cm": 196, "depth_cm": 196, "overall_height_cm": 102},
    "valenza-round-dining-table-modern-dining-table": {"width_cm": 120, "depth_cm": 120, "overall_height_cm": 75},
    "bruno-modern-dining-chair": {"width_cm": 63, "depth_cm": 48, "overall_height_cm": 48},
    "fatima-modern-sofa": {"width_cm": 87, "depth_cm": 80, "overall_height_cm": 67},
    "mallow-sofa": {"width_cm": 210, "depth_cm": 80, "overall_height_cm": 72},
    "ember-modern-sofa": {"width_cm": 237, "depth_cm": 106, "overall_height_cm": 82},
    "aeris-console-table": {"width_cm": 120, "depth_cm": 40, "overall_height_cm": 75},
}

KNOWN_HANDLES = list(GROUND_TRUTH.keys())

async def digitize(url, cat):
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{API}/api/crawl-to-dxf", json={"url": url, "category": cat})
        return r.json()

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="CAD Digitizer Accuracy Benchmark")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    parser.add_argument("--days", type=int, default=7, help="Filter comparisons by days")
    args = parser.parse_args()

    results = []
    score_rows = []

    print(f"Running accuracy benchmark on {len(KNOWN_HANDLES)} known products...\n")

    for handle in KNOWN_HANDLES:
        gt = GROUND_TRUTH[handle]
        url = f"https://homeu.ph/products/{handle}"
        result = await digitize(url, "table" if "table" in handle else "sofa" if "sofa" in handle else "bed" if "bed" in handle else "chair")
        
        dims = result.get("page_dimensions", {}) or {}
        comp = result.get("comparison", {}) or {}
        detected = result.get("detected_dimensions", {}) or {}
        dxf = bool(result.get("dxf_file"))
        skeleton = bool(result.get("skeleton_svg"))
        
        # Compare detected vs ground truth
        errors = {}
        for dim_key, gt_val in gt.items():
            detected_val = dims.get(dim_key, 0) or detected.get(dim_key, 0)
            if detected_val and gt_val:
                dev_pct = abs(detected_val - gt_val) / gt_val * 100
                errors[dim_key] = {"expected": gt_val, "detected": round(detected_val, 1), "deviation_pct": round(dev_pct, 1)}
            else:
                errors[dim_key] = {"expected": gt_val, "detected": detected_val, "deviation_pct": None}
        
        avg_dev = statistics.mean([e["deviation_pct"] for e in errors.values() if e["deviation_pct"] is not None]) if any(e["deviation_pct"] is not None for e in errors.values()) else None
        overall = round(avg_dev, 1) if avg_dev else None
        
        results.append({
            "handle": handle,
            "dxf_generated": dxf,
            "skeleton_generated": skeleton,
            "ground_truth": gt,
            "extracted": dims,
            "errors": errors,
            "avg_deviation_pct": overall,
            "validation_score": comp.get("overall_score"),
            "edge_overlap": comp.get("edge_overlap_score"),
            "has_dimensions": bool(dims.get("width_cm")),
        })
        
        print(f"{handle:<50} gt={list(gt.values())[0]}cm "
              f"det={dims.get('width_cm', '?')}cm "
              f"dev={overall}% "
              f"score={comp.get('overall_score', 0):.2f} "
              f"dxf={'Y' if dxf else 'N'}")
    
    # Aggregated stats
    avg_scores = [r["validation_score"] for r in results if r["validation_score"]]
    avg_devs = [r["avg_deviation_pct"] for r in results if r["avg_deviation_pct"] is not None]
    with_dims = sum(1 for r in results if r["has_dimensions"])
    with_dxf = sum(1 for r in results if r["dxf_generated"])
    
    report = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "products_tested": len(results),
        "metrics": {
            "avg_validation_score": round(statistics.mean(avg_scores), 3) if avg_scores else 0,
            "avg_dim_deviation_pct": round(statistics.mean(avg_devs), 1) if avg_devs else None,
            "products_with_dimensions": f"{with_dims}/{len(results)}",
            "products_with_dxf": f"{with_dxf}/{len(results)}",
        },
        "results": results,
    }
    
    if args.json:
        print(json.dumps(report, indent=2))
    elif args.csv:
        import csv
        writer = csv.writer(sys.stdout)
        writer.writerow(["handle", "dxf", "skeleton", "gt_width", "det_width", "dev_pct", "score"])
        for r in results:
            gw = list(r["ground_truth"].values())[0] if r["ground_truth"] else ""
            dw = r["extracted"].get("width_cm", "") if r["extracted"] else ""
            writer.writerow([r["handle"], r["dxf_generated"], r["skeleton_generated"], gw, dw, r["avg_deviation_pct"], r["validation_score"]])
    else:
        print(f"\n{'='*60}")
        print(f"ACCURACY REPORT")
        print(f"{'='*60}")
        print(f"Products tested:     {len(results)}")
        print(f"Avg validation:      {report['metrics']['avg_validation_score']*100:.1f}%")
        if report['metrics']['avg_dim_deviation_pct']:
            print(f"Avg dim deviation:   {report['metrics']['avg_dim_deviation_pct']:.1f}%")
        print(f"With dimensions:     {report['metrics']['products_with_dimensions']}")
        print(f"With DXF:            {report['metrics']['products_with_dxf']}")
        print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
