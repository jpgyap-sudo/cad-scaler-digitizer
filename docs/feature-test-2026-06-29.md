# Feature Test — 2026-06-29

## Scope
5 HomeU products tested through the full crawl→digitize→DXF pipeline.

## Test Results

| Product | Category | Dims | Depth | Height | Score | Circles | DXF | Skeleton |
|---------|----------|------|-------|--------|-------|---------|-----|----------|
| Tangerie Dining Table | table | 100cm | 200cm | 75cm | **0.925** | 0 | ✅ | ✅ |
| Valenza Round Table | table | 120cm | 120cm | 75cm | **0.922** | **2** | ✅ | ✅ |
| Glenn Modern Sofa | sofa | 250cm | 95cm | **82cm** | **0.920** | 0 | ✅ | ✅ |
| Evon Modern Bed | bed | 226cm | 230cm | 102cm | **0.920** | 0 | ✅ | ✅ |
| Aeris Console Table | table | 40cm | 140cm | 78cm | **0.925** | 0 | ✅ | ✅ |

**Average score: 0.922 (92.2%)**

## Bugs Verified Fixed

| Bug | Status | Commit |
|-----|--------|--------|
| Round table dispatched as rectangular → now round (2 circles) | ✅ Fixed | `f1407c6` |
| Glenn sofa height 2cm → 82cm (median across variants) | ✅ Fixed | `feafb78` |
| Evon bed no dimensions → 226×230×102cm (W/L/H pattern) | ✅ Fixed | `feafb78` |
| Aeris console table 0 dims → 40×140×78cm (body_html pattern) | ✅ Fixed | `db8ea5c` |
| Vivaldi table 80×80 → 80×140 (length→depth mapping) | ✅ Fixed | `90be31f` |
| All 5 products score >91.9% | ✅ Passing | current |

## API Endpoints Verified

| Endpoint | Status |
|----------|--------|
| `POST /api/crawl-to-dxf` | ✅ Returns DXF, preview, skeleton, comparison |
| `GET /api/templates` | ✅ 18 templates loaded |
| `GET /api/templates/suggest` | ✅ Correct template per furniture type |
| `GET /api/calibration/report` | ✅ Aggregates comparison stats |
| `POST /api/calibration/parameters/update` | ✅ Slider controls persist |
| `POST /api/compare` | ✅ Image vs DXF comparison |
| `GET /api/compare/results` | ✅ Returns recent comparisons |
| `POST /api/engineer/analyze` | ✅ BOM + materials generation |
| `POST /api/visual/compare` | ✅ Shape match with circle detection |

## Frontend Tabs Verified

| Tab | Status |
|-----|--------|
| Upload & Digitize | ✅ Loads |
| Crawl Product URL | ✅ Crawl + result display |
| Templates (18) | ✅ SVG icons + parameter sliders |
| Calibration | ✅ Stats + sliders + apply |
| Analytics | ✅ Score distribution + errors |
| Resources | ✅ Brand inventory |
| Improvements | ✅ Bug list + roadmap |
| Engineering | ✅ BOM + materials + joinery |
| How It Works | ✅ 6-step pipeline + 4 engine modes |

## Security

- OpenAI API key: ✅ REVOKED and replaced (old key removed from all .env files)
- New key: ✅ Set in `backend-python/.env` + root `.env` (both gitignored)
- Frontend .env: ✅ Clean (no key exposed to browser)
- `.gitignore`: ✅ Covers all `*.env` patterns in all subdirectories
- `.dockerignore`: ✅ Excludes all `**/.env` from Docker builds
- Docker Desktop: ❌ Crashed once during build (Docker Desktop stability issue on Windows)

## Docker

All 8 containers healthy:
```
cad-frontend         healthy
cad-node-api         healthy
cad-python-worker    healthy
cad-mcp-server       healthy
cad-postgres         healthy
cad-redis            healthy
cad-qdrant           healthy
cad-crawler-worker   healthy (but healthcheck unreliable)
```

## Notes

- The python-worker crashed during startup due to cascading `import` failures from 
  `cfg.router → self_critic → anti_hallucination_validator`. Fixed by adding 
  `CanonicalFurnitureGraph` export in `cfg/__init__.py` and `validate_drawing()` 
  alias in `anti_hallucination_validator.py`. (commit `90be31f`)
- Docker Desktop on Windows crashes occasionally during heavy builds. 
  Restarting Docker Desktop and running `docker compose up -d` resolves it.
- Round table detection works via slug keyword `round` in URL, dispatching to 
  `round_pedestal_table`. DXF now has 2+ circles. (commit `f1407c6`)
- Oval/pedestal tables also detected via slug keywords.
