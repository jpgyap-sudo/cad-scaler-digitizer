import { chromium } from "playwright";

(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage();
  await p.goto("https://www.jardan.com.au/collections/arden", {
    waitUntil: "networkidle",
    timeout: 30000,
  });

  // Get all links
  const links = await p.evaluate(() =>
    Array.from(document.querySelectorAll("a[href]")).map((a) => ({
      text: a.textContent.trim().slice(0, 100),
      href: a.href,
    }))
  );

  // Find all product page links
  const productLinks = links.filter((l) =>
    l.href.includes("/products/")
  );
  console.log("=== Product links on Arden collection ===");
  productLinks.slice(0, 30).forEach((l) => console.log("  " + l.href));

  // Check the first product page for DXF/CAD links
  if (productLinks.length > 0) {
    console.log("\n=== First product page ===");
    await p.goto(productLinks[0].href, {
      waitUntil: "networkidle",
      timeout: 30000,
    });

    const pageLinks = await p.evaluate(() =>
      Array.from(document.querySelectorAll("a[href]")).map((a) => ({
        text: a.textContent.trim().slice(0, 100),
        href: a.href,
      }))
    );
    const cadLinks = pageLinks.filter((l) =>
      /dxf|cad|dwg|step|download|spec|tech/.test(l.href.toLowerCase()) ||
      /dxf|cad|dwg|step|download|spec|tech/.test(l.text.toLowerCase()) ||
      l.href.match(/\.(dxf|dwg|step|stp|pdf)$/i)
    );
    if (cadLinks.length > 0) {
      console.log("CAD/download links on product page:");
      cadLinks.forEach((l) => console.log("  " + l.text + " => " + l.href));
    } else {
      console.log("No CAD/download links found on first product page.");
    }

    // Also scan for links in meta/head
    const metas = await p.evaluate(() =>
      Array.from(document.querySelectorAll('link[rel*="alternate"], link[type*="dxf"], link[href*=".dxf"]')).map(
        (e) => ({ rel: e.rel, href: e.href, type: e.type })
      )
    );
    if (metas.length > 0) {
      console.log("Meta links:", JSON.stringify(metas));
    }
  }

  await b.close();
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
