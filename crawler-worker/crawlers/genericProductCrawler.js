/**
 * Generic Product Page Crawler
 * =============================
 * Uses Crawlee + Playwright to visit a product page,
 * extract product info, find CAD/image asset links,
 * download them, upload to Spaces, and save metadata.
 *
 * Adapted from the reference library starter.
 */

import { PlaywrightCrawler, Dataset } from "crawlee";
import path from "path";
import axios from "axios";
import crypto from "crypto";

// S3-compatible storage (DigitalOcean Spaces)
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";

const SPACES_ENDPOINT = process.env.SPACES_ENDPOINT || "";
const SPACES_REGION = process.env.SPACES_REGION || "sgp1";
const SPACES_BUCKET = process.env.SPACES_BUCKET || "";
const SPACES_KEY = process.env.SPACES_KEY || "";
const SPACES_SECRET = process.env.SPACES_SECRET || "";
const SPACES_CDN_BASE = process.env.SPACES_CDN_BASE || "";

let s3Client = null;

function getS3() {
  if (!s3Client && SPACES_ENDPOINT && SPACES_KEY) {
    s3Client = new S3Client({
      endpoint: SPACES_ENDPOINT,
      region: SPACES_REGION,
      credentials: {
        accessKeyId: SPACES_KEY,
        secretAccessKey: SPACES_SECRET,
      },
    });
  }
  return s3Client;
}

function getCdnUrl(spaceKey) {
  if (!SPACES_CDN_BASE) return null;
  return `${SPACES_CDN_BASE.replace(/\/$/, "")}/${spaceKey}`;
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
      "User-Agent": "HomeU CAD Reference Bot/1.0",
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
  if (!s3) {
    // Local fallback
    const fs = await import("fs");
    const dir = path.dirname(key);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(key, buffer);
    return {
      spaceKey: key,
      cdnUrl: `/local/${key}`,
      fileHash: crypto.createHash("sha256").update(buffer).digest("hex"),
      mimeType: contentType || "application/octet-stream",
    };
  }

  const mime = contentType || "application/octet-stream";
  await s3.send(
    new PutObjectCommand({
      Bucket: SPACES_BUCKET,
      Key: key,
      Body: buffer,
      ACL: "public-read",
      ContentType: mime,
    })
  );

  return {
    spaceKey: key,
    cdnUrl: getCdnUrl(key),
    fileHash: crypto.createHash("sha256").update(buffer).digest("hex"),
    mimeType: mime,
  };
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

/**
 * Main crawl function — called by the Redis worker.
 */
export async function genericProductCrawler(input) {
  const { url, manufacturer, category } = input;

  const results = {
    productName: null,
    productId: null,
    assetCount: 0,
  };

  const crawler = new PlaywrightCrawler({
    maxRequestsPerCrawl: 1,
    headless: true,
    requestHandler: async ({ page, request }) => {
      await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => null);

      // Extract product name
      const title =
        (await page.locator("h1").first().textContent().catch(() => null)) ||
        (await page.title()) ||
        "unknown-product";

      const productName = title.trim().replace(/\s+/g, " ");
      const productSlug = slugify(`${manufacturer}-${productName}`);

      results.productName = productName;
      results.productId = productSlug;

      // Find all asset URLs on the page
      const urls = await page.evaluate(() => {
        const found = new Set();
        document.querySelectorAll("a[href]").forEach((a) => {
          if (a.href) found.add(a.href);
        });
        document.querySelectorAll("img[src]").forEach((img) => {
          if (img.src) found.add(img.src);
        });
        document.querySelectorAll("source[srcset]").forEach((source) => {
          source.srcset.split(",").forEach((part) => {
            const url = part.trim().split(" ")[0];
            if (url) found.add(url);
          });
        });
        return Array.from(found);
      });

      // Filter downloadable assets
      const downloadable = urls
        .map((u) => normalizeUrl(u, request.loadedUrl || request.url))
        .filter(Boolean)
        .map((u) => ({ url: u, type: inferAssetType(u) }))
        .filter((x) => x.type !== null);

      const seen = new Set();
      let assetCount = 0;

      for (const item of downloadable.slice(0, 50)) {
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

          const key = `raw/${manufacturer}/${productSlug}/${folder}/${fileName}`;
          const uploaded = await uploadBuffer({
            key,
            buffer: downloaded.buffer,
            contentType: downloaded.contentType,
          });

          assetCount++;
          console.log(`[Crawler] Downloaded: ${fileName} (${item.type})`);
        } catch (err) {
          console.error(`[Crawler] Download failed: ${item.url} — ${err.message}`);
        }
      }

      results.assetCount = assetCount;

      // Save crawl data
      await Dataset.pushData({
        productId: productSlug,
        productName,
        manufacturer,
        url: request.loadedUrl || request.url,
        assetCount,
        timestamp: new Date().toISOString(),
      });

      // Push crawl result to the processing queue for DXF parsing and Qdrant indexing
      try {
        const { createClient } = await import("redis");
        const REDIS_PASSWORD = process.env.REDIS_PASSWORD || undefined;
        const publisher = createClient({
          url: process.env.REDIS_URL || "redis://redis:6379",
          password: REDIS_PASSWORD,
        });
        await publisher.connect();
        await publisher.lPush("cad-processing", JSON.stringify({
          type: "crawl_result",
          data: {
            product_id: productSlug,
            manufacturer: input.manufacturer,
            assets: downloadable.slice(0, 50).map((item, idx) => ({
              assetType: item.type,
              cdnUrl: item.url,
              sourceUrl: item.url,
              id: `${productSlug}-${idx}`,
            })),
          },
        }));
        await publisher.disconnect();
        console.log(`[Crawler] Pushed crawl_result to cad-processing for ${productSlug}`);
      } catch (e) {
        console.error("[Crawler] Failed to push crawl result:", e.message);
      }
    },

    // Error handling
    failedRequestHandler({ request, error }) {
      console.error(`[Crawler] Request ${request.url} failed:`, error.message);
    },
  });

  await crawler.run([url]);
  return results;
}
