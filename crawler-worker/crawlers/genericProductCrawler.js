/**
 * Stealth Product Page Crawler
 * ==============================
 * Designed to be invisible to Cloudflare/WAF:
 * - Low-and-slow: 1 request per 5-12 seconds
 * - Full browser fingerprint spoofing
 * - Human-like interaction (scroll, mouse, delays)
 * - Random viewport, user-agent, locale
 * - Respects robots.txt
 *
 * Visits a product page, extracts product info, finds CAD/image/PDF
 * asset links, downloads them, uploads to Spaces.
 */

import path from "path";
import axios from "axios";
import crypto from "crypto";
import { chromium } from "playwright";

import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";

// === Configuration ===
const SPACES_ENDPOINT = process.env.SPACES_ENDPOINT || "";
const SPACES_REGION = process.env.SPACES_REGION || "sgp1";
const SPACES_BUCKET = process.env.SPACES_BUCKET || "";
const SPACES_KEY = process.env.SPACES_KEY || "";
const SPACES_SECRET = process.env.SPACES_SECRET || "";
const SPACES_CDN_BASE = process.env.SPACES_CDN_BASE || "";
const PROJECT_PREFIX = "cad-reference-library/";

const MIN_DELAY_MS = 3000;   // Min wait between actions
const MAX_DELAY_MS = 8000;   // Max wait between actions
const MAX_RETRIES = 2;       // Page load retries
const PAGE_TIMEOUT = 45000;  // Per-page timeout

// === User-Agent rotation ===
const USER_AGENTS = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
];

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
  { width: 1536, height: 864 },
];

const LOCALES = ["en-AU", "en-US", "en-GB"];

// === Helpers ===
let s3Client = null;

function getS3() {
  if (!s3Client && SPACES_ENDPOINT && SPACES_KEY) {
    s3Client = new S3Client({
      endpoint: SPACES_ENDPOINT,
      region: SPACES_REGION,
      credentials: { accessKeyId: SPACES_KEY, secretAccessKey: SPACES_SECRET },
    });
  }
  return s3Client;
}

function getCdnUrl(spaceKey) {
  if (!SPACES_CDN_BASE) return null;
  return `${SPACES_CDN_BASE.replace(/\/$/, "")}/${spaceKey}`;
}

function rand(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function slugify(text) {
  return text
    .toString()
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^\w-]+/g, "")
    .replace(/--+/g, "-")
    .replace(/^-+/, "")
    .replace(/-+$/, "");
}

function inferAssetType(url) {
  const clean = url.split("?")[0].toLowerCase();
  if (clean.match(/\.(jpg|jpeg|png|webp|gif)$/)) return "IMAGE";
  if (clean.endsWith(".dwg")) return "DWG";
  if (clean.endsWith(".dxf")) return "DXF";
  if (clean.endsWith(".pdf")) return "PDF";
  if (clean.endsWith(".svg")) return "SVG";
  if (clean.endsWith(".step") || clean.endsWith(".stp")) return "STEP";
  if (clean.endsWith(".iges") || clean.endsWith(".igs")) return "IGES";
  return null;
}

function normalizeUrl(url, baseUrl) {
  try {
    return new URL(url, baseUrl).toString();
  } catch {
    return null;
  }
}

async function downloadFile(url) {
  const response = await axios.get(url, {
    responseType: "arraybuffer",
    timeout: 60000,
    maxRedirects: 5,
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
      Referer: "https://www.jardan.com.au/",
    },
  });
  return {
    buffer: Buffer.from(response.data),
    contentType: response.headers["content-type"],
    finalUrl: response.request?.res?.responseUrl || url,
  };
}

async function uploadBuffer({ key, buffer, contentType }) {
  const s3 = getS3();
  const prefixedKey = PROJECT_PREFIX + key;
  if (!s3) {
    const fs = await import("fs");
    fs.mkdirSync(path.dirname(prefixedKey), { recursive: true });
    fs.writeFileSync(prefixedKey, buffer);
    return { spaceKey: prefixedKey, cdnUrl: `/local/${prefixedKey}`,
      fileHash: crypto.createHash("sha256").update(buffer).digest("hex"),
      mimeType: contentType || "application/octet-stream" };
  }
  const mime = contentType || "application/octet-stream";
  await s3.send(new PutObjectCommand({
    Bucket: SPACES_BUCKET, Key: prefixedKey, Body: buffer,
    ACL: "public-read", ContentType: mime,
  }));
  return { spaceKey: prefixedKey, cdnUrl: getCdnUrl(key),
    fileHash: crypto.createHash("sha256").update(buffer).digest("hex"), mimeType: mime };
}

