# CAD Digitizer MCP Server — Install for ChatGPT

## What This Is

This MCP server exposes 15 tools that allow ChatGPT to control the CAD Scaler Digitizer:
- Crawl product URLs → generate DXF files
- List and suggest engineering templates
- Validate detected dimensions
- Compare photos against generated DXFs
- Monitor calibration and analytics
- Adjust digitizer parameters

## Setup for ChatGPT Desktop App

### Option 1: VPS / Remote (Docker)

The MCP server runs inside Docker as `cad-mcp-server`. For ChatGPT Desktop to reach it:

```json
// C:\Users\<user>\AppData\Roaming\Claude\claude_desktop_config.json
// or ChatGPT Desktop equivalent
{
  "mcpServers": {
    "cad-digitizer": {
      "command": "node",
      "args": ["/path/to/mcp-server/server.js"],
      "env": {
        "PYTHON_WORKER_URL": "http://python-worker:8001",
        "NODE_API_URL": "http://node-api:4000"
      }
    }
  }
}
```

### Option 2: Local Machine (Windows)

If Docker is running on the same machine as ChatGPT Desktop:

```json
{
  "mcpServers": {
    "cad-digitizer": {
      "command": "node",
      "args": ["C:\\cad-digitizer\\mcp-server\\server.js"],
      "env": {
        "PYTHON_WORKER_URL": "http://localhost:8001",
        "NODE_API_URL": "http://localhost:4000"
      }
    }
  }
}
```

## Available Tools (15)

| Tool | Description |
|------|-------------|
| `crawl_product_url` | Crawl a URL → extract photo + dimensions → generate DXF |
| `batch_crawl` | Crawl multiple URLs in sequence |
| `list_templates` | List all 18 engineering templates |
| `suggest_template` | Suggest template for given dimensions |
| `validate_dimensions` | Run hallucination verifier on detected dims |
| `compare_digitization` | Compare photo vs DXF (edge overlay + dims) |
| `get_calibration_report` | Get error distribution + correction hints |
| `apply_corrections` | Auto-apply high-confidence corrections |
| `update_parameter` | Manually set a digitizer parameter |
| `get_current_parameters` | Read current Canny/contour/scale settings |
| `get_comparison_results` | List recent validation results |
| `get_analytics` | Full analytics summary |
| `cleanup_old_comparisons` | Delete old comparison records |

## Example ChatGPT Prompts

> "Crawl https://homeu.ph/products/tangerie-dining-table and generate a DXF"

> "What templates are available for rectangular tables?"

> "Show me the calibration report and apply any corrections"

> "Compare the last 5 digitizations and show me the accuracy scores"

> "Set canny_low to 40 and canny_high to 130, then test the fatima sofa"
