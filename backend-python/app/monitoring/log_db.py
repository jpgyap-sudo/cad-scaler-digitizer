"""
Monitoring Database Layer — logs every chat, task, decision, and tool
usage to PostgreSQL for performance tracking and improvement recommendations.

Mirrors the connection pattern from brain_sync.py for consistency.
"""

import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

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
            print(f"[MonitorDB] Postgres unavailable: {e}")
            return None
    return _conn


def _execute(sql: str, params: tuple = None, fetch: bool = False) -> Any:
    """Execute SQL, optionally returning results."""
    conn = _get_conn()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if fetch:
            rows = cur.fetchall()
            # Build column names for dict-style access
            if cur.description:
                cols = [desc[0] for desc in cur.description]
                result = [dict(zip(cols, row)) for row in rows]
            else:
                result = rows
            cur.close()
            return result
        cur.close()
    except Exception as e:
        print(f"[MonitorDB] SQL error: {e}")
    return None


# =============================================================
# CHAT LOGGING
# =============================================================

def log_chat(
    session_id: str,
    user_message: str,
    assistant_response: str,
    extracted_action: str = None,
    furniture_type: str = None,
    dimension_changes: Dict = None,
    material_changes: Dict = None,
    backend_used: str = None,
    response_time_ms: int = None,
    token_count: int = None,
) -> bool:
    """Log a user↔assistant chat exchange."""
    return bool(_execute("""
        INSERT INTO assistant_chat_log
            (session_id, user_message, assistant_response, extracted_action,
             furniture_type, dimension_changes, material_changes,
             backend_used, response_time_ms, token_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        session_id, user_message, assistant_response, extracted_action,
        furniture_type,
        json.dumps(dimension_changes) if dimension_changes else None,
        json.dumps(material_changes) if material_changes else None,
        backend_used, response_time_ms, token_count,
    )))


def get_recent_chats(session_id: str = None, limit: int = 50) -> List[Dict]:
    """Return recent chat log entries."""
    if session_id:
        rows = _execute("""
            SELECT * FROM assistant_chat_log
            WHERE session_id = %s
            ORDER BY created_at DESC LIMIT %s
        """, (session_id, limit), fetch=True)
    else:
        rows = _execute("""
            SELECT * FROM assistant_chat_log
            ORDER BY created_at DESC LIMIT %s
        """, (limit,), fetch=True)
    return rows or []


# =============================================================
# TASK LOGGING
# =============================================================

def log_task(
    session_id: str,
    task_type: str,
    furniture_type: str = None,
    input_params: Dict = None,
    output_summary: Dict = None,
    success: bool = True,
    error_message: str = None,
    duration_ms: int = None,
) -> bool:
    """Log an assistant task execution."""
    return bool(_execute("""
        INSERT INTO assistant_task_log
            (session_id, task_type, furniture_type, input_params,
             output_summary, success, error_message, duration_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        session_id, task_type, furniture_type,
        json.dumps(input_params) if input_params else None,
        json.dumps(output_summary) if output_summary else None,
        success, error_message, duration_ms,
    )))


def get_recent_tasks(task_type: str = None, limit: int = 50) -> List[Dict]:
    """Return recent task log entries."""
    if task_type:
        rows = _execute("""
            SELECT * FROM assistant_task_log
            WHERE task_type = %s
            ORDER BY created_at DESC LIMIT %s
        """, (task_type, limit), fetch=True)
    else:
        rows = _execute("""
            SELECT * FROM assistant_task_log
            ORDER BY created_at DESC LIMIT %s
        """, (limit,), fetch=True)
    return rows or []


# =============================================================
# DECISION LOGGING
# =============================================================

def log_decision(
    session_id: str,
    decision_type: str,
    confidence: float = None,
    rationale: str = None,
    alternatives: List = None,
    context: Dict = None,
) -> bool:
    """Log an AI decision with confidence and rationale."""
    return bool(_execute("""
        INSERT INTO assistant_decision_log
            (session_id, decision_type, confidence, rationale, alternatives, context)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        session_id, decision_type, confidence, rationale,
        json.dumps(alternatives) if alternatives else None,
        json.dumps(context) if context else None,
    )))


def get_recent_tools(limit: int = 50) -> List[Dict]:
    """Return recent tool usage log entries directly from assistant_tool_log."""
    rows = _execute("""
        SELECT * FROM assistant_tool_log
        ORDER BY created_at DESC LIMIT %s
    """, (limit,), fetch=True)
    return rows or []


def get_recent_decisions(decision_type: str = None, limit: int = 50) -> List[Dict]:
    """Return recent decision log entries."""
    if decision_type:
        rows = _execute("""
            SELECT * FROM assistant_decision_log
            WHERE decision_type = %s
            ORDER BY created_at DESC LIMIT %s
        """, (decision_type, limit), fetch=True)
    else:
        rows = _execute("""
            SELECT * FROM assistant_decision_log
            ORDER BY created_at DESC LIMIT %s
        """, (limit,), fetch=True)
    return rows or []


# =============================================================
# TOOL USAGE LOGGING
# =============================================================

def log_tool_usage(
    session_id: str,
    tool_name: str,
    input_summary: str = None,
    output_summary: str = None,
    duration_ms: int = None,
    success: bool = True,
) -> bool:
    """Log an internal tool/function call."""
    return bool(_execute("""
        INSERT INTO assistant_tool_log
            (session_id, tool_name, input_summary, output_summary, duration_ms, success)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (session_id, tool_name, input_summary, output_summary, duration_ms, success)))


