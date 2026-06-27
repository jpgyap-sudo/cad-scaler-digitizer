import { Router } from "express";
import { createClient } from "redis";
import crypto from "crypto";

export const crawlRouter = Router();

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";

/**
 * POST /crawl
 * Creates a crawl job and pushes it to the Redis queue.
 * The crawler-worker picks it up and processes it.
 *
 * Body: { url: string, manufacturer: string, category?: string }
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
    const client = createClient({ url: REDIS_URL, password: process.env.REDIS_PASSWORD || undefined });
    client.on("error", (err) => console.error("[Redis] Error:", err.message));
    await client.connect();

    // Check per-job result key
    const client = createClient({ url: REDIS_URL, password: process.env.REDIS_PASSWORD || undefined });
    client.on("error", (err) => console.error("[Redis] Error:", err.message));
    await client.connect();

    const raw = await client.get(`crawler:result:${jobId}`);
    await client.disconnect();

    if (raw) {
      try {
        const result = JSON.parse(raw);
        return res.json({ jobId, ...result });
      } catch {
        // fall through to pending
      }
    }

    res.json({ jobId, status: "pending" });
  } catch (err: any) {
    console.error("[Crawl] Status error:", err.message);
    res.status(500).json({ error: err.message });
  }
});
