"""
CAD Scaler Digitizer — Python FastAPI Backend
Entry point using modular router pattern.
"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
        from fastapi.responses import JSONResponse
        return JSONResponse({"events": parsed, "count": len(parsed)})
    except Exception as e:
        return JSONResponse({"events": [], "error": str(e)})
