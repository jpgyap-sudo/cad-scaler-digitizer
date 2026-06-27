/**
 * Inspect a Jardan product page for Shopify product ID and hidden DXF links.
 */
import { chromium } from "playwright";

const TARGET_URL = process.argv[2] || "https://www.jardan.com.au/products/nk198";

(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage();
  await p.goto(TARGET_URL, { waitUntil: "domcontentloaded", timeout: 20000 });

  const info = await p.evaluate(() => {
    const results = {};

    // Shopify product ID from JSON-LD
    const scripts = Array.from(document.querySelectorAll("script"));
    for (const s of scripts) {
      const t = s.textContent;
      if (t.includes('"@type":"Product"') || t.includes('"product"')) {
        try {
          const json = JSON.parse(t);
          if (json["@type"] === "Product" || json["@graph"]) {
            const graph = json["@graph"] || [json];
            for (const item of graph) {
              if (item["@type"] === "Product") {
                results.productId = item.productID || item.sku;
                results.name = item.name;
                results.description = (item.description || "").slice(0, 200);
                // Check offers for product ID
                if (item.offers) {
                  results.offers = Array.isArray(item.offers)
                    ? item.offers.slice(0, 3)
                    : [item.offers];
                }
                break;
              }
            }
          }
        } catch {}
      }

      // Check for Shopify global variables
      if (t.includes("ShopifyAnalytics") || t.includes("productId")) {
        const match = t.match(/product[Ii]d[:\s]*[=]?\s*["']?(\d+)["']?/);
        if (match) results.shopifyIdFromScript = match[1];
      }

      // Check for accentuate.io references
      if (t.includes("accentuate") || t.includes("accentuate")) {
        const matches = t.match(/https?:\/\/[^"'\s]*(?:accentuate|dxf|dwg)[^"'\s]*/gi);
        if (matches) results.accentuateUrls = matches;
      }
    }

    // Check all link tags' full HTML
    results.linkTags = Array.from(document.querySelectorAll("link")).map((l) => ({
      rel: l.rel,
      href: l.href,
      type: l.type,
      as: l.as,
    }));

    // Check all <a> tags for download/CAD references
    results.downloadLinks = Array.from(document.querySelectorAll("a[href]"))
      .filter(
        (a) =>
          a.href.match(/\.(dxf|dwg|step|stp|pdf)$/i) ||
          a.href.includes("accentuate") ||
          a.textContent.toLowerCase().includes("dxf") ||
          a.textContent.toLowerCase().includes("cad") ||
          a.textContent.toLowerCase().includes("download")
      )
      .map((a) => ({ text: a.textContent.trim().slice(0, 60), href: a.href, download: a.download }));

    // Check all <form> elements
    results.forms = Array.from(document.querySelectorAll("form")).map((f) => ({
      action: f.action,
      id: f.id,
      inputs: Array.from(f.querySelectorAll("input[name]")).map((i) => ({
        name: i.name,
        value: (i.value || "").slice(0, 50),
        type: i.type,
      })),
    }));

    return results;
  });

  console.log("Product:", info.name || "unknown");
  console.log("Product ID:", info.productId || info.shopifyIdFromScript || "NOT FOUND");
  console.log("Description:", (info.description || "").slice(0, 150));
  console.log("");
  if (info.downloadLinks.length > 0) {
    console.log("=== Download/CAD links found ===");
    info.downloadLinks.forEach((l) => console.log(`  ${l.text} => ${l.href}`));
  } else {
    console.log("No DXF/CAD links on this page");
  }
  console.log("");
  if (info.accentuateUrls && info.accentuateUrls.length > 0) {
    console.log("=== Accentuate.io URLs found in scripts ===");
    info.accentuateUrls.forEach((u) => console.log("  " + u));
  }
  console.log("\n=== All link tags ===");
  info.linkTags.forEach((l) => console.log(`  ${l.rel}: ${l.href} (type:${l.type})`));

  await b.close();
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
