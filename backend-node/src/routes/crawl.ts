import { Router } from "express";
import { createClient } from "redis";
import crypto from "crypto";

export const crawlRouter = Router();

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";

/**
 * @openapi
 * /api/crawl:
 *   post:
 *     summary: Submit a product URL for crawling
 *     description: Pushes a crawl job to Redis. The crawler-worker scrapes the page, downloads CAD files and images, uploads to Spaces.
 *     tags: [Crawler]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [url, manufacturer]
 *             properties:
 *               url: { type: string, example: "https://www.jardan.com.au/products/pia-side-table" }
 *               manufacturer: { type: string, example: "jardan" }
 *               category: { type: string, example: "table" }
 *     responses:
 *       201:
 *         description: Crawl job queued
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 jobId: { type: string }
 *                 status: { type: string }
 *
 *   get:
 *     summary: Get crawl job status
 *     tags: [Crawler]
 *     parameters:
 *       - in: path
 *         name: jobId
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200:
 *         description: Job status
 * /api/crawl/{jobId}:
 *   get:
 *     summary: Check crawl job status
 *     tags: [Crawler]
 *     parameters:
 *       - in: path
 *         name: jobId
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200:
 *         description: Job status
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 jobId: { type: string }
 *                 status: { type: string, enum: [pending, queued, completed, failed] }
 */
crawlRouter.post("/", async (req, res) => {
  try {
    const { url, manufacturer, category } = req.body;

    if (!url || !manufacturer) {
      return res.status(400).json({
        error: "Missing required fields: url, manufacturer",
      });
    }

    // Validate URL
    try {
      new URL(url);
    } catch {
      return res.status(400).json({ error: "Invalid URL" });
    }

    const jobId = `crawl-${crypto.randomUUID().slice(0, 8)}-${Date.now()}`;

    const job = {
      jobId,
      url,
      manufacturer,
      category: category || null,
      createdAt: new Date().toISOString(),
    };

    // Push to Redis queue
    const client = createClient({ url: REDIS_URL, password: process.env.REDIS_PASSWORD || undefined });
    client.on("error", (err) => console.error("[Redis] Error:", err.message));
    await client.connect();
    await client.lPush("crawler:jobs", JSON.stringify(job));
    await client.disconnect();

    console.log(`[Crawl] Job ${jobId} created for ${url}`);

    res.status(201).json({
      jobId,
      status: "queued",
      message: `Crawl job created for ${manufacturer}`,
    });
  } catch (err: any) {
    console.error("[Crawl] Error:", err.message);
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /crawl/:jobId
 * Check the status of a crawl job.
 */
crawlRouter.get("/:jobId", async (req, res) => {
  try {
    const { jobId } = req.params;

    // Check per-job result key
    const client = createClient({ url: REDIS_URL, password: process.env.REDIS_PASSWORD || undefined });
    client.on("error", (err) => console.error("[Redis] Error:", err.message));
    await client.connect();

    const raw = await client.get(`crawler:result:${jobId}`);
    const timeoutKey = await client.get(`crawler:timeout:${jobId}`);
    await client.disconnect();

    if (raw) {
      try {
        const result = JSON.parse(raw);
        return res.json({ jobId, ...result });
      } catch {
        // fall through
      }
    }

    // Check for timeout — job started but never completed within window
    if (timeoutKey === "1") {
      return res.json({ jobId, status: "timed_out", message: "Crawl did not complete within the allowed time" });
    }

    res.json({ jobId, status: "pending" });
  } catch (err: any) {
    console.error("[Crawl] Status error:", err.message);
    res.status(500).json({ error: err.message });
  }
});
