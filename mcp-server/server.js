/**
 * CAD Digitizer MCP Server
 * ==========================
 * Exposes tools for ChatGPT to control the CAD Scaler Digitizer.
 * Connects to the existing API endpoints and exposes them as MCP tools.
 *
 * Run: node server.js
 * Connect ChatGPT: mcp-servers.cad-digitizer-mcp.config.json
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";

// ── Configuration ──────────────────────────────────────────────────
const PY_API = process.env.PYTHON_WORKER_URL || "http://python-worker:8001";
const NODE_API = process.env.NODE_API_URL || "http://node-api:4000";

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

// ── MCP Server ─────────────────────────────────────────────────────
const server = new Server(
  { name: "cad-digitizer-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// ── List Tools ─────────────────────────────────────────────────────
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    // ── Product Crawling ──
    {
      name: "crawl_product_url",
      description: "Crawl a product page URL, extract the hero image, discover dimensions, digitize the photo, and return a DXF file with validation score.",
      inputSchema: {
        type: "object",
        properties: {
          url: { type: "string", description: "Product page URL to crawl (e.g., https://homeu.ph/products/tangerie-dining-table)" },
          category: { type: "string", description: "Furniture type: table, sofa, chair, bed, cabinet, lighting", default: "table" },
        },
        required: ["url"],
      },
    },
    {
      name: "batch_crawl",
      description: "Crawl multiple product URLs in sequence and return results for all.",
      inputSchema: {
        type: "object",
        properties: {
          urls: { type: "array", items: { type: "string" }, description: "Array of product page URLs" },
          category: { type: "string", default: "table" },
        },
        required: ["urls"],
      },
    },

    // ── Templates ──
    {
      name: "list_templates",
      description: "List all available engineering templates grouped by family. Returns template names, parameter ranges, and IDs.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "suggest_template",
      description: "Suggest the best engineering template for detected dimensions. Returns template name, resolved parameters in mm, and solved dimensions.",
      inputSchema: {
        type: "object",
        properties: {
          furniture_type: { type: "string", description: "Product type: rectangular_table, round_pedestal_table, sofa, dining_chair, bed, cabinet, desk, console_table" },
          width_cm: { type: "number", description: "Detected width in cm" },
          height_cm: { type: "number", description: "Detected height in cm" },
          depth_cm: { type: "number", description: "Detected depth in cm" },
        },
        required: ["furniture_type"],
      },
    },

    // ── Validation ──
    {
      name: "validate_dimensions",
      description: "Validate detected dimensions against reference geometry and physical bounds. Returns VERIFIED/ESTIMATED/HALLUCINATION verdicts per dimension.",
      inputSchema: {
        type: "object",
        properties: {
          furniture_type: { type: "string" },
          detected_dims: { type: "object", description: "Detected dimensions as {width_cm: value, overall_height_cm: value, depth_cm: value}" },
          reference_geometry: { type: "object", description: "Optional parsed DXF geometry as {bbox: {width, height}, counts: {entityCount}}" },
        },
        required: ["furniture_type", "detected_dims"],
      },
    },
    {
      name: "compare_digitization",
      description: "Compare a product photo against a generated DXF. Runs edge overlay, entity count, and dimension deviation checks. Returns a 0-1 accuracy score.",
      inputSchema: {
        type: "object",
        properties: {
          image_url: { type: "string", description: "URL of the original product image" },
          dxf_path: { type: "string", description: "Local path to the generated DXF file" },
          product_id: { type: "string" },
          page_dimensions: { type: "object", description: "Dimensions from product page as {width_cm, overall_height_cm}" },
        },
        required: ["image_url", "dxf_path"],
      },
    },

    // ── Calibration ──
    {
      name: "get_calibration_report",
      description: "Get calibration report showing comparison stats, error distribution, systematic biases, and recommended corrections.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "apply_corrections",
      description: "Auto-apply high-confidence correction hints from accumulated comparison errors. Adjusts digitizer parameters like Canny thresholds and scale factors.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "update_parameter",
      description: "Manually set a digitizer parameter. Takes effect on next digitize call. Common params: canny_low (10-150), canny_high (50-400), min_contour_area (5-200).",
      inputSchema: {
        type: "object",
        properties: {
          param_key: { type: "string", description: "Parameter name (e.g., canny_low, canny_high, min_contour_area)" },
          param_value: { type: "number", description: "New value" },
        },
        required: ["param_key", "param_value"],
      },
    },
    {
      name: "get_current_parameters",
      description: "Get current digitizer parameter values including Canny thresholds, contour area, scale corrections, and OCR confidence.",
      inputSchema: { type: "object", properties: {} },
    },

    // ── Analytics ──
    {
      name: "get_comparison_results",
      description: "List recent comparison results with scores, edge overlap, and error counts.",
      inputSchema: {
        type: "object",
        properties: {
          limit: { type: "number", default: 20 },
        },
      },
    },
    {
      name: "get_analytics",
      description: "Get analytics including comparison counts, score distribution, error breakdown, systematic biases, and current parameters.",
      inputSchema: { type: "object", properties: {} },
    },

    // ── Cleanup ──
    {
      name: "cleanup_old_comparisons",
      description: "Delete comparison results older than N days to free database space.",
      inputSchema: {
        type: "object",
        properties: {
          days: { type: "number", description: "Retention period in days", default: 90 },
        },
      },
    },
  ],
}));

// ── Call Tool Handler ──────────────────────────────────────────────
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result;

    switch (name) {
      // ── Crawl ──
      case "crawl_product_url":
        result = await post(`${PY_API}/api/crawl-to-dxf`, {
          url: args.url,
          category: args.category || "table",
        });
        break;

      case "batch_crawl":
        const results = [];
        for (const url of args.urls) {
          const r = await post(`${PY_API}/api/crawl-to-dxf`, {
            url,
            category: args.category || "table",
          });
          results.push({ url, status: r.status, dims: r.page_dimensions, score: r.comparison?.overall_score, dxf: !!r.dxf_file });
        }
        result = { batch_results: results, total: results.length, succeeded: results.filter(r => r.status === "completed").length };
        break;

      // ── Templates ──
      case "list_templates":
        result = await get(`${PY_API}/api/templates`);
        break;

      case "suggest_template":
        const params = new URLSearchParams({ furniture_type: args.furniture_type });
        if (args.width_cm) params.set("width_cm", args.width_cm);
        if (args.height_cm) params.set("height_cm", args.height_cm);
        if (args.depth_cm) params.set("depth_cm", args.depth_cm);
        result = await get(`${PY_API}/api/templates/suggest?${params.toString()}`);
        break;

      // ── Validation ──
      case "validate_dimensions":
        result = await post(`${PY_API}/api/verify`, {
          product_id: args.product_id || "mcp-request",
          furniture_type: args.furniture_type,
          detected_dims: args.detected_dims,
          reference_geometry: args.reference_geometry,
        });
        break;

      case "compare_digitization":
        result = await post(`${PY_API}/api/compare`, {
          job_id: args.job_id || `mcp-${Date.now()}`,
          product_id: args.product_id || "mcp-compare",
          image_url: args.image_url,
          dxf_path: args.dxf_path,
          page_dimensions: args.page_dimensions,
        });
        break;

      // ── Calibration ──
      case "get_calibration_report":
        result = await get(`${PY_API}/api/calibration/report`);
        break;

      case "apply_corrections":
        result = await post(`${PY_API}/api/calibration/apply`, {});
        break;

      case "update_parameter":
        result = await post(`${PY_API}/api/calibration/parameters/update`, {
          param_key: args.param_key,
          param_value: args.param_value,
        });
        break;

      case "get_current_parameters":
        result = await get(`${PY_API}/api/calibration/parameters`);
        break;

      // ── Analytics ──
      case "get_comparison_results":
        result = await get(`${PY_API}/api/compare/results?limit=${args.limit || 20}`);
        break;

      case "get_analytics":
        const [cal, paramsList, results] = await Promise.all([
          get(`${PY_API}/api/calibration/report`),
          get(`${PY_API}/api/calibration/parameters`),
          get(`${PY_API}/api/compare/results?limit=5`),
        ]);
        result = {
          comparison_stats: cal.comparison_stats,
          systematic_biases: cal.systematic_biases,
          correction_hints: cal.correction_hints?.length || 0,
          current_parameters: paramsList,
          recent_comparisons: results?.slice(0, 5) || [],
        };
        break;

      // ── Cleanup ──
      case "cleanup_old_comparisons":
        result = await post(`${PY_API}/api/calibration/cleanup`, { days: args.days || 90 });
        break;

      default:
        throw new Error(`Unknown tool: ${name}`);
    }

    // Format response for MCP
    const text = typeof result === "string" ? result : JSON.stringify(result, null, 2);
    return {
      content: [{ type: "text", text }],
    };
  } catch (err) {
    return {
      content: [{ type: "text", text: `Error: ${err.message}` }],
      isError: true,
    };
  }
});

// ── Start ──────────────────────────────────────────────────────────
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("CAD Digitizer MCP Server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
