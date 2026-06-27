/**
 * Download all accentuat.io PDF spec sheets and import them as product assets.
 * PDFs contain technical drawings that can be used for validation.
 */
const ASSETS_FILE = "/tmp/all-accentuate-assets.json";
const API_BASE = "http://localhost:4000";
const DOWNLOAD_DIR = "/tmp/cad-pdfs";

import { readFileSync, mkdirSync, writeFileSync } from "fs";
import { join } from "path";

async function downloadFile(url, dest) {
  const res = await fetch(url, { signal: AbortSignal.timeout(30000) });
  if (!res.ok) throw new Error("HTTP " + res.status);
  const buf = Buffer.from(await res.arrayBuffer());
  writeFileSync(dest, buf);
  return buf.length;
}

async function createProductAndUpload(handle, pdfUrl) {
  const productName = handle.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  const category = handle.includes("rug") ? "rug" :
    handle.includes("mirror") ? "homewares" : "furniture";

  // Create product
  try {
    const r = await fetch(API_BASE + "/api/product-references", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        manufacturer: "jardan",
        productName,
        category,
        slug: handle,
      }),
    });
    if (!r.ok) {
      const err = await r.text();
      if (err.includes("Unique") || err.includes("already exists")) {
        return { status: "exists", handle };
      }
      return { status: "error", error: err.slice(0, 100) };
    }
    const product = await r.json();

    // Download PDF
    const filename = pdfUrl.split("/").pop().split("?")[0];
    const dest = join(DOWNLOAD_DIR, filename);
    const size = await downloadFile(pdfUrl, dest);

    // Upload as asset
    const fd = new FormData();
    fd.append("assetType", "PDF");
    const buf = readFileSync(dest);
    fd.append("file", new Blob([buf]), filename);
    const a = await fetch(API_BASE + "/api/product-references/" + product.id + "/assets", {
      method: "POST",
      body: fd,
    });
    if (!a.ok) {
      return { status: "upload_failed", handle };
    }
    const asset = await a.json();

    return { status: "imported", handle, productId: product.id, size, cdnUrl: asset.cdnUrl };
  } catch (e) {
    return { status: "error", error: e.message.slice(0, 100) };
  }
}

async function main() {
  // Load assets
  const data = JSON.parse(readFileSync(ASSETS_FILE, "utf-8"));
  const pdfs = Object.entries(data.assets).filter(([url, info]) => info.ext === "pdf");

  console.log("Total PDFs to import: " + pdfs.length);

  // Create download dir
  mkdirSync(DOWNLOAD_DIR, { recursive: true });

  let imported = 0;
  let exists = 0;
  let errors = 0;

  for (const [url, info] of pdfs) {
    const result = await createProductAndUpload(info.handle, url);

    if (result.status === "imported") {
      console.log("  OK " + info.handle + " (" + result.size + " bytes)");
      imported++;
    } else if (result.status === "exists") {
      exists++;
    } else {
      console.log("  FAIL " + info.handle + ": " + (result.error || ""));
      errors++;
    }
  }

  console.log("");
  console.log("=== PDF IMPORT COMPLETE ===");
  console.log("Imported: " + imported);
  console.log("Already exists: " + exists);
  console.log("Errors: " + errors);
}

main().catch(e => { console.error("FATAL:", e.message); process.exit(1); });
