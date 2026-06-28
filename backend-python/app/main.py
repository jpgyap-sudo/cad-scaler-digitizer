"""
CAD Scaler Digitizer — Python FastAPI Backend
Entry point using modular router pattern.
"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load .env
_env_path = Path(__file__).parent.parent / '.env'
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                if not os.environ.get(_k):
                    os.environ[_k] = _v.strip().strip('"').strip("'")

from app.api.routes import router
from app.furniture_intelligence.api.routes import router as fi_router
from app.monitoring.middleware import MonitoringMiddleware

app = FastAPI(title="AI Furniture CAD Digitizer", version="2.0.0")

# Add monitoring middleware to auto-log all requests
app.add_middleware(MonitoringMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(router, prefix="/py-api")  # Vite dev proxy compatibility
app.include_router(fi_router, prefix="/api")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

@app.get("/health")
def health():
    return {"ok": True, "engine": "opencv+ocr+ezdxf+v2", "version": "2.0.0", "hybrid": bool(OPENAI_API_KEY)}

@app.get("/api/progress")
def progress(limit: int = 50):
    """Get recent progress events buffered in Redis."""
    try:
        import redis as redis_lib
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        redis_pass = os.environ.get("REDIS_PASSWORD") or None
        client = redis_lib.from_url(redis_url, decode_responses=True, password=redis_pass)
        events = client.lRange("progress:buffer", 0, limit - 1)
        parsed = []
        for e in events:
            try:
                parsed.append(json.loads(e))
            except json.JSONDecodeError:
                parsed.append({"raw": e})
        return JSONResponse({"events": parsed, "count": len(parsed)})
    except Exception as e:
        return JSONResponse({"events": [], "error": str(e)})


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    # Pre-warm the drawing model cache
    try:
        from app.backend.drawing_builders import build_round_pedestal_model
        build_round_pedestal_model()
    except Exception as e:
        print(f"[Startup] Drawing model cache warm failed: {e}")

    # Initialize Qdrant geometry embedding collection for reference library
    try:
        from app.services.embedding_service import init_collection
        init_collection()
        print("[Startup] Qdrant CAD geometry collection initialized")
    except Exception as e:
        print(f"[Startup] Qdrant init failed (non-fatal): {e}")

    # Initialize Resource Engine database (SQLite/Postgres for feedback + scenes)
    try:
        from app.resource_engine.db_persistence import init_db
        init_db()
        print("[Startup] Resource Engine database initialized")
    except Exception as e:
        print(f"[Startup] Resource Engine DB init failed (non-fatal): {e}")
