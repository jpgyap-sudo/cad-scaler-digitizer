/**
 * Bulk Import Script — Import DXF/PDF/Image files from the starter archive
 * into the CAD Reference Library.
 *
 * Usage:
 *   node scripts/bulk-import.mjs --dir /path/to/archives --manufacturer "jardan" --category "table"
 *
 * The script:
 *   1. Scans the directory recursively for .dxf, .pdf, .jpg/.png files
 *   2. Groups files by product name (directory name or filename prefix)
 *   3. Creates a ProductReference for each product
 *   4. Uploads each file as an asset to Spaces (or local fallback)
 *   5. Triggers DXF processing for any DXF assets
 *
 * Options:
 *   --dir         Directory to scan (required)
 *   --manufacturer Manufacturer name (required)
 *   --category    Category for all products (optional, default: "imported")
 *   --api-base    API base URL (default: http://localhost:4000)
 *   --dry-run     Just list what would be imported, don't POST
 */

const API_BASE = process.env.API_BASE || "http://localhost:4000";

function parseArgs() {
  const args = {};
  for (let i = 2; i < process.argv.length; i++) {
    const key = process.argv[i].replace(/^--/, "");
    const val = process.argv[++i];
    if (val !== undefined) args[key] = val;
  }
  return args;
}

const args = parseArgs();
const dryRun = args["dry-run"] === "true";

async function main() {
  // 1. Scan directory
  const dir = args.dir || process.cwd();
  const manufacturer = args.manufacturer;
  const category = args.category || "imported";

  if (!manufacturer) {
    console.error("Error: --manufacturer is required");
    console.error("Usage: node bulk-import.mjs --dir ./archives --manufacturer jardan --category table");
    process.exit(1);
  }

  // Find files grouped by product
  const fs = await import("fs");
  const path = await import("path");
  const files = fs.readdirSync(dir, { recursive: true }).filter(f => {
    const ext = path.extname(f).toLowerCase();
    return [".dxf", ".dwg", ".pdf", ".jpg", ".jpeg", ".png", ".svg", ".step", ".stp", ".iges", ".igs"].includes(ext);
  });

  if (files.length === 0) {
    console.log("No CAD/image files found in", dir);
    process.exit(0);
  }

  console.log(`Found ${files.length} files in ${dir}`);

  // Group by product (directory name, or filename prefix before _ or -)
  const products = new Map();
  for (const file of files) {
    const parent = path.dirname(file);
    const basename = path.basename(file);
    const slug = basename.replace(/\.\w+$/, "").replace(/[_-]\d+$/, "");
    const productName = parent === "." ? slug.replace(/[-_]/g, " ") : path.basename(parent);

    if (!products.has(productName)) {
      products.set(productName, { name: productName, files: [] });
    }
    products.get(productName).files.push({ path: file, name: basename, ext: path.extname(file).toLowerCase() });
  }

  console.log(`Grouped into ${products.size} products:`);
  for (const [name, product] of products) {
    console.log(`  ${name}: ${product.files.length} files`);
  }

  if (dryRun) {
    console.log("\nDry run complete. Pass --dry-run=false to import.");
    process.exit(0);
  }

  // 2. Import each product
  let created = 0;
  let uploaded = 0;
  let processed = 0;

  for (const [productName, product] of products) {
    const slug = productName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    // Create product
    try {
      const res = await fetch(`${API_BASE}/api/product-references`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manufacturer,
          productName,
          category,
          slug,
        }),
      });
      if (!res.ok) {
        const err = await res.text();
        console.error(`  ✗ Failed to create ${productName}: ${err}`);
        continue;
      }
      const productRef = await res.json();
      console.log(`  ✓ Created product: ${productRef.id}`);
      created++;

      // Upload each file
      for (const file of product.files) {
        const fullPath = path.join(dir, file.path);
        const buf = fs.readFileSync(fullPath);
        const assetType = [".dxf", ".dwg"].includes(file.ext) ? "DXF" :
          [".pdf"].includes(file.ext) ? "PDF" :
          [".jpg", ".jpeg", ".png"].includes(file.ext) ? "IMAGE" :
          [".svg"].includes(file.ext) ? "SVG" :
          [".step", ".stp"].includes(file.ext) ? "STEP" : "ASSET";

        const fd = new FormData();
        fd.append("assetType", assetType);
        fd.append("file", new Blob([buf]), file.name);

        const assetRes = await fetch(`${API_BASE}/api/product-references/${productRef.id}/assets`, {
          method: "POST",
          body: fd,
        });

        if (!assetRes.ok) {
          const err = await assetRes.text();
          console.error(`    ✗ Failed to upload ${file.name}: ${err}`);
          continue;
        }

        const asset = await assetRes.json();
        console.log(`    ✓ Uploaded ${file.name} → ${asset.cdnUrl || "local"}`);
        uploaded++;

        // Trigger DXF processing
        if (assetType === "DXF") {
          try {
            const procRes = await fetch(`${API_BASE}/api/product-references/${productRef.id}/process-dxf`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
            });
            if (procRes.ok) {
              const procResult = await procRes.json();
              console.log(`      ✓ Processed DXF: ${procResult.entity_count || 0} entities`);
              processed++;
            } else {
              console.error(`      ✗ Processing failed: ${await procRes.text()}`);
            }
          } catch (e) {
            console.error(`      ✗ Processing error: ${e.message}`);
          }
        }
      }
    } catch (e) {
      console.error(`  ✗ Error importing ${productName}: ${e.message}`);
    }
  }

  console.log("\n======= IMPORT SUMMARY =======");
  console.log(`Products created: ${created}`);
  console.log(`Files uploaded: ${uploaded}`);
  console.log(`DXF files processed: ${processed}`);
}

main().catch((e) => {
  console.error("Fatal:", e.message);
  process.exit(1);
});