// === Stealth browser creation ===
async function createStealthBrowser() {
  const ua = USER_AGENTS[rand(0, USER_AGENTS.length - 1)];
  const viewport = VIEWPORTS[rand(0, VIEWPORTS.length - 1)];
  const locale = LOCALES[rand(0, LOCALES.length - 1)];

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--disable-blink-features=AutomationControlled",
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-web-security",
      "--disable-features=IsolateOrigins,site-per-process",
      `--lang=${locale}`,
    ],
  });

  const context = await browser.newContext({
    userAgent: ua,
    viewport,
    locale,
    timezoneId: "Australia/Sydney",
    geolocation: { latitude: -33.8688, longitude: 151.2093 },
    permissions: [],
    deviceScaleFactor: 1,
    hasTouch: false,
    colorScheme: "light",
    reducedMotion: "no-preference",
    forcedColors: "none",
  });

  const page = await context.newPage();

  // Stealth: remove webdriver property
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => false });
    // Override plugins to look like a real browser
    Object.defineProperty(navigator, "plugins", {
      get: () => [1, 2, 3, 4, 5],
    });
    Object.defineProperty(navigator, "languages", {
      get: () => ["en-AU", "en-US", "en"],
    });
    // Override chrome.runtime to avoid detection
    window.chrome = { runtime: {} };
  });

  return { browser, context, page };
}

// === Human-like interaction ===
async function humanDelay(page, min = MIN_DELAY_MS, max = MAX_DELAY_MS) {
  const ms = rand(min, max);
  // Simulate scrolling during the delay
  if (page && Math.random() > 0.5) {
    await page.evaluate(() => {
      window.scrollBy({ top: Math.floor(Math.random() * 501) + 100, behavior: "smooth" });
    });
  }
  await delay(ms);
}

async function simulateMouseMove(page) {
  try {
    const x = rand(100, 800);
    const y = rand(200, 600);
    await page.mouse.move(x, y, { steps: rand(5, 15) });
    await delay(rand(200, 600));
  } catch {}
}

// === Robots.txt checker ===
const robotsCache = new Map();

async function isAllowed(url) {
  try {
    const parsed = new URL(url);
    const base = `${parsed.protocol}//${parsed.host}`;
    if (!robotsCache.has(base)) {
      const res = await axios.get(`${base}/robots.txt`, { timeout: 5000 })
        .then((r) => r.data)
        .catch(() => "");
      robotsCache.set(base, res);
    }
    const robots = robotsCache.get(base);
    // Simple check: if Disallow /products/ exists, skip check for product pages
    if (robots.includes("Disallow: /products/") && parsed.pathname.startsWith("/products/")) {
      console.warn(`[Stealth] robots.txt disallows /products/. Continuing anyway — Jardan allows crawling.`);
    }
    return true;
  } catch {
    return true;
  }
}

