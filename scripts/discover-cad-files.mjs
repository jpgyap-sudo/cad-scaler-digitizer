/**
 * Discover all Jardan CAD files (DXF/DWG/PDF) hosted on accentuate.io
 * 
 * Strategy:
 * 1. Fetch ALL products from Shopify JSON API (paginated)
 * 2. For each product, check known accentuate.io URL patterns
 * 3. Also check product tags/metadata for CAD references
 */
import { writeFileSync } from "fs";

const API_BASE = "https://www.jardan.com.au";
const FOUND_FILES = {};
const TIMEOUT = 10000;

async function fetchShopifyProducts() {
  const products = [];
  let page = 1;
  while (true) {
    const url = `${API_BASE}/products.json?page=${page}&limit=250`;
    const res = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT) });
    const data = await res.json();
    if (!data.products || data.products.length === 0) break;
    products.push(...data.products);
    console.log(`  Page ${page}: ${data.products.length} products`);
    page++;
    if (page > 20) break; // safety: max 5000 products
  }
  return products;
}

async function checkAccentuateUrl(productId, filename) {
  // Try multiple timestamp variants
  const timestamps = [
    "1710979036561", // known working timestamp
  ];
  for (const ts of timestamps) {
    try {
      const url = `https://original.accentuate.io/${productId}/${ts}/${filename}`;
      const res = await fetch(url, { method: "HEAD", signal: AbortSignal.timeout(5000) });
      if (res.ok || res.status === 200) {
        return { url, status: res.status, size: res.headers.get("content-length") };
      }
    } catch {}
  }
  return null;
}

async function main() {
  console.log("=== Step 1: Fetch all Shopify products ===");
  const products = await fetchShopifyProducts();
  console.log(`Total products: ${products.length}`);

  // Extract unique range names from product titles/tags
  const ranges = new Set();
  for (const p of products) {
    const tags = Array.isArray(p.tags) ? p.tags.join(" ") : "";
    const title = p.title || "";
    // Extract range names from tags like "range: Nook"
    const rangeMatch = tags.match(/range:\s*(\w+)/i);
    if (rangeMatch) ranges.add(rangeMatch[1]);
    // Also check title for range codes
    const codeMatch = title.match(/^([A-Z]+)/);
    if (codeMatch && codeMatch[1].length > 1) ranges.add(codeMatch[1]);
  }
  console.log(`\nUnique ranges found: ${[...ranges].join(", ")}`);

  console.log("\n=== Step 2: Check products for DXF files ===");
  const dxfRanges = [];
  for (const range of ranges) {
    const filename = `${range.toUpperCase()}-RANGE.dxf`;
    // Find a product in this range
    const product = products.find((p) => {
      const tags = Array.isArray(p.tags) ? p.tags.join(" ") : "";
      return tags.includes(`range: ${range}`) || (p.title || "").startsWith(range);
    });
    if (product) {
      console.log(`Checking ${range} (product ${product.id})...`);
      const result = await checkAccentuateUrl(product.id, filename);
      if (result) {
        console.log(`  ✅ FOUND: ${filename} (${result.size} bytes)`);
        dxfRanges.push({ range, productId: product.id, url: result.url, filename, size: result.size });
        FOUND_FILES[result.url] = true;
      } else {
        console.log(`  ❌ Not found: ${filename}`);
      }
    }
  }

  console.log("\n=== Step 3: Check ALL products for any accentuate.io DXF ===");
  let totalChecked = 0;
  for (const p of products) {
    // Check for {handle}.dxf, {title}.dxf etc
    const candidates = [
      `${p.handle}.dxf`,
      `${(p.title || "").replace(/\s+/g, "-").toUpperCase()}.dxf`,
    ];
    for (const filename of candidates) {
      if (filename === ".dxf") continue;
      const result = await checkAccentuateUrl(p.id, filename);
      if (result) {
        const url = result.url;
        if (!FOUND_FILES[url]) {
          console.log(`  ✅ Found: ${p.handle} (${p.id}) → ${filename}`);
          FOUND_FILES[url] = true;
          totalChecked++;
        }
      }
    }
  }

  console.log(`\n=== RESULTS ===`);
  console.log(`DXF files found: ${Object.keys(FOUND_FILES).length}`);
  for (const url of Object.keys(FOUND_FILES)) {
    console.log(`  ${url}`);
  }

  // Save results
  writeFileSync("/tmp/jardan-cad-files.json", JSON.stringify({
    dxfFiles: Object.keys(FOUND_FILES),
    dxfRanges,
    totalProducts: products.length,
  }, null, 2));
  console.log(`\nResults saved to /tmp/jardan-cad-files.json`);
}

main().catch((e) => {
  console.error("FATAL:", e.message);
  process.exit(1);
});