# =============================================================
# PERFORMANCE METRICS (daily aggregation)
# =============================================================

def update_performance_metrics() -> Dict:
    """Aggregate today's logs into assistant_performance_metrics.
    Called periodically by the monitor worker. Returns summary dict."""
    today = date.today()

    # Count chats
    chat_rows = _execute("""
        SELECT COUNT(*) as cnt,
               AVG(response_time_ms) as avg_rt,
               COUNT(*) FILTER (WHERE backend_used = 'OpenAI') as openai_cnt,
               COUNT(*) FILTER (WHERE backend_used = 'Ollama') as ollama_cnt,
               COUNT(DISTINCT session_id) as uniq_sessions
        FROM assistant_chat_log
        WHERE created_at::date = %s
    """, (today,), fetch=True)

    # Count tasks + errors
    task_rows = _execute("""
        SELECT COUNT(*) as cnt,
               COUNT(*) FILTER (WHERE NOT success) as err_cnt,
               AVG(duration_ms) as avg_dur
        FROM assistant_task_log
        WHERE created_at::date = %s
    """, (today,), fetch=True)

    # Furniture type breakdown
    ft_rows = _execute("""
        SELECT furniture_type, COUNT(*) as cnt
        FROM assistant_task_log
        WHERE created_at::date = %s AND furniture_type IS NOT NULL
        GROUP BY furniture_type
    """, (today,), fetch=True)

    # Error type breakdown
    err_rows = _execute("""
        SELECT task_type, COUNT(*) as cnt
        FROM assistant_task_log
        WHERE created_at::date = %s AND NOT success
        GROUP BY task_type
    """, (today,), fetch=True)

    # P50 / P95 response times
    rt_rows = _execute("""
        SELECT duration_ms FROM assistant_task_log
        WHERE created_at::date = %s AND duration_ms IS NOT NULL
        ORDER BY duration_ms
    """, (today,), fetch=True)

    total_chats = chat_rows[0]['cnt'] if chat_rows else 0
    total_tasks = task_rows[0]['cnt'] if task_rows else 0
    total_errors = task_rows[0]['err_cnt'] if task_rows else 0
    avg_rt = chat_rows[0]['avg_rt'] if chat_rows and chat_rows[0]['avg_rt'] else None
    openai_cnt = chat_rows[0]['openai_cnt'] if chat_rows else 0
    ollama_cnt = chat_rows[0]['ollama_cnt'] if chat_rows else 0
    uniq_sessions = chat_rows[0]['uniq_sessions'] if chat_rows else 0
    avg_dur = task_rows[0]['avg_dur'] if task_rows and task_rows[0]['avg_dur'] else None

    # Calculate P50/P95
    rt_values = [r['duration_ms'] for r in (rt_rows or []) if r['duration_ms'] is not None]
    p50 = None
    p95 = None
    if rt_values:
        rt_values.sort()
        n = len(rt_values)
        p50 = rt_values[int(n * 0.5)]
        p95 = rt_values[int(n * 0.95)]

    ft_breakdown = {r['furniture_type']: r['cnt'] for r in (ft_rows or [])}
    err_breakdown = {r['task_type']: r['cnt'] for r in (err_rows or [])}

    # Average confidence
    conf_rows = _execute("""
        SELECT AVG(confidence) as avg_conf
        FROM assistant_decision_log
        WHERE created_at::date = %s
    """, (today,), fetch=True)
    avg_conf = conf_rows[0]['avg_conf'] if conf_rows and conf_rows[0]['avg_conf'] else None

    # UPSERT
    _execute("""
        INSERT INTO assistant_performance_metrics
            (metric_date, total_chats, total_tasks, total_errors,
             avg_response_time_ms, p50_response_time_ms, p95_response_time_ms,
             avg_confidence, openai_usage_count, ollama_usage_count,
             unique_sessions, furniture_type_breakdown, error_type_breakdown,
             updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (metric_date) DO UPDATE SET
            total_chats = EXCLUDED.total_chats,
            total_tasks = EXCLUDED.total_tasks,
            total_errors = EXCLUDED.total_errors,
            avg_response_time_ms = EXCLUDED.avg_response_time_ms,
            p50_response_time_ms = EXCLUDED.p50_response_time_ms,
            p95_response_time_ms = EXCLUDED.p95_response_time_ms,
            avg_confidence = EXCLUDED.avg_confidence,
            openai_usage_count = EXCLUDED.openai_usage_count,
            ollama_usage_count = EXCLUDED.ollama_usage_count,
            unique_sessions = EXCLUDED.unique_sessions,
            furniture_type_breakdown = EXCLUDED.furniture_type_breakdown,
            error_type_breakdown = EXCLUDED.error_type_breakdown,
            updated_at = NOW()
    """, (
        today, total_chats, total_tasks, total_errors,
        avg_rt, p50, p95, avg_conf, openai_cnt, ollama_cnt,
        uniq_sessions,
        json.dumps(ft_breakdown), json.dumps(err_breakdown),
    ))

    return {
        "date": str(today),
        "total_chats": total_chats,
        "total_tasks": total_tasks,
        "total_errors": total_errors,
        "avg_response_time_ms": avg_rt,
        "p50_response_time_ms": p50,
        "p95_response_time_ms": p95,
        "avg_confidence": avg_conf,
        "openai_usage": openai_cnt,
        "ollama_usage": ollama_cnt,
        "unique_sessions": uniq_sessions,
        "furniture_types": ft_breakdown,
        "error_types": err_breakdown,
    }