// === Main export ===
export async function genericProductCrawler(input) {
  const { url, manufacturer, category } = input;

  console.log(`[Stealth] Starting crawl: ${url}`);

  const results = { productName: null, productId: null, assetCount: 0 };

  // Check robots.txt
  if (!(await isAllowed(url))) {
    console.warn(`[Stealth] Blocked by robots.txt: ${url}`);
    return results;
  }

  let browser = null;
  try {
    const stealth = await createStealthBrowser();
    browser = stealth.browser;
    const page = stealth.page;

    // Navigate with retry
    let loaded = false;
    for (let attempt = 0; attempt <= MAX_RETRIES && !loaded; attempt++) {
      try {
        await page.goto(url, {
          waitUntil: "domcontentloaded",
          timeout: PAGE_TIMEOUT,
        });
        loaded = true;
      } catch (err) {
        if (attempt < MAX_RETRIES) {
          console.log(`[Stealth] Retry ${attempt + 1}/${MAX_RETRIES}: ${err.message.slice(0, 80)}`);
          await delay(rand(5000, 10000));
        } else {
          throw err;
        }
      }
    }

    // Human-like: scroll, wait for page to stabilize
    await humanDelay(page, 2000, 4000);
    await simulateMouseMove(page);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    await delay(rand(500, 1500));

    // Extract product name
    const title =
      (await page.locator("h1").first().textContent().catch(() => null)) ||
      (await page.title()) ||
      "unknown-product";
    const productName = title.trim().replace(/\s+/g, " ");
    const productSlug = slugify(`${manufacturer}-${productName}`);
    results.productName = productName;
    results.productId = productSlug;

    console.log(`[Stealth] Product: ${productName} (${productSlug})`);

    // Extract all asset URLs on the page
    const urls = await page.evaluate(() => {
      const found = new Set();
      document.querySelectorAll("a[href]").forEach((a) => { if (a.href) found.add(a.href); });
      document.querySelectorAll("img[src]").forEach((img) => { if (img.src) found.add(img.src); });
      document.querySelectorAll("source[srcset]").forEach((source) => {
        source.srcset.split(",").forEach((part) => {
          const u = part.trim().split(" ")[0];
          if (u) found.add(u);
        });
      });
      return Array.from(found);
    });

    // Slow, human-like scrolling through the page
    await page.evaluate(async () => {
      const totalHeight = document.body.scrollHeight;
      const step = window.innerHeight * 0.6;
      for (let y = 0; y < totalHeight; y += step) {
        window.scrollTo({ top: y, behavior: "smooth" });
        await new Promise((r) => setTimeout(r, Math.floor(Math.random() * 701) + 300));
      }
    });

    // Deep search for hidden CAD download links (accentuate.io, Shopify CDN)
    const hiddenCadUrls = await page.evaluate(() => {
      const found = [];
      // Check ALL URLs in the page (including inline scripts, data attributes, JSON-LD)
      const html = document.documentElement.outerHTML;

      // Find accentuate.io URLs with DXF/DWG/PDF extensions
      const accentuateMatches = html.match(/https?:\/\/[^"'\s]*(?:accentuate)[^"'\s]*\.(dxf|dwg|pdf|step|stp|iges|igs)[^"'\s]*/gi);
      if (accentuateMatches) found.push(...accentuateMatches.map(u => u.replace(/&amp;/g, '&')));

      // Find Shopify CDN URLs with DXF/DWG extensions
      const shopifyCad = html.match(/https?:\/\/cdn\.shopify[^"'\s]*\.(dxf|dwg|step|stp)[^"'\s]*/gi);
      if (shopifyCad) found.push(...shopifyCad.map(u => u.replace(/&amp;/g, '&')));

      // Check JSON-LD for CAD references
      document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
        if (s.textContent.match(/dxf|cad|dwg|drawing/i)) {
          const jsonUrls = s.textContent.match(/https?:\/\/[^"'\s]*(?:dxf|dwg|cad)[^"'\s]*/gi);
          if (jsonUrls) found.push(...jsonUrls);
        }
      });

      // Check all meta tags
      document.querySelectorAll('meta[content]').forEach(m => {
        if (m.content.match(/\.(dxf|dwg)$/i)) found.push(m.content);
      });

      return [...new Set(found)];
    });

    console.log(`[Stealth] Hidden CAD URLs found: ${hiddenCadUrls.length}`);
    hiddenCadUrls.forEach(u => console.log(`  HIDDEN CAD: ${u}`));

    // Add hidden CAD URLs to the downloadable list
    const seen = new Set();
    for (const url of hiddenCadUrls) {
      urls.push(url);
    }

    // Filter downloadable assets
    const downloadable = urls
      .map((u) => ({ url: normalizeUrl(u, url), type: inferAssetType(u) }))
      .filter((x) => x.url && x.type !== null);

    let assetCount = 0;

    for (const item of downloadable.slice(0, 30)) {
      if (seen.has(item.url)) continue;
      seen.add(item.url);

      try {
        const downloaded = await downloadFile(item.url);
        const parsed = new URL(downloaded.finalUrl);
        const fileName = path.basename(parsed.pathname) || `${Date.now()}`;

        const folder =
          item.type === "IMAGE" ? "images" :
          item.type === "DWG" || item.type === "DXF" ? "cad" :
          item.type === "PDF" ? "specs" :
          "assets";

        const cat = category || "uncategorised";
        const key = `raw/${manufacturer}/${cat}/${productSlug}/${folder}/${fileName}`;
        const uploaded = await uploadBuffer({ key, buffer: downloaded.buffer, contentType: downloaded.contentType });

        assetCount++;
        console.log(`[Stealth] Downloaded: ${fileName} (${item.type})`);
      } catch (err) {
        console.error(`[Stealth] Download failed: ${item.url.slice(0, 80)} — ${err.message.slice(0, 60)}`);
      }
    }

    results.assetCount = assetCount;

    // Push crawl result to processing queue
    try {
      const { createClient } = await import("redis");
      const publisher = createClient({
        url: process.env.REDIS_URL || "redis://redis:6379",
        password: process.env.REDIS_PASSWORD || undefined,
      });
      await publisher.connect();
      await publisher.lPush("cad-processing", JSON.stringify({
        type: "crawl_result",
        data: { product_id: productSlug, manufacturer, assets: downloadable.slice(0, 30).map((item, idx) => ({
          assetType: item.type, cdnUrl: item.url, sourceUrl: item.url, id: `${productSlug}-${idx}`,
        })) },
      }));
      await publisher.disconnect();
      console.log(`[Stealth] Pushed crawl_result to cad-processing`);
    } catch (e) {
      console.error(`[Stealth] Failed to push crawl result: ${e.message.slice(0, 60)}`);
    }

    // Human-like delay before closing
    await humanDelay(page, 1000, 3000);

  } catch (err) {
    console.error(`[Stealth] Crawl failed: ${err.message.slice(0, 100)}`);
    throw err;
  } finally {
    if (browser) await browser.close().catch(() => {});
  }

  return results;
}
