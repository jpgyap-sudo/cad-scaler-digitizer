import { chromium } from "playwright";

(async () => {
  const browser = await chromium.launch({headless:true, args:["--no-sandbox"]});
  const context = await browser.newContext({userAgent:"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"});
  const page = await context.newPage();
  
  // Intercept network to find API calls
  const apiUrls = [];
  page.on("response", response => {
    const url = response.url();
    if(url.includes("products") || url.includes("collections")) apiUrls.push(url);
  });
  
  await page.goto("https://www.jardan.com.au/pages/dining-tables", {
    waitUntil: "domcontentloaded", timeout: 20000
  }).catch(() => {});
  
  // Scroll to trigger lazy loading
  for(let i = 0; i < 10; i++) {
    await page.evaluate(() => window.scrollBy(0, 500));
    await new Promise(r => setTimeout(r, 1000));
  }
  
  // Extract product links from the fully scrolled page
  const links = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll("a[href]"));
    return all.map(a => ({text: a.textContent.trim().slice(0,50), href: a.href}))
             .filter(l => l.href.includes("/products/") && !l.href.includes("rug"));
  });
  
  console.log("Table product links: " + links.length);
  [...new Set(links.map(l => l.href))].slice(0,15).forEach(href => {
    const text = links.find(l => l.href === href).text;
    console.log("  " + text + " -> " + href);
  });
  
  console.log("\nAPI calls:");
  [...new Set(apiUrls)].forEach(u => console.log("  " + u));
  
  await browser.close();
})().catch(e => {console.error(e.message); process.exit(1)});
