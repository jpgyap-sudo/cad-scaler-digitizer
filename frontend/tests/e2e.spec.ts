import { test, expect } from '@playwright/test';

const SITE = 'https://cad.abcx124.xyz';

test.describe('CAD Digitizer E2E', () => {

  test('page loads with all components', async ({ page }) => {
    await page.goto(SITE);
    await page.waitForLoadState('networkidle');

    // Title should be visible
    await expect(page.locator('h1')).toContainText('CAD', { timeout: 10000 });

    // Upload area div should be clickable (file input is hidden by design)
    const uploadDiv = page.locator('.border-dashed, [class*="cursor-pointer"]');
    await expect(uploadDiv.first()).toBeVisible({ timeout: 5000 });
    console.log('PASS: Page loads, upload area visible');
  });

  test('ChatBox and BrainStats visible at idle', async ({ page }) => {
    await page.goto(SITE);
    await page.waitForLoadState('networkidle');

    // ChatBox should be visible (Drawing Assistant button)
    const chatButton = page.locator('button:has-text("Drawing Assistant")');
    await expect(chatButton).toBeVisible({ timeout: 10000 });
    console.log('PASS: ChatBox visible');

    // BrainStats should be visible (Central Brain text)
    const brainText = page.locator('text=Central Brain');
    await expect(brainText).toBeVisible({ timeout: 5000 });
    console.log('PASS: BrainStats visible');
  });

  test('API health check', async ({ request }) => {
    const resp = await request.get(`${SITE}/py-api/health`);
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data.ok).toBe(true);
    expect(data.hybrid).toBe(true);
    console.log('PASS: API healthy:', JSON.stringify(data));
  });

  test('Brain API works', async ({ request }) => {
    const resp = await request.get(`${SITE}/py-api/brain/report`);
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data).toHaveProperty('corrections_by_type');
    expect(data).toHaveProperty('top_materials');
    console.log('PASS: Brain report returned');
  });

  test('Presets API works', async ({ request }) => {
    const resp = await request.get(`${SITE}/py-api/presets`);
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data).toHaveProperty('presets');
    console.log('PASS: Presets API');
  });

  test('Chat API returns response', async ({ request }) => {
    const formData = new URLSearchParams();
    formData.append('message', 'test');
    const resp = await request.post(`${SITE}/py-api/chat`, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: formData.toString(),
    });
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data).toHaveProperty('response');
    console.log('PASS: Chat API works, response:', data.response?.slice(0, 60));
  });

});
