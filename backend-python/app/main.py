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
from app.backend.cfg.router import router as cfg_router  # CFG / Grammar / SelfCritic endpoints

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
app.include_router(cfg_router)  # CFG endpoints at /api/cfg/*

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

    # Ensure auxiliary Postgres tables exist
    try:
        _init_postgres_tables()
    except Exception as e:
        print(f"[Startup] Postgres tables init failed (non-fatal): {e}")


def _init_postgres_tables():
    """Ensure auxiliary tables (drawing_history, assistant_task_log, comparison_results) exist in Postgres."""
    import psycopg2
    import os
    conn = psycopg2.connect(
        host=os.environ.get("PG_HOST", "postgres"),
        port=int(os.environ.get("PG_PORT", 5432)),
        dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
        user=os.environ.get("PG_USER", "postgres"),
        password=os.environ.get("PG_PASSWORD", "postgres"),
    )
    cur = conn.cursor()
    
    # 1. Create drawing_history
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drawing_history (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            furniture_type TEXT,
            dxf_file TEXT,
            quality_score FLOAT,
            entity_counts JSONB,
            dimensions_used JSONB,
            preview_urls JSONB,
            correction_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_drawings_session ON drawing_history(session_id);
        CREATE INDEX IF NOT EXISTS idx_drawings_type ON drawing_history(furniture_type);
    """)

    # 2. Create assistant_task_log
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assistant_task_log (
            id              SERIAL PRIMARY KEY,
            session_id      VARCHAR(100),
            task_type       VARCHAR(50) NOT NULL,
            furniture_type  VARCHAR(100),
            input_params    JSONB,
            output_summary  JSONB,
            success         BOOLEAN DEFAULT TRUE,
            error_message   TEXT,
            duration_ms     INTEGER,
            created_at      TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_task_log_session   ON assistant_task_log(session_id);
        CREATE INDEX IF NOT EXISTS idx_task_log_type      ON assistant_task_log(task_type);
        CREATE INDEX IF NOT EXISTS idx_task_log_created   ON assistant_task_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_task_log_success   ON assistant_task_log(success);
    """)
    
    # 3. Create comparison_results
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comparison_results (
            id SERIAL PRIMARY KEY,
            job_id TEXT UNIQUE NOT NULL,
            product_id TEXT,
            overall_score FLOAT NOT NULL DEFAULT 0.0,
            edge_overlap_score FLOAT DEFAULT 0.0,
            entity_match_score FLOAT DEFAULT 0.0,
            dimension_deviation_pct FLOAT DEFAULT 0.0,
            errors_json JSONB DEFAULT '[]',
            dimension_comparisons_json JSONB DEFAULT '[]',
            image_width INT DEFAULT 0,
            image_height INT DEFAULT 0,
            dxf_width_mm FLOAT DEFAULT 0.0,
            dxf_height_mm FLOAT DEFAULT 0.0,
            image_url TEXT,
            dxf_url TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_comparison_results_score ON comparison_results(overall_score);
        CREATE INDEX IF NOT EXISTS idx_comparison_results_job_id ON comparison_results(job_id);
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("[Startup] Postgres auxiliary tables initialized successfully.")
