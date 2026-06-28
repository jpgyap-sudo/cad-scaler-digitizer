/**
 * CAD Digitizer MCP Server
 * ==========================
 * Exposes 15 tools for ChatGPT to control the CAD Scaler Digitizer.
 * Supports both stdio transport (ChatGPT Desktop) and SSE transport (web/Docker).
 *
 * Usage:
 *   node server.js              # stdio mode (ChatGPT Desktop)
 *   node server.js --sse        # SSE mode (Docker container, listens on :3003)
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import axios from "axios";
import http from "http";
import { randomBytes } from "crypto";

// ── Configuration ──────────────────────────────────────────────────
const PY_API = process.env.PYTHON_WORKER_URL || "http://python-worker:8001";
const NODE_API = process.env.NODE_API_URL || "http://node-api:4000";
const PORT = parseInt(process.env.MCP_PORT || "3003");
const USE_SSE = process.argv.includes("--sse") || process.env.MCP_TRANSPORT === "sse";

// ── Helpers ────────────────────────────────────────────────────────
async function post(url, data) {
  try {
    const res = await axios.post(url, data, { timeout: 120000 });
    return res.data;
  } catch (err) {
    const detail = err.response?.data || err.message;
    return { error: typeof detail === "string" ? detail : JSON.stringify(detail) };
  }
}

async function get(url) {
  try {
    const res = await axios.get(url, { timeout: 30000 });
    return res.data;
  } catch (err) {
    const detail = err.response?.data || err.message;
    return { error: typeof detail === "string" ? detail : JSON.stringify(detail) };
  }
}

const TOOL_DEFS = [
  {
    name: "crawl_product_url",
    description: "Crawl a product page URL → extract photo → discover dimensions → generate DXF → validate. One-call pipeline.",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "Product page URL" },
        category: { type: "string", description: "furniture type: table, sofa, chair, bed, cabinet, lighting", default: "table" },
      },
      required: ["url"],
    },
  },
  {
    name: "batch_crawl",
    description: "Crawl multiple product URLs and return DXF + validation for each.",
    inputSchema: {
      type: "object",
      properties: {
        urls: { type: "array", items: { type: "string" } },
        category: { type: "string", default: "table" },
      },
      required: ["urls"],
    },
  },
  {
    name: "list_templates",
    description: "List all 18 engineering templates with parameter ranges, grouped by family.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "suggest_template",
    description: "Suggest best template for detected dimensions. Returns template name, parameters in mm, and confidence.",
    inputSchema: {
      type: "object",
      properties: {
        furniture_type: { type: "string", description: "rectangular_table, round_pedestal_table, sofa, dining_chair, bed, desk, console_table" },
        width_cm: { type: "number" }, height_cm: { type: "number" }, depth_cm: { type: "number" },
      },
      required: ["furniture_type"],
    },
  },
  {
    name: "validate_dimensions",
    description: "Run hallucination verifier on detected dimensions. Returns VERIFIED/ESTIMATED/HALLUCINATION per dimension.",
    inputSchema: {
      type: "object",
      properties: {
        furniture_type: { type: "string" },
        detected_dims: { type: "object", description: "{width_cm, overall_height_cm, depth_cm}" },
      },
      required: ["furniture_type", "detected_dims"],
    },
  },
  {
    name: "compare_digitization",
    description: "Compare product photo vs generated DXF. Returns edge overlap, entity match, dimension deviation scores.",
    inputSchema: {
      type: "object",
      properties: {
        image_url: { type: "string", description: "Original product image URL" },
        dxf_path: { type: "string", description: "Path to generated DXF" },
        page_dimensions: { type: "object", description: "{width_cm, overall_height_cm} from product page" },
      },
      required: ["image_url", "dxf_path"],
    },
  },
  {
    name: "get_calibration_report",
    description: "Get error distribution, systematic biases, and recommended correction hints from all comparisons.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "apply_corrections",
    description: "Auto-apply high-confidence correction hints. Adjusts digitizer parameters from accumulated errors.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "update_parameter",
    description: "Manually set a digitizer parameter. Common: canny_low (10-150), canny_high (50-400), min_contour_area (5-200).",
    inputSchema: {
      type: "object",
      properties: {
        param_key: { type: "string", description: "Parameter name" },
        param_value: { type: "number", description: "New value" },
      },
      required: ["param_key", "param_value"],
    },
  },
  {
    name: "get_current_parameters",
    description: "Get current digitizer parameters: Canny thresholds, contour area, scale corrections, OCR confidence.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "get_comparison_results",
    description: "List recent validation comparisons with scores and error counts.",
    inputSchema: { type: "object", properties: { limit: { type: "number", default: 20 } } },
  },
  {
    name: "get_analytics",
    description: "Full analytics: comparison stats, score distribution, biases, parameter state.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "cleanup_old_comparisons",
    description: "Delete comparison results older than N days.",
    inputSchema: { type: "object", properties: { days: { type: "number", default: 90 } } },
  },
  {
    name: "engineering_analyze",
    description: "Reverse-engineer a furniture product. Returns complete engineering analysis with bill of materials, materials, joinery, structural analysis, and CAD layer recommendations. Provide product_id, furniture_type, and optional page_dimensions.",
    inputSchema: {
      type: "object",
      properties: {
        product_id: { type: "string", description: "Product identifier" },
        furniture_type: { type: "string", description: "dining_table, sofa, coffee_table, desk, cabinet, chair, bed, armchair" },
        page_dimensions: { type: "object", description: "{width_cm, depth_cm, overall_height_cm} from product page" },
        detected_dimensions: { type: "object", description: "Detected dimensions from digitizer" },
      },
      required: ["product_id", "furniture_type"],
    },
  },
  {
    name: "list_engineering_families",
    description: "List all furniture families and types with engineering specifications.",
    inputSchema: { type: "object", properties: {} },
  },
];

const TOOL_HANDLERS = {
  async crawl_product_url(args) {
    return post(`${PY_API}/api/crawl-to-dxf`, { url: args.url, category: args.category || "table" });
  },
  async batch_crawl(args) {
    const results = [];
    for (const url of args.urls) {
      const r = await post(`${PY_API}/api/crawl-to-dxf`, { url, category: args.category || "table" });
      results.push({ url, status: r.status, dims: r.page_dimensions, score: r.comparison?.overall_score, dxf: !!r.dxf_file });
    }
    return { batch_results: results, total: results.length, succeeded: results.filter(r => r.status === "completed").length };
  },
  async list_templates() { return get(`${PY_API}/api/templates`); },
  async suggest_template(args) {
    const p = new URLSearchParams({ furniture_type: args.furniture_type });
    if (args.width_cm) p.set("width_cm", args.width_cm);
    if (args.height_cm) p.set("height_cm", args.height_cm);
    if (args.depth_cm) p.set("depth_cm", args.depth_cm);
    return get(`${PY_API}/api/templates/suggest?${p.toString()}`);
  },
  async validate_dimensions(args) {
    return post(`${PY_API}/api/verify`, { product_id: "mcp-request", furniture_type: args.furniture_type, detected_dims: args.detected_dims });
  },
  async compare_digitization(args) {
    return post(`${PY_API}/api/compare`, { job_id: `mcp-${Date.now()}`, product_id: "mcp-compare", image_url: args.image_url, dxf_path: args.dxf_path, page_dimensions: args.page_dimensions });
  },
  async get_calibration_report() { return get(`${PY_API}/api/calibration/report`); },
  async apply_corrections() { return post(`${PY_API}/api/calibration/apply`, {}); },
  async update_parameter(args) { return post(`${PY_API}/api/calibration/parameters/update`, { param_key: args.param_key, param_value: args.param_value }); },
  async get_current_parameters() { return get(`${PY_API}/api/calibration/parameters`); },
  async get_comparison_results(args) { return get(`${PY_API}/api/compare/results?limit=${args.limit || 20}`); },
  async get_analytics() {
    const [cal, paramsList] = await Promise.all([get(`${PY_API}/api/calibration/report`), get(`${PY_API}/api/calibration/parameters`)]);
    return { comparison_stats: cal.comparison_stats, systematic_biases: cal.systematic_biases, correction_hints: cal.correction_hints?.length || 0, current_parameters: paramsList };
  },
  async cleanup_old_comparisons(args) { return post(`${PY_API}/api/calibration/cleanup`, { days: args.days || 90 }); },
  async engineering_analyze(args) { return post(`${PY_API}/api/engineer/analyze`, { product_id: args.product_id, furniture_type: args.furniture_type, page_dimensions: args.page_dimensions, detected_dimensions: args.detected_dimensions }); },
  async list_engineering_families() { return get(`${PY_API}/api/engineer/families`); },
};

// ── Create MCP Server ──────────────────────────────────────────────
const server = new Server({ name: "cad-digitizer-mcp", version: "1.0.0" }, { capabilities: { tools: {} } });

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOL_DEFS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const handler = TOOL_HANDLERS[name];
  if (!handler) throw new Error(`Unknown tool: ${name}`);
  try {
    const result = await handler(args || {});
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  } catch (err) {
    return { content: [{ type: "text", text: `Error: ${err.message}` }], isError: true };
  }
});

// ── SSE Transport (Docker / web) ───────────────────────────────────
function startSSEServer() {
  const clients = new Map();
  const httpx_server = http.createServer(async (req, res) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");

    if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }

    const url = new URL(req.url, `http://localhost:${PORT}`);

    // Health endpoint
    if (url.pathname === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, server: "cad-digitizer-mcp", transport: "sse", tools: TOOL_DEFS.length }));
      return;
    }

    // SSE endpoint — MCP client connects here
    if (url.pathname === "/sse") {
      const sessionId = randomBytes(8).toString("hex");
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
        "Access-Control-Allow-Origin": "*",
      });

      res.write(`event: endpoint\ndata: /messages?sessionId=${sessionId}\n\n`);
      clients.set(sessionId, res);

      req.on("close", () => { clients.delete(sessionId); });
      return;
    }

    // Message endpoint — client posts tool calls here
    if (url.pathname === "/messages" && req.method === "POST") {
      const sessionId = url.searchParams.get("sessionId");
      const clientRes = clients.get(sessionId);
      if (!clientRes) { res.writeHead(404); res.end("Session not found"); return; }

      let body = "";
      req.on("data", (chunk) => body += chunk);
      req.on("end", async () => {
        try {
          const message = JSON.parse(body);
          // Forward to MCP server via temporary stdio transport
          // We use the standard MCP SDK's SSE Server transport here
          // For simplicity, handle tool calls directly:
          if (message.method === "tools/list") {
            clientRes.write(`data: ${JSON.stringify({ id: message.id, result: { tools: TOOL_DEFS } })}\n\n`);
          } else if (message.method === "tools/call") {
            const handler = TOOL_HANDLERS[message.params.name];
            if (!handler) {
              clientRes.write(`data: ${JSON.stringify({ id: message.id, error: { code: -32601, message: `Unknown tool: ${message.params.name}` } })}\n\n`);
            } else {
              try {
                const result = await handler(message.params.arguments || {});
                clientRes.write(`data: ${JSON.stringify({ id: message.id, result: { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] } })}\n\n`);
              } catch (err) {
                clientRes.write(`data: ${JSON.stringify({ id: message.id, error: { code: -32603, message: err.message } })}\n\n`);
              }
            }
          } else {
            clientRes.write(`data: ${JSON.stringify({ id: message.id, error: { code: -32601, message: `Method not supported: ${message.method}` } })}\n\n`);
          }
          res.writeHead(202, { "Content-Type": "application/json" }); res.end();
        } catch (e) {
          res.writeHead(400, { "Content-Type": "text/plain" }); res.end(`Bad request: ${e.message}`);
        }
      });
      return;
    }

    res.writeHead(404); res.end("Not found");
  });

  httpx_server.listen(PORT, "0.0.0.0", () => {
    console.error(`MCP SSE server listening on http://0.0.0.0:${PORT}`);
    console.error(`  Health:     http://localhost:${PORT}/health`);
    console.error(`  SSE URL:    http://localhost:${PORT}/sse`);
    console.error(`  Tools:      ${TOOL_DEFS.length} registered`);
  });
}

// ── Start ──────────────────────────────────────────────────────────
async function main() {
  if (USE_SSE) {
    startSSEServer();
  } else {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("CAD Digitizer MCP Server running on stdio — connect via ChatGPT Desktop");
  }
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
