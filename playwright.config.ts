import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './frontend/tests',
  timeout: 30000,
  expect: { timeout: 10000 },
  use: {
    baseURL: 'https://cad.abcx124.xyz',
    headless: true,
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
});
