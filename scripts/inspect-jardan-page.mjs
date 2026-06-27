import { chromium } from "playwright";

(async () => {
  const browser = await chromium.launch({headless:true, args:["--no-sandbox"]});
  const page = await browser.newPage();
  
  await page.goto("https://www.jardan.com.au/pages/dining-tables", {
    waitUntil: "domcontentloaded", timeout: 20000
  }).catch(() => {});
  
  await new Promise(r => setTimeout(r, 3000));
  
  const links = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll("a[href]"));
    return all.map(a => ({text: a.textContent.trim().slice(0,50), href: a.href}))
             .filter(l => l.href.includes("/products/"));
  });
  
  console.log("Product links: " + links.length);
  links.slice(0,15).forEach(l => console.log("  " + l.text + " -> " + l.href));
  
  const title = await page.title();
  console.log("\nTitle: " + title);
  
  await browser.close();
})().catch(e => {console.error(e.message); process.exit(1)});
