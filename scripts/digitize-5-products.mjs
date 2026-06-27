/**
 * Digitize 5 product photos and validate against reference CAD.
 *
 * Pipeline:
 * 1. Download product hero image from Spaces CDN
 * 2. POST to /api/digitize - detects dimensions, furniture type
 * 3. POST to /api/validate/product - compares against range DXF
 * 4. Report scores for each product
 */
const PY_BASE = "http://python-worker:8001";

// 5 best product hero images from our Spaces crawl
const PRODUCTS = [
  {
    name: "Nook Sofa (NK198)",
    imageUrl: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/furniture/jardan-nook/images/NK198_Darcy_Iron_Timber_Ash_1000.png",
    refGeometry: { bbox: { width: 218, height: 86 }, counts: { entityCount: 1218 }, entities: [] },
    type: "sofa",
  },
  {
    name: "Boulder Rug (BOU2030)",
    imageUrl: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/furniture/jardan-boulder-rug/images/BOU2030_Boulder_Acorn_1000.png",
    refGeometry: { bbox: { width: 200, height: 290 }, counts: { entityCount: 50 }, entities: [] },
    type: "rug",
  },
  {
    name: "Cooper Sofa (CP180)",
    imageUrl: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/furniture/jardan-cooper/images/CP180_Oak_Raw_1000.png",
    refGeometry: { bbox: { width: 220, height: 85 }, counts: { entityCount: 800 }, entities: [] },
    type: "sofa",
  },
  {
    name: "Cleo Sofa (CE196)",
    imageUrl: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/furniture/jardan-cleo/images/CE196_Stone_Washed_Linen_Cloud_1000.png",
    refGeometry: { bbox: { width: 200, height: 82 }, counts: { entityCount: 600 }, entities: [] },
    type: "sofa",
  },
  {
    name: "Miller Sofa (ML290)",
    imageUrl: "https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library/raw/jardan/furniture/jardan-miller/images/ML290_Luna_Eggshell_Steel_Oyster_1000.png",
    refGeometry: { bbox: { width: 210, height: 84 }, counts: { entityCount: 700 }, entities: [] },
    type: "sofa",
  },
];

async function downloadImage(url) {
  const res = await fetch(url, { signal: AbortSignal.timeout(30000) });
  if (!res.ok) throw new Error("HTTP " + res.status);
  const buf = Buffer.from(await res.arrayBuffer());
  const filename = url.split("/").pop().split("?")[0] || "product.png";
  return { buf, filename, size: buf.length };
}

async function digitizeProduct(image, furnitureType) {
  const fd = new FormData();
  fd.append("file", new Blob([image.buf], { type: "image/png" }), image.filename);
  fd.append("furniture_type", furnitureType);

  const res = await fetch(PY_BASE + "/api/digitize", {
    method: "POST",
    body: fd,
    signal: AbortSignal.timeout(60000),
  });
  if (!res.ok) {
    const err = await res.text();
    return { status: "failed", error: err.slice(0, 200) };
  }
  return await res.json();
}

async function validateAgainstCAD(productId, detectedDims, refGeo, type) {
  const res = await fetch(PY_BASE + "/api/validate/product", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: productId,
      furniture_type: type,
      detected_dims: detectedDims,
      reference_geometry: refGeo,
    }),
  });
  if (!res.ok) return { status: "failed" };
  return await res.json();
}

async function main() {
  console.log("=== DIGITIZING 5 PRODUCTS ===\n");

  for (let i = 0; i < PRODUCTS.length; i++) {
    const product = PRODUCTS[i];
    console.log((i + 1) + ". " + product.name);
    console.log("   Image: " + product.imageUrl);

    try {
      // Step 1: Download image
      const image = await downloadImage(product.imageUrl);
      console.log("   Downloaded: " + image.size + " bytes");

      // Step 2: Digitize
      const digitized = await digitizeProduct(image, product.type);
      if (digitized.status === "failed") {
        console.log("   DIGITIZE FAILED: " + (digitized.error || "unknown"));
        console.log("");
        continue;
      }

      // Extract detected dimensions
      const detectedDims = {};
      if (digitized.detected_width_cm) detectedDims.width_cm = parseFloat(digitized.detected_width_cm);
      if (digitized.detected_height_cm) detectedDims.overall_height_cm = parseFloat(digitized.detected_height_cm);
      if (digitized.real_width_cm) detectedDims.width_cm = parseFloat(digitized.real_width_cm);
      if (digitized.real_height_cm) detectedDims.overall_height_cm = parseFloat(digitized.real_height_cm);

      // Also check for dimensions in the response
      if (digitized.dimensions) {
        if (digitized.dimensions.width_cm) detectedDims.width_cm = digitized.dimensions.width_cm;
        if (digitized.dimensions.height_cm) detectedDims.overall_height_cm = digitized.dimensions.height_cm;
      }

      console.log("   Detected dims: " + JSON.stringify(detectedDims));

      // Step 3: Validate against reference CAD
      if (Object.keys(detectedDims).length > 0) {
        const validation = await validateAgainstCAD(
          "product-" + (i + 1),
          detectedDims,
          product.refGeometry,
          product.type
        );
        console.log("   Validation score: " + (validation.overall_score || "N/A"));
        console.log("   Passed: " + (validation.passed || false));
        if (validation.dimensions) {
          for (const d of validation.dimensions) {
            console.log("     " + d.dimension_key + ": " + d.detected_cm + "cm vs ref " + d.reference_cm + "cm (dev: " + d.deviation_pct + "%)");
          }
        }
      } else {
        console.log("   No dimensions detected - cannot validate");
        console.log("   Full response: " + JSON.stringify(digitized).slice(0, 300));
      }

    } catch (e) {
      console.log("   ERROR: " + e.message);
    }
    console.log("");
  }

  console.log("=== DIGITIZE COMPLETE ===");
}

main().catch(e => console.error("FATAL:", e.message));
