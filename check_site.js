const { chromium } = require('@playwright/test');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(err.message));
  await page.goto('https://cad.abcx124.xyz', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(2000);
  console.log('Title:', await page.title());
  console.log('Has body content:', (await page.content()).length > 500 ? 'YES' : 'NO');
  console.log('JS errors:', errors.length ? errors.join('; ') : 'NONE');
  // Check if ChatBox is in DOM
  const chatHtml = await page.evaluate(() => document.body.innerHTML.includes('Drawing Assistant'));
  console.log('ChatBox in DOM:', chatHtml);
  await browser.close();
})();
