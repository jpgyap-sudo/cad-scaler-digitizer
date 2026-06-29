"""
Central Brain Sync — PostgreSQL intelligence layer for the CAD Digitizer.

Connects every component (chat, corrections, presets, drawings) to a
shared Postgres brain. Enables:

1. Cross-user learning — corrections from User A improve User B's defaults
2. Persistent sessions — chat history survives container restarts
3. Global material library — crowd-sourced material/component pairings
4. Proportion intelligence — aggregated dimension ratios from all users
5. Drawing history — every DXF tracked with quality scores
6. Evolution tracking — correction→improvement loops

Schema: 6 tables extending the existing ml_predictions + ml_models
- furniture_corrections
- material_library
- style_presets
- chat_sessions
- drawing_history
- component_proportions
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

# Postgres connection (reads from env, falls back to local defaults)
PG_HOST = os.environ.get("PG_HOST", "postgres")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_DATABASE = os.environ.get("PG_DATABASE", "cad_reference_library")
PG_USER = os.environ.get("PG_USER", "postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "postgres")

_conn = None


def _get_conn():
    """Lazy Postgres connection."""
    global _conn
    if _conn is None or _conn.closed:
        try:
            import psycopg2
            _conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, database=PG_DATABASE,
                user=PG_USER, password=PG_PASSWORD
            )
            _conn.autocommit = True
        except Exception as e:
            print(f"[BrainSync] Postgres unavailable: {e}")
            return None
    return _conn


def _execute(sql: str, params: tuple = None, fetch: bool = False, commit: bool = False) -> Any:
    """Execute SQL, optionally returning results or committing."""
    conn = _get_conn()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if fetch:
            return cur.fetchall()
        cur.close()
        if commit:
            conn.commit()
    except Exception as e:
        print(f"[BrainSync] SQL error: {e}")
        if commit:
            conn.rollback()
    return None


# ===== Corrections =====

def record_correction(
    session_id: str,
    furniture_type: str,
    field: str,
    old_value: Any,
    new_value: Any,
    correction_type: str = "dimension",
    user_id: str = "default",
    context: Optional[Dict] = None,
) -> bool:
    """Record a correction to the central brain."""
    ratio = None
    if correction_type == "dimension":
        try:
            ov, nv = float(old_value or 0), float(new_value or 0)
            if ov > 0:
                ratio = round(nv / ov, 4)
        except (ValueError, TypeError):
            pass

    return bool(_execute("""
        INSERT INTO furniture_corrections
            (session_id, furniture_type, field, old_value, new_value,
             correction_ratio, correction_type, user_id, context)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        session_id, furniture_type, field,
        str(old_value)[:200] if old_value is not None else None,
        str(new_value)[:200] if new_value is not None else None,
        ratio, correction_type, user_id,
        json.dumps(context or {}),
    )))


def get_correction_stats(furniture_type: str, field: str) -> Dict:
    """Get aggregate correction statistics for a component."""
    rows = _execute("""
        SELECT AVG(correction_ratio), COUNT(*), STDDEV(correction_ratio)
        FROM furniture_corrections
        WHERE furniture_type = %s AND field = %s AND correction_ratio IS NOT NULL
    """, (furniture_type, field), fetch=True)
    if rows and rows[0][0]:
        return {
            "avg_ratio": round(rows[0][0], 4),
            "count": rows[0][1],
            "stddev": round(rows[0][2] or 0, 4),
        }
    return {"avg_ratio": 1.0, "count": 0, "stddev": 0.0}


# ===== Material Library =====

def record_material(
    component: str,
    material: str,
    furniture_type: str = "round_pedestal_table",
    finish: str = None,
    texture: str = None,
    color: str = None,
) -> bool:
    """Record a material choice to the global library."""
    return bool(_execute("""
        INSERT INTO material_library (component, material, finish, texture, color, furniture_type)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (component, material, furniture_type)
        DO UPDATE SET usage_count = material_library.usage_count + 1,
                      finish = COALESCE(EXCLUDED.finish, material_library.finish)
    """, (component, material, finish, texture, color, furniture_type)))


