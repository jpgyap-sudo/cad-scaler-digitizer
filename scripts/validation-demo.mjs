/**
 * Validation Demo — End-to-end photo vs CAD validation pipeline
 *
 * 1. Load a crawled product photo (CDN URL from Spaces)
 * 2. Load the corresponding range DXF geometry from Qdrant
 * 3. Run validation: compare simulated detections vs CAD
 * 4. Show score, pass/fail, per-dimension comparison
 * 5. Export ML training record
 */
const API_BASE = "http://localhost:4000";
const PY_BASE = "http://python-worker:8001";
const QDRANT_BASE = "http://qdrant:6333";

async function main() {
  console.log("=== VALIDATION PIPELINE DEMO ===\n");

  // 1. List all DXF ranges in Qdrant
  console.log("1. DXF Ranges in Qdrant:");
  const qr = await fetch(QDRANT_BASE + "/collections/cad_geometry");
  const q = await qr.json();
  const points = q.result.points_count;
  console.log("   Total indexed geometries: " + points);

  // Scroll through Qdrant to see each range
  const scroll = await fetch(QDRANT_BASE + "/collections/cad_geometry/points/scroll", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit: 10, with_payload: true }),
  });
  const scrollData = await scroll.json();
  if (scrollData.result) {
    for (const pt of scrollData.result) {
      console.log("   - " + (pt.payload?.product_id || "?") + " (score: " + pt.score + ")");
    }
  }

  // 2. Available product photos by category
  console.log("\n2. Product photos available by category:");
  const cats = [];
  // Hardcoded from our Space inventory
  const categories = [
    { cat: "sofa", products: ["nook", "jardan-nook", "jardan-banjo"] },
    { cat: "table", products: ["arden-range", "bon-range", "lola-range", "pia-range", "oio-table", "au120", "wattle-table"] },
    { cat: "rug", products: ["bou2030-boulder-rug"] },
    { cat: "furniture", products: ["ml290-miller", "nk-modular-a", "nk-modular-b"] },
  ];
  for (const c of categories) {
    console.log("   " + c.cat + ": " + c.products.length + " products");
  }

  // 3. Run validation: Arden Range CAD vs sample detected dims
  console.log("\n3. Validate: Arden Range DXF (1,218 entities)");
  const validationResult = await fetch(PY_BASE + "/api/validate/product", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: "jardan-arden-range",
      furniture_type: "table",
      detected_dims: {
        width_cm: 220,
        overall_height_cm: 78,
      },
      reference_geometry: {
        bbox: { width: 218, height: 76 },
        counts: { entityCount: 1218 },
        entities: [],
      },
    }),
  });
  const vr = await validationResult.json();
  console.log("   Overall Score: " + vr.overall_score);
  console.log("   Passed: " + vr.passed);
  console.log("   Dimensions:");
  if (vr.dimensions) {
    for (const d of vr.dimensions) {
      console.log("     " + d.dimension_key + ": detected=" + d.detected_cm + "cm ref=" + d.reference_cm + "cm dev=" + d.deviation_pct + "% " + (d.passed ? "PASS" : "FAIL"));
    }
  }

  // 4. Validate Bon Range (2,143 entities)
  console.log("\n4. Validate: Bon Range DXF (2,143 entities)");
  const vr2 = await fetch(PY_BASE + "/api/validate/product", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: "jardan-bon-range",
      furniture_type: "table",
      detected_dims: {
        width_cm: 180,
        overall_height_cm: 74,
        depth_cm: 90,
      },
      reference_geometry: {
        bbox: { width: 182, height: 73 },
        counts: { entityCount: 2143 },
        entities: [],
      },
    }),
  });
  const vr2d = await vr2.json();
  console.log("   Overall Score: " + vr2d.overall_score);
  console.log("   Passed: " + vr2d.passed);
  if (vr2d.dimensions) {
    for (const d of vr2d.dimensions) {
      console.log("     " + d.dimension_key + ": detected=" + d.detected_cm + "cm ref=" + d.reference_cm + "cm dev=" + d.deviation_pct + "% " + (d.passed ? "PASS" : "FAIL"));
    }
  }

  // 5. Batch validation and export training data
  console.log("\n5. Export ML Training Data");
  const batchResult = await fetch(PY_BASE + "/api/validate/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      min_score: 0.7,
      export_path: "/tmp/training-data.jsonl",
      families: [
        {
          product_id: "jardan-arden-range",
          furniture_type: "table",
          detected_dims: { width_cm: 220, overall_height_cm: 78 },
          reference_geometry: { bbox: { width: 218, height: 76 }, counts: { entityCount: 1218 }, entities: [] },
          image_url: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/table/arden-range/images/sample.jpg",
          dxf_url: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/table/arden-range/cad/ARDEN_RANGE.dxf",
        },
        {
          product_id: "jardan-bon-range",
          furniture_type: "table",
          detected_dims: { width_cm: 180, overall_height_cm: 74 },
          reference_geometry: { bbox: { width: 182, height: 73 }, counts: { entityCount: 2143 }, entities: [] },
          image_url: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/table/bon-range/images/sample.jpg",
          dxf_url: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/table/bon-range/cad/BON-RANGE.dxf",
        },
        {
          product_id: "jardan-lola-range",
          furniture_type: "table",
          detected_dims: { width_cm: 160, overall_height_cm: 76 },
          reference_geometry: { bbox: { width: 158, height: 75 }, counts: { entityCount: 265 }, entities: [] },
          image_url: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/table/lola-range/images/sample.jpg",
          dxf_url: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/table/lola-range/cad/LOLA-RANGE.dxf",
        },
      ],
    }),
  });
  const br = await batchResult.json();
  console.log("   Summary: " + JSON.stringify(br.summary));
  console.log("\n   Sample training records:");
  if (br.samples) {
    for (const s of br.samples) {
      console.log("     " + s.product_id + ": score=" + s.validation.overall_score + " " + (s.validation.passed ? "PASS" : "FAIL"));
    }
  }

  // 6. Check reference ratio solver
  console.log("\n6. Reference Ratio Solver — missing dimensions");
  const solverTest = await fetch(PY_BASE + "/api/reference-ratios/round_pedestal_table");
  // This is a local calculation using the ratio_solver module
  console.log("   (Built into validation layer — run from Python worker directly)");

  console.log("\n=== VALIDATION PIPELINE READY ===");
  console.log("Next: Import more photos + DXF pairs to grow the training dataset");
}

main().catch(e => console.error("FATAL:", e.message));
