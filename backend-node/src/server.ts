import express from "express";
import { config } from "./config.js";
import { productReferencesRouter } from "./routes/productReferences.js";
import { crawlRouter } from "./routes/crawl.js";

const app = express();

app.use(express.json({ limit: "10mb" }));

// ---- Global auth middleware ----
// Protects all routes except /health.
// Expected header: x-api-key matching AUTH_TOKEN env var.
// If AUTH_TOKEN is not set, auth is disabled (dev mode).
const AUTH_TOKEN = process.env.AUTH_TOKEN || "";

app.use((req, res, next) => {
  // Allow health endpoints and CORS preflight without auth
  if (req.path === "/health" || req.path.startsWith("/health/") || req.method === "OPTIONS") {
    return next();
  }

  // If auth is configured, enforce it
  if (AUTH_TOKEN) {
    const apiKey = req.headers["x-api-key"] as string | undefined;
    if (!apiKey || apiKey !== AUTH_TOKEN) {
      return res.status(401).json({ error: "Unauthorized. Set x-api-key header." });
    }
  }

  next();
});

// ---- CORS ----
const allowedOrigins = (process.env.CORS_ORIGIN || "").split(",").filter(Boolean);
app.use((_req, res, next) => {
  // In production behind Nginx, CORS is handled by Nginx.
  // These headers are for direct-access scenarios.
  if (allowedOrigins.length > 0) {
    res.setHeader("Access-Control-Allow-Origin", allowedOrigins.join(", "));
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, x-api-key");
    if (_req.method === "OPTIONS") {
      return res.sendStatus(204);
    }
  }
  next();
});

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "cad-reference-backend", auth: AUTH_TOKEN ? "enabled" : "disabled" });
});

app.use("/api/product-references", productReferencesRouter);
app.use("/api/crawl", crawlRouter);

// Redis health check
app.get("/api/health/redis", async (_req, res) => {
  try {
    const { createClient } = await import("redis");
    const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";
    // Use AUTH_PASSWORD if Redis password is set
    const client = createClient({ url: REDIS_URL, password: process.env.REDIS_PASSWORD || undefined });
    client.on("error", () => {});
    await client.connect();
    await client.ping();
    await client.disconnect();
    res.json({ status: "ok", redis: "connected" });
  } catch {
    res.json({ status: "degraded", redis: "disconnected" });
  }
});

app.listen(config.port, () => {
  console.log(`CAD reference backend running on http://localhost:${config.port}`);
  console.log(`Auth: ${AUTH_TOKEN ? "enabled" : "DISABLED (dev mode)"}`);
  console.log(`CORS origins: ${allowedOrigins.length > 0 ? allowedOrigins.join(", ") : "none (handled by Nginx)"}`);
});
