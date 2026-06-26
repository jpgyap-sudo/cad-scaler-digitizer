# Assistant Monitor Worker

A VPS-deployed autonomous monitoring agent for the CAD Drawing Assistant. It continuously tracks performance, analyzes error patterns, and generates actionable improvement recommendations.

## Purpose

The monitor worker ensures the Drawing Assistant gets better over time by:
1. **Tracking everything** — every chat, task, decision, and tool call is logged to PostgreSQL
2. **Auto-diagnosing problems** — error pattern analysis, performance regression detection, confidence monitoring
3. **Generating recommendations** — data-backed suggestions for accuracy, performance, and UX improvements
4. **Health reporting** — real-time health status accessible via API

## Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│  FastAPI Backend    │────▶│  PostgreSQL      │◀────│  Monitor Worker      │
│  + Middleware       │     │  Monitoring DB   │     │  (assistant_monitor) │
│                     │     │  6 tables        │     │                      │
│  Auto-logs every    │     │                  │     │  Aggregates metrics  │
│  request/tool/      │     │                  │     │  Analyzes patterns   │
│  decision via       │     │                  │     │  Generates recs      │
│  middleware         │     │                  │     │                      │
└─────────────────────┘     └──────────────────┘     └──────────────────────┘
                                                              │
                                                              ▼
                                                   ┌──────────────────┐
                                                   │  Improvement    │
                                                   │  Recommendations│
                                                   │  (prioritized)  │
                                                   └──────────────────┘
```

## Monitoring Tables

| Table | Purpose |
|-------|---------|
| `assistant_chat_log` | Every user↔assistant message exchange |
| `assistant_task_log` | Every operation (digitize, adjust, chat, etc.) |
| `assistant_decision_log` | Every AI decision with confidence & rationale |
| `assistant_tool_log` | Every internal tool/function call |
| `assistant_performance_metrics` | Daily aggregated stats |
| `assistant_improvement_recommendations` | Auto-generated improvement ideas |

## How the Monitor Generates Recommendations

The worker runs analysis cycles every 6 hours, examining:

### 1. Error Pattern Analysis
- Groups failed tasks by type and error message
- If a task type fails ≥ 3 times in 7 days → **high-impact recommendation**
- Example: *"High failure rate in digitize — OCR processing failed 5 times"*

### 2. Performance Trend Analysis
- Compares first-half vs second-half error rates
- Detects response time degradation (>30% increase → recommendation)
- Example: *"Error rate increasing — response time up 45%"*

### 3. Confidence Trend Analysis
- Averages decision confidence by type
- Any type averaging < 60% confidence with ≥ 3 samples → **high-accuracy recommendation**
- Example: *"Low confidence in dimension_association (0.45) — needs improvement"*

### 4. Usage Pattern Analysis
- Tracks Ollama fallback ratio (>50% → OpenAI config issue)
- Identifies most-used furniture types for prioritization
- Example: *"Heavy Ollama fallback (72%) — check OpenAI API key"*

## API Endpoints

The monitor exposes these endpoints via the main API:

| Endpoint | Description |
|----------|-------------|
| `GET /api/monitor/dashboard?days=7` | Full performance dashboard |
| `GET /api/monitor/stats` | Quick summary stats |
| `GET /api/monitor/chats` | Recent chat logs |
| `GET /api/monitor/tasks` | Recent task logs |
| `GET /api/monitor/decisions` | Recent decision logs |
| `GET /api/monitor/recommendations` | Open improvement recommendations |
| `POST /api/monitor/recommendations/{id}/status` | Update recommendation status |
| `POST /api/monitor/metrics/refresh` | Force daily metric aggregation |

## Deployment

The monitor runs as a separate Docker service:

```yaml
monitor:
  build:
    context: .
    dockerfile: Dockerfile.api  # Same image, different command
  container_name: cad-digitizer-monitor
  command: python -m app.monitoring.assistant_monitor
  environment:
    - MONITOR_POLL_INTERVAL=300
    - MONITOR_AGGREGATE_INTERVAL=3600
    - MONITOR_ANALYSIS_INTERVAL=21600
  depends_on:
    api:
      condition: service_healthy
  restart: unless-stopped
```

## Checking Monitor Health

```bash
# Via API
curl http://localhost:8000/api/monitor/stats

# In worker logs
docker logs cad-digitizer-monitor --tail 20
```

## Interpreting Recommendations

Each recommendation has:
- **type**: accuracy | performance | ui | error | pattern
- **impact**: high | medium | low
- **effort**: high | medium | low
- **evidence**: JSON data supporting the recommendation

Prioritize `high` impact / `low` effort recommendations first.
