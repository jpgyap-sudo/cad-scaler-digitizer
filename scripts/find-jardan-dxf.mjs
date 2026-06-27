/**
 * Find all Jardan DXF/DWG files
 * Step 1: Crawl product pages looking for accentuate.io links
 * Step 2: Check page source for hidden CAD download links
 * Step 3: Try to enumerate via Shopify product API
 */
import { chromium } from "playwright";
import { createClient } from "redis";

const PRODUCT_URLS = []; // populated from sitemap

const FOUND_DXF = {};

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

async function checkPageForDXF(url) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
    
    // Method 1: Check all link tags in <head>
    const dxfLinks = await page.evaluate(() => {
      const results = [];
      
      // Check all <link> tags
      document.querySelectorAll("link").forEach(l => {
        if (l.href) results.push({ tag: "link", rel: l.rel, href: l.href, type: l.type });
      });
      
      // Check all <a> tags with DXF/DWG in href or text
      document.querySelectorAll("a[href]").forEach(a => {
        if (a.href.match(/\.(dxf|dwg|step|stp|iges|igs|pdf)$/i) || 
            a.textContent.match(/dxf|dwg|cad|download|spec|technical|drawing/i)) {
          results.push({ tag: "a", text: a.textContent.trim().slice(0, 50), href: a.href });
        }
      });
      
      // Check all <meta> tags
      document.querySelectorAll("meta").forEach(m => {
        if (m.content?.match(/\.dxf/i)) {
          results.push({ tag: "meta", name: m.name, content: m.content });
        }
      });
      
      // Check JSON-LD
      document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
        if (s.textContent?.match(/dxf/i)) {
          results.push({ tag: "jsonld", content: s.textContent.slice(0, 200) });
        }
      });
      
      return results;
    });
    
    return dxfLinks;
  } catch (e) {
    return [{ error: e.message }];
  } finally {
    await browser.close();
  }
}

async function main() {
  console.log("=== Step 1: Discover product URLs ===");
  const products = await crawlSitemap();
  console.log(`Found ${products.length} products`);
  
  // Quick-check a sample of products for DXF links
  const sampleSize = Math.min(products.length, 100);
  console.log(`\n=== Step 2: Check ${sampleSize} products for DXF links ===`);
  
  let dxfFound = 0;
  for (let i = 0; i < sampleSize; i++) {
    const url = products[i];
    const links = await checkPageForDXF(url);
    const dxfRel = links.filter(l => 
      l.href?.match(/\.(dxf|dwg)$/i) || 
      l.href?.includes("accentuate") ||
      l.text?.match(/dxf|cad|dwg/i)
    );
    
    if (dxfRel.length > 0) {
      console.log(`\nDXF on ${url.split('/').pop()}:`);
      dxfRel.forEach(l => {
        if (!FOUND_DXF[l.href]) {
          FOUND_DXF[l.href] = true;
          console.log(`  [${l.tag}] ${l.href}`);
          dxfFound++;
        }
      });
    }
    
    if ((i + 1) % 20 === 0) console.log(`  Checked ${i + 1}/${sampleSize}`);
  }
  
  console.log(`\n=== Results ===`);
  console.log(`Products checked: ${sampleSize}`);
  console.log(`Unique DXF/DWG URLs found: ${dxfFound}`);
  console.log(`URLs:`, Object.keys(FOUND_DXF));
  
  process.exit(0);
}

main().catch(e => { console.error(e); process.exit(1); });