def get_material_suggestions(component: str, furniture_type: str = None, limit: int = 5) -> List[Dict]:
    """Get most-used materials for a component."""
    rows = _execute("""
        SELECT material, finish, texture, color, usage_count, hatch_pattern
        FROM material_library
        WHERE component = %s
          AND (furniture_type = %s OR %s IS NULL)
        ORDER BY usage_count DESC
        LIMIT %s
    """, (component, furniture_type, furniture_type, limit), fetch=True)
    if not rows:
        return []
    return [
        {"material": r[0], "finish": r[1], "texture": r[2], "color": r[3],
         "count": r[4], "hatch": r[5]}
        for r in rows
    ]


# ===== Style Presets =====

def save_preset(name: str, state: Dict, user_id: str = "default", furniture_type: str = None) -> bool:
    """Save a style preset to Postgres."""
    return bool(_execute("""
        INSERT INTO style_presets (name, user_id, furniture_type, materials, dimensions, visibility, notes, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (name) DO UPDATE SET
            materials = EXCLUDED.materials,
            dimensions = EXCLUDED.dimensions,
            visibility = EXCLUDED.visibility,
            notes = EXCLUDED.notes,
            furniture_type = COALESCE(EXCLUDED.furniture_type, style_presets.furniture_type),
            updated_at = NOW()
    """, (
        name, user_id,
        furniture_type or state.get("furniture_type", "round_pedestal_table"),
        json.dumps(state.get("materials", {})),
        json.dumps(state.get("dimensions", {})),
        json.dumps(state.get("visibility", {})),
        json.dumps(state.get("notes", [])),
    )))


def load_preset(name: str) -> Optional[Dict]:
    """Load a style preset from Postgres."""
    rows = _execute(
        "SELECT furniture_type, materials, dimensions, visibility, notes, finish_notes FROM style_presets WHERE name = %s",
        (name,), fetch=True
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "furniture_type": r[0],
        "materials": r[1] if isinstance(r[1], dict) else json.loads(r[1] or "{}"),
        "dimensions": r[2] if isinstance(r[2], dict) else json.loads(r[2] or "{}"),
        "visibility": r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}"),
        "notes": r[4] if isinstance(r[4], list) else json.loads(r[4] or "[]"),
    }


def list_presets(user_id: str = None) -> List[Dict]:
    """List all presets."""
    rows = _execute(
        "SELECT name, furniture_type, updated_at FROM style_presets WHERE user_id = %s OR %s IS NULL ORDER BY updated_at DESC",
        (user_id, user_id), fetch=True
    )
    return [{"name": r[0], "type": r[1], "updated": str(r[2])} for r in (rows or [])]


# ===== Chat Sessions =====

def save_chat_session(session_id: str, state: Dict, user_id: str = "default", image_id: str = None) -> bool:
    """Persist a chat session to Postgres."""
    return bool(_execute("""
        INSERT INTO chat_sessions (session_id, user_id, image_id, state, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (session_id) DO UPDATE SET
            state = EXCLUDED.state,
            message_count = chat_sessions.message_count + 1,
            last_message = %s,
            updated_at = NOW()
    """, (session_id, user_id, image_id, json.dumps(state),
          json.dumps(state.get("notes", [])[-1] if state.get("notes") else None))))


def load_chat_session(session_id: str) -> Optional[Dict]:
    """Load a chat session from Postgres."""
    rows = _execute(
        "SELECT state FROM chat_sessions WHERE session_id = %s",
        (session_id,), fetch=True
    )
    if not rows:
        return None
    return rows[0][0] if isinstance(rows[0][0], dict) else json.loads(rows[0][0] or "{}")


# ===== Drawing History =====

