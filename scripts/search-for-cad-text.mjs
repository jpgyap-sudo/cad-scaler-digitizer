/**
 * Search Jardan product pages for text labels like "2D CAD FILE", "DXF", "CAD Download"
 * These might be linked to hidden DXF download URLs.
 */
import { chromium } from "playwright";
import { writeFileSync } from "fs";

// Text patterns to search for case-insensitive
const CAD_PATTERNS = [
  "2d cad", "cad file", "cad download", "technical drawing",
  "dxf download", "dwg download", "download dxf", "download cad",
  "specification sheet", "tech spec", "product drawing",
  "2d", "cad", "dxf", "dwg"
];

async function searchProduct(handle) {
  const url = "https://www.jardan.com.au/products/" + handle;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const result = { handle, cadLinks: [], textMatches: [], errors: [] };

  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });

    // Search for CAD-related text in all visible elements
    const textMatches = await page.evaluate((patterns) => {
      const results = [];
      const allElements = document.querySelectorAll("a, button, span, div, p, h1, h2, h3, h4, h5, h6, label, dt, dd, li");
      
      for (const el of allElements) {
        const text = (el.textContent || "").trim().toLowerCase();
        for (const pattern of patterns) {
          if (text.includes(pattern)) {
            // Check if this element or its parent has a link
            const link = el.closest("a") || el.querySelector("a[href]");
            const href = link ? link.href : null;
            const dataAttrs = {};
            for (const attr of el.attributes) {
              if (attr.name.startsWith("data-") || attr.name === "href" || attr.name === "download") {
                dataAttrs[attr.name] = attr.value;
              }
            }
            results.push({
              text: el.textContent.trim().slice(0, 100),
              tag: el.tagName,
              href,
              dataAttrs,
              parentClass: el.parentElement?.className?.slice(0, 100) || "",
              parentId: el.parentElement?.id || "",
            });
            break; // one match per element
          }
        }
      }
      return results;
    }, CAD_PATTERNS);

    result.textMatches = textMatches;

    // Also get the full HTML around any "2D" or "CAD" mentions
    const htmlContext = await page.evaluate(() => {
      const html = document.documentElement.outerHTML;
      const results = [];
      // Find "2D CAD" and capture surrounding context
      const regex = /.{0,100}(?:2D\s*CAD|CAD\s*FILE|DXF|DWG|2D\s*DRAWING).{0,100}/gi;
      let match;
      while ((match = regex.exec(html)) !== null) {
        results.push(match[0].trim());
      }
      return results;
    });
    result.htmlContext = htmlContext;

    // Also check for hidden download links in data attributes
    const hiddenLinks = await page.evaluate(() => {
      const links = [];
      document.querySelectorAll("[data-cad], [data-dxf], [data-download], [href*='.dxf'], [href*='.dwg']").forEach(el => {
        links.push({
          tag: el.tagName,
          href: el.href || el.getAttribute("data-cad") || el.getAttribute("data-dxf") || el.getAttribute("data-download"),
          text: el.textContent?.trim()?.slice(0, 50),
        });
      });
      return links;
    });
    result.hiddenLinks = hiddenLinks;

  } catch (e) {
    result.errors.push(e.message.slice(0, 100));
  } finally {
    await browser.close();
  }
  return result;
}

async function main() {
  // Check a focused set of products that we know have range DXF files
  const priorityHandles = [
    "arden-table",
    "lola-chair",
    "pia-table",
    "nk198",    // Nook sofa (Arden range)
    "ml290",    // Miller
    "bou2030",  // Boulder rug
    "bon-chair",
    "bon-table",
    "nk-modular-a",
    "nk-modular-b",
    "su240",
    "su-modular-a",
    "va-modular",
    "hd-modular",
    "thu280",
    "iz219",
    "mar210",
    "oi120",
    "au120",
    "olv172",
    "sbd115",
    "mi48t",
    "jean-chair",
    "cp-modular",
    "ce-modular",
    "vs-modular",
    "fn-chair",
    "byn-bed",
    "preston-desk",
    "andy-desk",
    "coast-table",
    "hugo-desk",
    "jy80-chair",
    "fn193-chair",
    "fo-chair",
    "willow-cabinet",
    "wilfred-cabinet",
    "harper-cabinet",
    "hudson-modular",
    "pearl-bed",
    "valley-sofa",
    "ml290",
    "indigo-modular",
    "izzy-chair",
    "floyd-bench",
    "ziggy-stool",
    "murphy-bed",
    "otis-table",
    "wattle-table",
    "oio-table",
    "pepper-chair",
    "seb-bench",
    "sweeney-cabinet",
    "stevie-chair",
    "dari-rug",
    "airo-bedding",
    // Rug products with PDFs
    "merla-rug-cinnamon",
    "patti-rug-clover",
    "bam-bam-drift",
    "ellis-rug",
    "nuri-rug-oat",
    "zora-rug-cobalt",
  ];

  console.log("=== Searching " + priorityHandles.length + " products for CAD text ===");

  let totalCadLinks = 0;
  let foundProducts = [];

  for (let i = 0; i < priorityHandles.length; i++) {
    const handle = priorityHandles[i];
    const result = await searchProduct(handle);

    // Filter to relevant matches
    const cadMatches = result.textMatches.filter(m =>
      m.href || m.dataAttrs?.href || Object.keys(m.dataAttrs).length > 0
    );

    if (cadMatches.length > 0 || result.hiddenLinks.length > 0 || result.htmlContext.length > 0) {
      console.log("\n--- " + handle + " ---");
      
      if (result.hiddenLinks.length > 0) {
        console.log("HIDDEN LINKS:");
        result.hiddenLinks.forEach(l => console.log("  " + JSON.stringify(l)));
      }

      if (cadMatches.length > 0) {
        console.log("TEXT MATCHES WITH LINKS:");
        cadMatches.slice(0, 5).forEach(m => {
          console.log("  Text: " + m.text);
          console.log("  Href: " + (m.href || "none"));
          console.log("  Data: " + JSON.stringify(m.dataAttrs));
          if (m.href && (m.href.includes("accentuate") || m.href.match(/\.(dxf|dwg|pdf)$/i))) {
            totalCadLinks++;
          }
        });
      }

      if (result.htmlContext.length > 0) {
        console.log("HTML CONTEXT:");
        result.htmlContext.slice(0, 3).forEach(ctx => console.log("  ..." + ctx + "..."));
      }

      foundProducts.push(handle);
    }

    if ((i + 1) % 10 === 0) console.log("\n  Checked " + (i + 1) + "/" + priorityHandles.length);
  }

  console.log("\n\n=== RESULTS ===");
  console.log("Products with CAD-related text: " + foundProducts.length);
  console.log("Actual DXF/DWG links found: " + totalCadLinks);
}

main().catch(e => { console.error("FATAL:", e.message); process.exit(1); });
