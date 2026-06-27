"""Database persistence for Resource Engine — feedback, scenes, and learned patterns.
Uses SQLite for zero-dependency portability. Switches to PostgreSQL when DATABASE_URL is set.

Tables (auto-created):
  - resource_feedback: user approval/rejection of generated scenes
  - resource_scenes: full scene graph snapshots (validation fixtures)
  - resource_patterns: learned dimension patterns from approved feedback
"""
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from .schema import ParametricSceneGraph

DB_DIR = Path(os.environ.get("RESOURCE_DB_DIR", str(Path(__file__).parent.parent.parent / "data")))
DB_PATH = DB_DIR / "resource_engine.db"

# Detect if PostgreSQL is available via DATABASE_URL
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _get_conn():
    """Get database connection — SQLite local, PostgreSQL if configured."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            return conn, "postgres"
        except Exception:
            pass
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"


def _init_sqlite():
    """Create SQLite tables if they don't exist."""
    conn, _ = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS resource_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT DEFAULT '',
                product_type TEXT NOT NULL,
                approved INTEGER NOT NULL DEFAULT 0,
                comment TEXT DEFAULT '',
                user_id TEXT DEFAULT 'default',
                component_count INTEGER DEFAULT 0,
                material_count INTEGER DEFAULT 0,
                warnings_json TEXT DEFAULT '[]',
                scene_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_type ON resource_feedback(product_type);
            CREATE INDEX IF NOT EXISTS idx_feedback_approved ON resource_feedback(approved);
            CREATE INDEX IF NOT EXISTS idx_feedback_user ON resource_feedback(user_id);

            CREATE TABLE IF NOT EXISTS resource_scenes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_type TEXT NOT NULL,
                label TEXT DEFAULT 'auto_generated',
                scene_json TEXT NOT NULL,
                warning_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_scenes_type ON resource_scenes(product_type);

            CREATE TABLE IF NOT EXISTS resource_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_type TEXT NOT NULL,
                dimension_key TEXT NOT NULL,
                mean_value REAL,
                std_dev REAL,
                min_value REAL,
                max_value REAL,
                sample_count INTEGER DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_type, dimension_key)
            );
            CREATE INDEX IF NOT EXISTS idx_patterns_type ON resource_patterns(product_type);
        """)
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Initialize the database on startup."""
    _init_sqlite()
    print(f"[ResourceDB] Initialized at {DB_PATH}")


def save_feedback_db(
    product_type: str,
    approved: bool,
    comment: str = "",
    user_id: str = "default",
    session_id: str = "",
    scene_json: str = "{}",
    warnings: Optional[List[str]] = None,
) -> int:
    """Save feedback to database. Returns the row ID."""
    conn, engine = _get_conn()
    try:
        cur = conn.cursor()
        if engine == "postgres":
            cur.execute("""
                INSERT INTO resource_feedback
                (session_id, product_type, approved, comment, user_id, warnings_json, scene_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (session_id, product_type, 1 if approved else 0, comment, user_id,
                  json.dumps(warnings or []), scene_json))
            row_id = cur.fetchone()[0]
        else:
            cur.execute("""
                INSERT INTO resource_feedback
                (session_id, product_type, approved, comment, user_id, warnings_json, scene_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, product_type, 1 if approved else 0, comment, user_id,
                  json.dumps(warnings or []), scene_json))
            row_id = cur.lastrowid
        conn.commit()
        return row_id
    finally:
        conn.close()


def save_scene_db(scene: ParametricSceneGraph, label: str = "auto_generated") -> int:
    """Save a scene graph to the database as a validation fixture."""
    conn, engine = _get_conn()
    try:
        scene_json = scene.model_dump_json()
        cur = conn.cursor()
        if engine == "postgres":
            cur.execute("""
                INSERT INTO resource_scenes (product_type, label, scene_json, warning_count)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (scene.product_type, label, scene_json, len(scene.warnings)))
            row_id = cur.fetchone()[0]
        else:
            cur.execute("""
                INSERT INTO resource_scenes (product_type, label, scene_json, warning_count)
                VALUES (?, ?, ?, ?)
            """, (scene.product_type, label, scene_json, len(scene.warnings)))
            row_id = cur.lastrowid
        conn.commit()
        return row_id
    finally:
        conn.close()


def update_pattern(product_type: str, dimension_key: str, value: float):
    """Update or insert a learned pattern from feedback."""
    conn, engine = _get_conn()
    try:
        cur = conn.cursor()
        if engine == "postgres":
            cur.execute("""
                INSERT INTO resource_patterns (product_type, dimension_key, mean_value, std_dev, min_value, max_value, sample_count)
                VALUES (%s, %s, %s, 0, %s, %s, 1)
                ON CONFLICT (product_type, dimension_key) DO UPDATE SET
                    mean_value = (resource_patterns.mean_value * resource_patterns.sample_count + %s) / (resource_patterns.sample_count + 1),
                    min_value = LEAST(resource_patterns.min_value, %s),
                    max_value = GREATEST(resource_patterns.max_value, %s),
                    sample_count = resource_patterns.sample_count + 1,
                    last_updated = NOW()
            """, (product_type, dimension_key, value, value, value, value, value, value))
        else:
            cur.execute("""
                INSERT INTO resource_patterns (product_type, dimension_key, mean_value, std_dev, min_value, max_value, sample_count)
                VALUES (?, ?, ?, 0, ?, ?, 1)
                ON CONFLICT(product_type, dimension_key) DO UPDATE SET
                    mean_value = (resource_patterns.mean_value * resource_patterns.sample_count + ?) / (resource_patterns.sample_count + 1),
                    min_value = CASE WHEN ? < resource_patterns.min_value THEN ? ELSE resource_patterns.min_value END,
                    max_value = CASE WHEN ? > resource_patterns.max_value THEN ? ELSE resource_patterns.max_value END,
                    sample_count = resource_patterns.sample_count + 1,
                    last_updated = CURRENT_TIMESTAMP
            """, (product_type, dimension_key, value, value, value, value, value, value, value, value))
        conn.commit()
    finally:
        conn.close()


def get_feedback_stats_db() -> Dict[str, Any]:
    """Get aggregated feedback statistics from database."""
    conn, engine = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total, SUM(approved) as approved FROM resource_feedback")
        row = cur.fetchone()
        total = row["total"] if row else 0
        approved = row["approved"] or 0 if row else 0

        cur.execute("SELECT DISTINCT product_type FROM resource_feedback")
        types = [r["product_type"] for r in cur.fetchall() if r["product_type"]]

        return {
            "total": total,
            "approved": approved,
            "rejected": total - approved,
            "approval_rate": round(approved / max(total, 1), 2),
            "product_types": types,
        }
    finally:
        conn.close()


def get_patterns_db(product_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get learned dimension patterns."""
    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        if product_type:
            cur.execute("SELECT * FROM resource_patterns WHERE product_type = ? ORDER BY dimension_key", (product_type,))
        else:
            cur.execute("SELECT * FROM resource_patterns ORDER BY product_type, dimension_key")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def load_recent_scenes_db(limit: int = 20) -> List[Dict[str, Any]]:
    """Load recent scene snapshots."""
    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM resource_scenes ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def load_recent_feedback_db(limit: int = 20) -> List[Dict[str, Any]]:
    """Load recent feedback entries from database."""
    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM resource_feedback ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
