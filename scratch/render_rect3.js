const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const svg = fs.readFileSync('scratch/rect_fixed2.svg', 'utf-8');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1300, height: 950 } });
  await page.setContent(`<html><body style="margin:0">${svg}</body></html>`);
  await page.screenshot({ path: 'scratch/rect_fixed2.png' });
  await browser.close();
})();
