import { writeFileSync } from "fs";

const ASSETS = {};

async function checkProduct(handle) {
  try {
    const url = "https://www.jardan.com.au/products/" + handle;
    const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
    const html = await res.text();
    const regex = /https?:\/\/(?:original|cdn)\.accentuate\.io\/(\d+)\/(\d+)\/([^"'\s>?]+)/gi;
    let match;
    let found = 0;
    while ((match = regex.exec(html)) !== null) {
      const fullUrl = match[0];
      if (!ASSETS[fullUrl]) {
        ASSETS[fullUrl] = {
          productId: match[1],
          timestamp: match[2],
          filename: match[3],
          ext: match[3].split(".").pop().toLowerCase(),
          handle
        };
        found++;
      }
    }
    return found;
  } catch {
    return 0;
  }
}

async function main() {
  console.log("Fetching all products from Shopify API...");
  const allHandles = [];
  for (let page = 1; page <= 5; page++) {
    try {
      const url = "https://www.jardan.com.au/products.json?page=" + page + "&limit=250";
      const r = await fetch(url, { signal: AbortSignal.timeout(10000) });
      const data = await r.json();
      allHandles.push(...data.products.map(p => p.handle));
    } catch (e) {
      console.error("Error page", page, e.message);
    }
  }
  console.log("Total: " + allHandles.length + " products");

  console.log("Scanning for accentuat.io assets...");
  for (let i = 0; i < allHandles.length; i++) {
    await checkProduct(allHandles[i]);
    if ((i + 1) % 200 === 0) {
      console.log("  " + (i + 1) + "/" + allHandles.length + " checked, " + Object.keys(ASSETS).length + " assets");
    }
  }

  // Categorize
  const byExt = {};
  for (const [url, info] of Object.entries(ASSETS)) {
    const ext = info.ext || "other";
    if (!byExt[ext]) byExt[ext] = [];
    byExt[ext].push(url);
  }

  console.log("");
  console.log("=== ACCENTUATE.IO ASSETS FOUND ===");
  const total = Object.keys(ASSETS).length;
  console.log("Total unique assets: " + total);
  for (const [ext, urls] of Object.entries(byExt)) {
    console.log("  ." + ext + ": " + urls.length + " files");
  }

  // Show DXF/DWG
  const dxf = byExt["dxf"] || [];
  const dwg = byExt["dwg"] || [];
  if (dxf.length > 0 || dwg.length > 0) {
    console.log("");
    console.log("=== CAD FILES (DXF/DWG) ===");
    for (const url of [...dxf, ...dwg]) {
      console.log("  " + ASSETS[url].handle + " -> " + url);
    }
  }

  // Show PDFs summary
  const pdf = byExt["pdf"] || [];
  if (pdf.length > 0) {
    console.log("");
    console.log("=== PDF FILES: " + pdf.length + " ===");
    const byProduct = {};
    for (const url of pdf) {
      const h = ASSETS[url].handle;
      if (!byProduct[h]) byProduct[h] = [];
      byProduct[h].push(url);
    }
    const entries = Object.entries(byProduct);
    for (const [handle, urls] of entries.slice(0, 10)) {
      console.log("  " + handle + ": " + urls.length + " PDFs");
      urls.forEach(u => console.log("    " + u));
    }
    if (entries.length > 10) {
      console.log("  ... and " + (entries.length - 10) + " more products");
    }
  }

  // Save
  const result = { total, byExt, assets: ASSETS };
  writeFileSync("/tmp/all-accentuate-assets.json", JSON.stringify(result, null, 2));
  console.log("");
  console.log("Saved to /tmp/all-accentuate-assets.json");
}

main().catch(e => { console.error("FATAL:", e.message); process.exit(1); });