def get_performance_dashboard(days: int = 7) -> Dict:
    """Return aggregated performance dashboard for the last N days."""
    since = date.today() - timedelta(days=days)

    # Daily metrics
    daily = _execute("""
        SELECT * FROM assistant_performance_metrics
        WHERE metric_date >= %s
        ORDER BY metric_date DESC
    """, (since,), fetch=True)

    # Aggregated totals
    totals = _execute("""
        SELECT SUM(total_chats) as chats,
               SUM(total_tasks) as tasks,
               SUM(total_errors) as errors,
               AVG(avg_response_time_ms) as avg_rt,
               SUM(openai_usage_count) as openai,
               SUM(ollama_usage_count) as ollama
        FROM assistant_performance_metrics
        WHERE metric_date >= %s
    """, (since,), fetch=True)

    # Recent errors
    recent_errors = _execute("""
        SELECT * FROM assistant_task_log
        WHERE NOT success AND created_at >= %s
        ORDER BY created_at DESC LIMIT 20
    """, (since,), fetch=True)

    # Top tools
    top_tools = _execute("""
        SELECT tool_name, COUNT(*) as cnt, AVG(duration_ms) as avg_dur
        FROM assistant_tool_log
        WHERE created_at >= %s
        GROUP BY tool_name
        ORDER BY cnt DESC LIMIT 15
    """, (since,), fetch=True)

    # Average confidence by decision type
    conf_by_type = _execute("""
        SELECT decision_type, AVG(confidence) as avg_conf, COUNT(*) as cnt
        FROM assistant_decision_log
        WHERE created_at >= %s
        GROUP BY decision_type
        ORDER BY cnt DESC
    """, (since,), fetch=True)

    # Recommendation count
    rec_counts = _execute("""
        SELECT status, COUNT(*) as cnt
        FROM assistant_improvement_recommendations
        GROUP BY status
    """, fetch=True)

    t = totals[0] if totals else {}

    return {
        "period_days": days,
        "daily_metrics": daily or [],
        "aggregated": {
            "total_chats": t['chats'] if t else 0,
            "total_tasks": t['tasks'] if t else 0,
            "total_errors": t['errors'] if t else 0,
            "avg_response_time_ms": round(t['avg_rt'], 1) if t and t['avg_rt'] else None,
            "openai_usage": t['openai'] if t else 0,
            "ollama_usage": t['ollama'] if t else 0,
        },
        "recent_errors": recent_errors or [],
        "top_tools": top_tools or [],
        "avg_confidence_by_type": conf_by_type or [],
        "recommendations": {r['status']: r['cnt'] for r in (rec_counts or [])},
    }


# =============================================================
# IMPROVEMENT RECOMMENDATIONS
# =============================================================

def add_recommendation(
    rec_type: str,
    title: str,
    description: str = None,
    evidence: Dict = None,
    impact: str = "medium",
    effort: str = "medium",
    source: str = None,
) -> bool:
    """Add an improvement recommendation generated by the monitor worker."""
    return bool(_execute("""
        INSERT INTO assistant_improvement_recommendations
            (recommendation_type, title, description, evidence, impact, effort, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        rec_type, title, description,
        json.dumps(evidence) if evidence else None,
        impact, effort, source,
    )))


def update_recommendation_status(rec_id: int, status: str) -> bool:
    """Update the status of a recommendation."""
    if status == "implemented":
        return bool(_execute("""
            UPDATE assistant_improvement_recommendations
            SET status = %s, implemented_at = NOW()
            WHERE id = %s
        """, (status, rec_id)))
    return bool(_execute("""
        UPDATE assistant_improvement_recommendations
        SET status = %s
        WHERE id = %s
    """, (status, rec_id)))


def get_open_recommendations(limit: int = 20) -> List[Dict]:
    """Get open and in-progress recommendations."""
    rows = _execute("""
        SELECT * FROM assistant_improvement_recommendations
        WHERE status IN ('open', 'in_progress')
        ORDER BY
            CASE impact WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
            created_at DESC
        LIMIT %s
    """, (limit,), fetch=True)
    return rows or []