def record_drawing(
    session_id: str,
    furniture_type: str,
    dxf_file: str,
    quality_score: float = None,
    entity_counts: Dict = None,
    dimensions_used: Dict = None,
    preview_urls: Dict = None,
) -> bool:
    """Record a DXF generation to history."""
    return bool(_execute("""
        INSERT INTO drawing_history
            (session_id, furniture_type, dxf_file, quality_score, entity_counts, dimensions_used, preview_urls)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        session_id, furniture_type, dxf_file, quality_score,
        json.dumps(entity_counts or {}),
        json.dumps(dimensions_used or {}),
        json.dumps(preview_urls or {}),
    )))


# ===== Component Proportions =====

def record_proportion(
    furniture_type: str,
    anchor_dimension: str,
    anchor_value: float,
    component: str,
    component_value: float,
) -> bool:
    """Record a component proportion to the global brain."""
    ratio = component_value / anchor_value if anchor_value > 0 else 0
    return bool(_execute("""
        INSERT INTO component_proportions
            (furniture_type, anchor_dimension, anchor_value, component, component_value, ratio, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (furniture_type, anchor_dimension, anchor_value, component) DO UPDATE SET
            component_value = (component_proportions.component_value * component_proportions.sample_count + EXCLUDED.component_value)
                              / (component_proportions.sample_count + 1),
            ratio = (component_proportions.ratio * component_proportions.sample_count + EXCLUDED.ratio)
                    / (component_proportions.sample_count + 1),
            sample_count = component_proportions.sample_count + 1,
            confidence = LEAST(0.95, component_proportions.confidence + 0.02),
            updated_at = NOW()
    """, (furniture_type, anchor_dimension, anchor_value, component, component_value, ratio)))


def get_proportion_estimate(
    furniture_type: str,
    anchor_dimension: str,
    anchor_value: float,
    component: str,
) -> Optional[Dict]:
    """Get the best estimated proportion from the brain."""
    rows = _execute("""
        SELECT component_value, ratio, sample_count, confidence
        FROM component_proportions
        WHERE furniture_type = %s
          AND anchor_dimension = %s
          AND component = %s
        ORDER BY ABS(anchor_value - %s) ASC, sample_count DESC
        LIMIT 1
    """, (furniture_type, anchor_dimension, component, anchor_value), fetch=True)
    if not rows:
        # Fallback: find any anchor value for this component type
        rows = _execute("""
            SELECT component_value, ratio, anchor_value, sample_count, confidence
            FROM component_proportions
            WHERE furniture_type = %s AND component = %s
            ORDER BY sample_count DESC LIMIT 1
        """, (furniture_type, component), fetch=True)
        if rows:
            r = rows[0]
            return {
                "estimated_value": round(r[1] * anchor_value, 1),
                "ratio": round(r[1], 4),
                "sample_count": r[3],
                "confidence": r[4],
                "source": "cross_anchor_extrapolation",
            }
        return None
    r = rows[0]
    return {
        "estimated_value": round(r[0] or r[1] * anchor_value, 1),
        "ratio": round(r[1], 4),
        "sample_count": r[2],
        "confidence": r[3],
        "source": "brain_statistics",
    }


# ===== Intelligence Queries =====

def get_intelligence_report(furniture_type: str = None) -> Dict:
    """Generate a brain intelligence report."""
    report = {}

    # Correction stats
    rows = _execute("""
        SELECT furniture_type, COUNT(*), AVG(correction_ratio)
        FROM furniture_corrections
        WHERE correction_ratio IS NOT NULL
        GROUP BY furniture_type
        ORDER BY COUNT(*) DESC
    """, fetch=True)
    report["corrections_by_type"] = [
        {"type": r[0], "count": r[1], "avg_ratio": round(r[2] or 1, 3)}
        for r in (rows or [])
    ]

    # Top materials
    rows = _execute("""
        SELECT component, material, usage_count
        FROM material_library
        ORDER BY usage_count DESC LIMIT 10
    """, fetch=True)
    report["top_materials"] = [
        {"component": r[0], "material": r[1], "count": r[2]}
        for r in (rows or [])
    ]

    # Proportion confidence
    rows = _execute("""
        SELECT furniture_type, component, sample_count, confidence
        FROM component_proportions
        WHERE sample_count >= 3
        ORDER BY confidence DESC LIMIT 10
    """, fetch=True)
    report["confident_proportions"] = [
        {"type": r[0], "component": r[1], "samples": r[2], "confidence": round(r[3], 2)}
        for r in (rows or [])
    ]

    # Recent drawings
    rows = _execute("""
        SELECT furniture_type, dxf_file, quality_score, created_at
        FROM drawing_history
        ORDER BY created_at DESC LIMIT 10
    """, fetch=True)
    report["recent_drawings"] = [
        {"type": r[0], "file": r[1], "quality": r[2], "time": str(r[3])}
        for r in (rows or [])
    ]

    return report
