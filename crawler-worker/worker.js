/**
 * Crawler Worker — Redis Queue Consumer
 * =======================================
 * Listens on the Redis 'crawler:jobs' queue for crawl requests.
 * When a job arrives, it runs the Crawlee/Playwright crawler
 * on the given product URL, extracts CAD/assets links,
 * downloads them, uploads to Spaces, and saves metadata.
 *
 * Runs as a long-lived daemon inside Docker.
 */

import { createClient } from "redis";
import { genericProductCrawler } from "./crawlers/genericProductCrawler.js";

// Configuration
const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";
const REDIS_PASSWORD = process.env.REDIS_PASSWORD || undefined;
const QUEUE_NAME = "crawler:jobs";
const PROGRESS_CHANNEL = "cad:progress";

let redisClient;

async function connectRedis() {
  redisClient = createClient({ url: REDIS_URL, password: REDIS_PASSWORD });
  redisClient.on("error", (err) => {
    console.error("[Crawler Worker] Redis error:", err.message);
  });
  await redisClient.connect();
  console.log(`[Crawler Worker] Connected to Redis: ${REDIS_URL}`);
}

async function processJob(job) {
  const { jobId, url, manufacturer, category } = job;
  console.log(`[Crawler Worker] Processing job ${jobId}: ${url} [${manufacturer}]`);

  // Publish progress
  await redisClient.publish(PROGRESS_CHANNEL, JSON.stringify({
    job_id: jobId,
    type: "crawl",
    status: "started",
    url,
    manufacturer,
  }));

  try {
    // Run the crawler
    const result = await genericProductCrawler({
      url,
      manufacturer,
      category,
    });

    console.log(`[Crawler Worker] Job ${jobId} complete:`, result?.productName);

    // Store result in per-job key with 1h TTL (not unbounded list)
    await redisClient.setEx(`crawler:result:${jobId}`, 3600, JSON.stringify({
      jobId,
      status: "completed",
      productId: result?.productId,
      productName: result?.productName,
      assetCount: result?.assetCount,
      timestamp: new Date().toISOString(),
    }));

    // Publish progress
    await redisClient.publish(PROGRESS_CHANNEL, JSON.stringify({
      job_id: jobId,
      type: "crawl",
      status: "completed",
      url,
      productName: result?.productName,
    }));

    return result;
  } catch (error) {
    console.error(`[Crawler Worker] Job ${jobId} failed:`, error.message);

    // Store error in per-job key with 1h TTL
    await redisClient.setEx(`crawler:result:${jobId}`, 3600, JSON.stringify({
      jobId,
      status: "failed",
      error: error.message,
      url,
      timestamp: new Date().toISOString(),
    }));

    await redisClient.publish(PROGRESS_CHANNEL, JSON.stringify({
      job_id: jobId,
      type: "crawl",
      status: "failed",
      error: error.message,
    }));

    throw error;
  }
}

async function main() {
  await connectRedis();

  console.log(`[Crawler Worker] Listening on queue: ${QUEUE_NAME}`);

  // Start health endpoint
  startHealthServer();

  // Main loop: block on BRPOP for new jobs
  while (true) {
    try {
      const result = await redisClient.brPop(QUEUE_NAME, 5); // timeout 5s
      if (!result) continue;

      const rawJob = result.element;
      let job;
      try {
        job = JSON.parse(rawJob);
      } catch {
        console.error("[Crawler Worker] Invalid job JSON:", rawJob.substring(0, 200));
        continue;
      }

      // Process without awaiting — allow parallel crawling if multiple jobs arrive
      processJob(job).catch((err) => {
        console.error("[Crawler Worker] Unhandled job error:", err.message);
      });
    } catch (err) {
      if (err.message?.includes("connection") || err.code === "ECONNREFUSED") {
        console.error("[Crawler Worker] Redis connection lost, reconnecting in 5s...");
        await new Promise((r) => setTimeout(r, 5000));
        try { await redisClient.disconnect(); } catch {}
        await connectRedis();
      } else {
        console.error("[Crawler Worker] Loop error:", err.message);
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
  }
}

function startHealthServer() {
  import("http").then((http) => {
    const server = http.createServer((req, res) => {
      if (req.url === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, worker: "crawler" }));
      } else {
        res.writeHead(404);
        res.end();
      }
    });
    server.listen(3002, "0.0.0.0", () => {
      console.log("[Crawler Worker] Health endpoint on http://0.0.0.0:3002/health");
    });
  });
}

// Graceful shutdown
process.on("SIGTERM", async () => {
  console.log("[Crawler Worker] Shutting down...");
  try { await redisClient?.disconnect(); } catch {}
  process.exit(0);
});

process.on("SIGINT", async () => {
  console.log("[Crawler Worker] Interrupted...");
  try { await redisClient?.disconnect(); } catch {}
  process.exit(0);
});

main().catch((err) => {
  console.error("[Crawler Worker] Fatal:", err);
  process.exit(1);
});
