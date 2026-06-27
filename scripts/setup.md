# CAD Scaler Digitizer — Docker Setup

## Quick Start

```bash
# 1. Start everything
docker compose up -d

# 2. Check status
docker compose ps

# 3. View logs
docker compose logs -f
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 8080 | React/Vite UI (served by Nginx) |
| Node API | 4000 | Express + Prisma API + Session management |
| Python Worker | 8001 | FastAPI CAD engine (OpenCV, OCR, ezdxf) |
| Crawler Worker | — | Crawlee + Playwright (Redis queue consumer) |
| Postgres | 5432 | Metadata, sessions, jobs |
| Redis | 6379 | Job queue + pub/sub |
| Qdrant | 6333 | Vector similarity search |

## Architecture Flow

```
User uploads image
       ↓
  Frontend (React)
       ↓ Nginx proxy
  Node API (/api/digitize)
       ↓
  Creates job → Redis queue ('cad-processing')
       ↓
  Python Worker consumes job
       ↓
  OpenCV → OCR → Furniture Classify → Scale → DXF
       ↓
  Saves DXF → Saves metadata in Postgres
       ↓
  Indexes geometry in Qdrant (vector search)
       ↓
  Publishes result via Redis pub/sub
       ↓
  Frontend shows result in real-time
```

## Crawler Usage

Submit a crawl job via the Node API:

```bash
curl -X POST http://localhost:4000/api/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/product-page",
    "manufacturer": "jardan",
    "category": "table"
  }'
```

## Environment

Edit `.env` to configure:
- DigitalOcean Spaces (S3-compatible storage)
- OpenAI API key (optional, for AI-enhanced detection)
- Database credentials
