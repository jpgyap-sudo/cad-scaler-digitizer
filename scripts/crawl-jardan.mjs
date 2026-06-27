/**
 * Jardan Catalog Crawler
 * Reads all product URLs from sitemap and submits crawl jobs in batches.
 *
 * Usage: node crawl-jardan.mjs
 */
import { chromium } from "playwright";
import { writeFileSync, readFileSync, existsSync } from "fs";

const API_BASE = process.env.API_BASE || "http://node-api:4000";
const BATCH_SIZE = 5;       // concurrent crawl jobs
const RATE_LIMIT_MS = 2000; // delay between batches

async function crawlSitemap() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  await page.goto("https://www.jardan.com.au/sitemap.xml", {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  const text = await page.evaluate(
    () => document.querySelector("pre")?.textContent || document.body.innerText
  );
  const locs = [...text.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
  const productSitemap = locs.find((l) => l.includes("product"));

  await page.goto(productSitemap, {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  const productText = await page.evaluate(
    () => document.querySelector("pre")?.textContent || document.body.innerText
  );
  const productUrls = [...productText.matchAll(/<loc>([^<]+)<\/loc>/g)]
    .map((m) => m[1])
    .filter((u) => u !== "https://www.jardan.com.au/");

  await browser.close();
  return productUrls;
}

/**
 * Categorise a Jardan product URL into a specific furniture type.
 * Returns: sofa, table, chair, lighting, rug, bed, cabinet, modular, homewares, or furniture
 */
function categorize(url) {
  const path = new URL(url).pathname.toLowerCase();
  const slug = path.replace(/\/products\//, "");

  // Specific product-type keywords, ordered most-specific first
  const categories = [
    { cat: "sofa",      kw: ["sofa", "couch", "ottoman", "chaise"] },
    { cat: "modular",   kw: ["modular"] },  // modular sofa/table components
    { cat: "table",     kw: ["table", "desk", "coffee", "dining", "sideboard", "console"] },
    { cat: "chair",     kw: ["chair", "stool", "bench"] },
    { cat: "bed",       kw: ["bed", "headboard", "mattress"] },
    { cat: "cabinet",   kw: ["cabinet", "drawer", "shelf", "bookcase", "wardrobe", "chest", "buffet", "credenza"] },
    { cat: "lighting",  kw: ["lamp", "light", "pendant", "chandelier", "sconce"] },
    { cat: "rug",       kw: ["rug", "carpet", "runner"] },
    { cat: "homewares", kw: ["cushion", "vase", "decor", "tray", "bowl", "basket", "mirror", "clock", "candle", "throw", "homewares"] },
  ];

  for (const { cat, kw } of categories) {
    for (const keyword of kw) {
      if (slug.includes(keyword)) return cat;
    }
  }

  // Heuristic: numeric product codes (nk198, va276, etc.) — check URL structure
  // Jardan product codes starting with certain prefixes indicate furniture type
  const codeMap = {
    // Sofa prefixes
    nk: "sofa", ml: "sofa", su: "sofa", va: "sofa", hd: "sofa",
    cp: "sofa", ad: "sofa", ce: "sofa", vs: "sofa",
    // Table prefixes
    iz: "table", mar: "table", oi: "table", oio: "table",
    au: "table", thu: "table", olv: "table",
    // Chair prefixes
    jy: "chair", ln: "chair", fn: "chair", fo: "chair",
    // Cabinet/storage prefixes
    lo: "cabinet", wf: "cabinet", wi: "cabinet",
    // Bedroom
    sbd: "bed", mi: "bed",
  };
  const code = slug.match(/^([a-z]+)/)?.[1];
  if (code && codeMap[code]) return codeMap[code];

  return "furniture"; // default fallback
}

async function submitJob(productUrl, category, index, total) {
  const id =
    productUrl.replace("https://www.jardan.com.au/products/", "").split(/[/?#]/)[0] ||
    `product-${index}`;

  try {
    const res = await fetch(`${API_BASE}/api/crawl`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: productUrl,
        manufacturer: "jardan",
        category,
      }),
    });
    if (res.ok) {
      const result = await res.json();
      console.log(`✓ [${index}/${total}] ${id} → ${result.jobId}`);
      return result.jobId;
    } else {
      const err = await res.text();
      console.error(`✗ [${index}/${total}] ${id}: ${err.substring(0, 100)}`);
      return null;
    }
  } catch (e) {
    console.error(`✗ [${index}/${total}] ${id}: ${e.message}`);
    return null;
  }
}

async function checkResults(productUrls, results) {
  const completed = results.filter((r) => r).length;
  const failed = results.filter((r) => r === null).length;
  console.log(`\nSubmitted: ${completed}, Failed: ${failed} / ${productUrls.length}`);

  // Check a sample of completed jobs
  const sample = results.filter(Boolean).slice(0, 5);
  for (const jobId of sample) {
    try {
      const res = await fetch(`${API_BASE}/api/crawl/${jobId}`);
      if (res.ok) {
        const status = await res.json();
        console.log(`  ${jobId}: ${status.status}`);
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
}

async function main() {
  let productUrls;
  if (process.argv.includes("--reuse") && existsSync("/tmp/jardan-products.json")) {
    productUrls = JSON.parse(readFileSync("/tmp/jardan-products.json", "utf-8"));
    console.log(`Loaded ${productUrls.length} products from cache`);
  } else {
    productUrls = await crawlSitemap();
    writeFileSync("/tmp/jardan-products.json", JSON.stringify(productUrls, null, 2));
    console.log(`Discovered ${productUrls.length} products`);
  }

  const total = productUrls.length;
  const results = [];
  let successCount = 0;
  let failCount = 0;

  // Process in batches
  for (let i = 0; i < total; i += BATCH_SIZE) {
    const batch = productUrls.slice(i, i + BATCH_SIZE);
    const batchResults = await Promise.all(
      batch.map((url, j) => {
        const idx = i + j + 1;
        const category = categorize(url);
        return submitJob(url, category, idx, total);
      })
    );

    results.push(...batchResults);
    successCount += batchResults.filter((r) => r).length;
    failCount += batchResults.filter((r) => r === null).length;

    // Rate limit between batches
    if (i + BATCH_SIZE < total) {
      await new Promise((r) => setTimeout(r, RATE_LIMIT_MS));
    }
  }

  console.log("\n======= CRAWL COMPLETE =======");
  console.log(`Total products: ${total}`);
  console.log(`Jobs submitted: ${successCount}`);
  console.log(`Jobs failed:    ${failCount}`);

  // Save results
  writeFileSync("/tmp/jardan-results.json", JSON.stringify(results, null, 2));

  // Check sample status
  console.log("\nChecking sample statuses...");
  await checkResults(productUrls, results);
}

main().catch((e) => {
  console.error("FATAL:", e.message);
  process.exit(1);
});
