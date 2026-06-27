/**
 * Find Jardan dining table product URLs and test 5 of them.
 * Uses Playwright for JS-rendered content since Jardan uses JavaScript.
 */
import { chromium } from "playwright";

const API = "http://python-worker:8001";
const BASE = "https://www.jardan.com.au";
const STORE = "https://www.jardan.com.au/pages/dining-tables";

async function findProducts() {
  const browser = await chromium.launch({ headless: true, args: [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
  ]});
  const page = await browser.newPage();
  
  await page.goto(STORE, { waitUntil: "domcontentloaded", timeout: 30000 });
  
  // Extract all product URLs from rendered page
  const urls = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll("a[href]"));
    return links
      .map(a => a.href)
      .filter(h => h.includes("/products/"))
      .filter((v, i, a) => a.indexOf(v) === i);
  });
  
  await browser.close();
  return urls;
}

async function digitize(url) {
  const r = await fetch(`${API}/api/crawl-to-dxf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, category: "table" }),
    signal: AbortSignal.timeout(90000),
  });
  return r.json();
}

async function main() {
  console.log("=== Jardan Dining Tables — Product Iteration ===\n");
  
  const products = await findProducts();
  console.log(`Found ${products.length} product URLs\n`);
  
  for (let i = 0; i < Math.min(products.length, 5); i++) {
    const url = products[i];
    const slug = url.split("/").pop();
    console.log(`${i + 1}. ${slug}`);
    
    try {
      const result = await digitize(url);
      const dims = result.page_dimensions || {};
      const cmp = result.comparison || {};
      const w = dims.width_cm || "?";
      const h = dims.overall_height_cm || "?";
      const score = cmp.overall_score;
      const sizes = dims.sizes || [];
      
      console.log(`   DXF: ${!!result.dxf_file} | Dims: ${w}x${h}${sizes.length ? ` (${sizes.length} sizes)` : ""}`);
      if (typeof score === "number") {
        console.log(`   Score: ${score.toFixed(4)}`);
        if (score >= 0.9) console.log("   🎯 REACHED");
        else console.log(`   Gap: ${((0.9 - score) * 100).toFixed(1)}%`);
      } else {
        console.log(`   Score: ${score}`);
      }
    } catch (e) {
      console.log(`   ERROR: ${e.message.slice(0, 80)}`);
    }
    console.log();
  }
  
  console.log("Done");
}

main().catch(e => { console.error(e.message); process.exit(1); });
