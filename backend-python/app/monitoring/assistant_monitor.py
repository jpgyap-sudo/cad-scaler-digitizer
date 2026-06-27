"""
Drawing Assistant Monitor — VPS monitoring worker.

Runs as a standalone service that periodically:
1. Aggregates daily performance metrics from logs
2. Analyzes patterns and generates improvement recommendations
3. Reports assistant health status

Designed to run as a Docker service alongside the API and frontend.
"""

import os
import json
import time
import signal
from datetime import datetime, timedelta
from typing import Dict, List

# --- Configuration ---
POLL_INTERVAL_SECONDS = int(os.environ.get("MONITOR_POLL_INTERVAL", "300"))  # 5 min default
AGGREGATE_INTERVAL_SECONDS = int(os.environ.get("MONITOR_AGGREGATE_INTERVAL", "3600"))  # 1 hour
ANALYSIS_INTERVAL_SECONDS = int(os.environ.get("MONITOR_ANALYSIS_INTERVAL", "21600"))  # 6 hours
LOG_LEVEL = os.environ.get("MONITOR_LOG_LEVEL", "INFO")

_running = True


def log(msg: str, level: str = "INFO"):
    """Structured log output."""
    ts = datetime.now().isoformat()
    print(f"[{ts}] [{level}] [MonitorWorker] {msg}")


def signal_handler(sig, frame):
    global _running
    log(f"Received signal {sig}, shutting down gracefully...")
    _running = False


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# =============================================================
# Database Access
# =============================================================

def _get_conn():
    """Get Postgres connection (same pattern as log_db.py)."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=os.environ.get("PG_PORT", "5432"),
            database=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        log(f"Postgres unavailable: {e}", "ERROR")
        return None


def _execute(sql: str, params: tuple = None, fetch: bool = False):
    conn = _get_conn()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if fetch:
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description] if cur.description else []
            result = [dict(zip(cols, row)) for row in rows]
            cur.close()
            return result
        cur.close()
    except Exception as e:
        log(f"SQL error: {e}", "ERROR")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return None


# =============================================================
# Analysis Functions
# =============================================================

def aggregate_daily_metrics() -> Dict:
    """Aggregate today's logs into daily metrics."""
    today = datetime.now().date()

    # Chat stats
    chat_rows = _execute("""
        SELECT COUNT(*) as cnt,
               AVG(response_time_ms) as avg_rt,
               COUNT(*) FILTER (WHERE backend_used = 'OpenAI') as openai_cnt,
               COUNT(*) FILTER (WHERE backend_used = 'Ollama') as ollama_cnt,
               COUNT(DISTINCT session_id) as uniq_sessions
        FROM assistant_chat_log
        WHERE created_at::date = %s
    """, (today,), fetch=True)

    # Task stats
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

    # Response time percentiles
    rt_rows = _execute("""
        SELECT duration_ms FROM assistant_task_log
        WHERE created_at::date = %s AND duration_ms IS NOT NULL
        ORDER BY duration_ms
    """, (today,), fetch=True)

    c = chat_rows[0] if chat_rows else {}
    t = task_rows[0] if task_rows else {}

    total_chats = c.get('cnt', 0) or 0
    total_tasks = t.get('cnt', 0) or 0
    total_errors = t.get('err_cnt', 0) or 0
    avg_rt = c.get('avg_rt')
    openai_cnt = c.get('openai_cnt', 0) or 0
    ollama_cnt = c.get('ollama_cnt', 0) or 0
    uniq_sessions = c.get('uniq_sessions', 0) or 0

    rt_values = [r['duration_ms'] for r in (rt_rows or []) if r.get('duration_ms')]
    p50 = rt_values[len(rt_values) // 2] if rt_values else None
    p95 = rt_values[int(len(rt_values) * 0.95)] if rt_values else None

    ft_breakdown = {r['furniture_type']: r['cnt'] for r in (ft_rows or [])}
    err_breakdown = {r['task_type']: r['cnt'] for r in (err_rows or [])}

    # Average confidence
    conf_rows = _execute("""
        SELECT AVG(confidence) as avg_conf FROM assistant_decision_log
        WHERE created_at::date = %s
    """, (today,), fetch=True)
    avg_conf = conf_rows[0]['avg_conf'] if conf_rows and conf_rows[0].get('avg_conf') else None

    # UPSERT into performance_metrics
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
        json.dumps(ft_breakdown) if ft_breakdown else None,
        json.dumps(err_breakdown) if err_breakdown else None,
    ))

    result = {
        "date": str(today),
        "total_chats": total_chats,
        "total_tasks": total_tasks,
        "total_errors": total_errors,
        "avg_response_time_ms": avg_rt,
        "openai_usage": openai_cnt,
        "ollama_usage": ollama_cnt,
    }
    log(f"Aggregated metrics: {json.dumps(result)}")
    return result


def analyze_error_patterns(days: int = 7) -> List[Dict]:
    """Analyze recent errors and generate recommendations."""
    since = datetime.now() - timedelta(days=days)

    rows = _execute("""
        SELECT task_type, error_message, COUNT(*) as error_count
        FROM assistant_task_log
        WHERE NOT success AND created_at >= %s
        GROUP BY task_type, error_message
        ORDER BY error_count DESC
        LIMIT 20
    """, (since,), fetch=True)

    recommendations = []
    if not rows:
        return recommendations

    # Group by task_type
    by_type = {}
    for r in rows:
        tt = r['task_type']
        if tt not in by_type:
            by_type[tt] = {"total": 0, "examples": []}
        by_type[tt]["total"] += r['error_count']
        by_type[tt]["examples"].append({
            "message": (r.get('error_message') or "Unknown")[:200],
            "count": r['error_count'],
        })

    for task_type, info in by_type.items():
        if info["total"] >= 3:
            recommendations.append({
                "type": "error",
                "title": f"High failure rate in {task_type}",
                "description": f"{task_type} failed {info['total']} times in {days} days. "
                               f"Most common error: {info['examples'][0]['message']}",
                "evidence": {"error_count": info["total"], "task_type": task_type, "examples": info["examples"][:3]},
                "impact": "high",
                "effort": "medium",
                "source": "error_pattern_analysis",
            })

    return recommendations


def analyze_performance_trends(days: int = 7) -> List[Dict]:
    """Analyze performance trends over the period."""
    since = datetime.now() - timedelta(days=days)

    rows = _execute("""
        SELECT metric_date, total_chats, total_tasks, total_errors,
               avg_response_time_ms, p95_response_time_ms
        FROM assistant_performance_metrics
        WHERE metric_date >= %s
        ORDER BY metric_date ASC
    """, (since,), fetch=True)

    recommendations = []
    if not rows or len(rows) < 2:
        return recommendations

    # Check if errors are trending up
    mid = len(rows) // 2
    first_half_errors = sum(r['total_errors'] or 0 for r in rows[:mid])
    second_half_errors = sum(r['total_errors'] or 0 for r in rows[mid:])

    if second_half_errors > first_half_errors * 1.5 and second_half_errors >= 3:
        recommendations.append({
            "type": "performance",
            "title": "Error rate increasing — investigate root cause",
            "description": f"Errors increased from {first_half_errors} to {second_half_errors} "
                           f"in the last {days} days. Review recent failing tasks.",
            "evidence": {"first_half_errors": first_half_errors, "second_half_errors": second_half_errors},
            "impact": "high",
            "effort": "high",
            "source": "performance_trend_analysis",
        })

    # Check response time degradation
    avg_rts = [r.get('avg_response_time_ms') for r in rows if r.get('avg_response_time_ms')]
    if len(avg_rts) >= 2 and avg_rts[-1] > avg_rts[0] * 1.3:
        recommendations.append({
            "type": "performance",
            "title": "Response time degrading — optimize slow endpoints",
            "description": f"Average response time increased from {avg_rts[0]:.0f}ms to "
                           f"{avg_rts[-1]:.0f}ms. Profile and optimize the slowest endpoints.",
            "evidence": {"first_avg_rt": avg_rts[0], "last_avg_rt": avg_rts[-1]},
            "impact": "medium",
            "effort": "medium",
            "source": "performance_trend_analysis",
        })

    return recommendations


def analyze_confidence_trends(days: int = 7) -> List[Dict]:
    """Analyze AI decision confidence and generate accuracy recommendations."""
    since = datetime.now() - timedelta(days=days)

    rows = _execute("""
        SELECT decision_type, AVG(confidence) as avg_conf, COUNT(*) as cnt
        FROM assistant_decision_log
        WHERE created_at >= %s AND confidence IS NOT NULL
        GROUP BY decision_type
        ORDER BY avg_conf ASC
    """, (since,), fetch=True)

    recommendations = []
    if not rows:
        return recommendations

    for r in rows:
        if r.get('avg_conf', 1) < 0.6 and r.get('cnt', 0) >= 3:
            recommendations.append({
                "type": "accuracy",
                "title": f"Low confidence in {r['decision_type']} — needs improvement",
                "description": f"Average confidence for '{r['decision_type']}' is "
                               f"{r['avg_conf']:.2f} over {r['cnt']} decisions. "
                               f"Consider improving this classifier or adding fallback logic.",
                "evidence": {"decision_type": r['decision_type'], "avg_confidence": r['avg_conf'],
                             "count": r['cnt']},
                "impact": "high",
                "effort": "high",
                "source": "confidence_trend_analysis",
            })

    return recommendations


def analyze_usage_patterns(days: int = 7) -> List[Dict]:
    """Analyze how the assistant is being used."""
    since = datetime.now() - timedelta(days=days)

    # Most used furniture types
    ft_rows = _execute("""
        SELECT furniture_type, COUNT(*) as cnt
        FROM assistant_task_log
        WHERE created_at >= %s AND furniture_type IS NOT NULL
        GROUP BY furniture_type
        ORDER BY cnt DESC
    """, (since,), fetch=True)

    # Tool usage
    tool_rows = _execute("""
        SELECT tool_name, COUNT(*) as cnt, AVG(duration_ms) as avg_dur
        FROM assistant_tool_log
        WHERE created_at >= %s
        GROUP BY tool_name
        ORDER BY cnt DESC
        LIMIT 10
    """, (since,), fetch=True)

    # Backend usage split
    backend_rows = _execute("""
        SELECT backend_used, COUNT(*) as cnt
        FROM assistant_chat_log
        WHERE created_at >= %s AND backend_used IS NOT NULL
        GROUP BY backend_used
    """, (since,), fetch=True)

    recommendations = []

    # Check if Ollama is falling back too much (indicates OpenAI issues)
    for br in (backend_rows or []):
        if br.get('backend_used') == 'Ollama' and br.get('cnt', 0) > 5:
            backends = {b['backend_used']: b['cnt'] for b in (backend_rows or [])}
            total = sum(backends.values())
            ollama_pct = (backends.get('Ollama', 0) / total * 100) if total > 0 else 0
            if ollama_pct > 50:
                recommendations.append({
                    "type": "performance",
                    "title": "Heavy Ollama fallback — check OpenAI API status",
                    "description": f"Ollama handled {ollama_pct:.0f}% of chat requests. "
                                   f"OpenAI may be down, rate-limited, or misconfigured.",
                    "evidence": {"ollama_percentage": ollama_pct, "backend_breakdown": backends},
                    "impact": "high",
                    "effort": "low",
                    "source": "usage_pattern_analysis",
                })

    # Suggest adding support for most-used furniture types
    if ft_rows:
        top_type = ft_rows[0]['furniture_type']
        top_count = ft_rows[0]['cnt']
        recommendations.append({
            "type": "pattern",
            "title": f"'{top_type}' is most used — prioritize accuracy improvements",
            "description": f"The '{top_type}' type was used {top_count} times in {days} days. "
                           f"Focus accuracy tuning, test fixtures, and edge cases on this type first.",
            "evidence": {"furniture_type": top_type, "usage_count": top_count, "all_types": ft_rows},
            "impact": "medium",
            "effort": "low",
            "source": "usage_pattern_analysis",
        })

    return recommendations


def deduplicate_recommendations(recommendations: List[Dict]) -> List[Dict]:
    """Remove duplicate recommendations that already exist in the DB."""
    existing = _execute("""
        SELECT title FROM assistant_improvement_recommendations
        WHERE status IN ('open', 'in_progress')
    """, fetch=True)

    existing_titles = {r['title'] for r in (existing or [])}
    return [r for r in recommendations if r['title'] not in existing_titles]


def store_recommendations(recommendations: List[Dict]):
    """Store new recommendations in the database."""
    for rec in recommendations:
        _execute("""
            INSERT INTO assistant_improvement_recommendations
                (recommendation_type, title, description, evidence, impact, effort, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            rec['type'], rec['title'], rec.get('description'),
            json.dumps(rec.get('evidence', {})),
            rec.get('impact', 'medium'),
            rec.get('effort', 'medium'),
            rec.get('source', 'monitor_worker'),
        ))
        log(f"Stored recommendation: [{rec.get('impact', 'medium')}] {rec['title']}")


def run_analysis_cycle():
    """Run one full analysis cycle: aggregate, analyze, recommend."""
    log("Starting analysis cycle...")

    # 1. Aggregate daily metrics
    try:
        aggregate_daily_metrics()
    except Exception as e:
        log(f"Aggregation failed: {e}", "ERROR")

    # 2. Analyze error patterns
    try:
        err_recs = analyze_error_patterns()
        store_recommendations(deduplicate_recommendations(err_recs))
    except Exception as e:
        log(f"Error pattern analysis failed: {e}", "ERROR")

    # 3. Analyze performance trends
    try:
        perf_recs = analyze_performance_trends()
        store_recommendations(deduplicate_recommendations(perf_recs))
    except Exception as e:
        log(f"Performance trend analysis failed: {e}", "ERROR")

    # 4. Analyze confidence trends
    try:
        conf_recs = analyze_confidence_trends()
        store_recommendations(deduplicate_recommendations(conf_recs))
    except Exception as e:
        log(f"Confidence trend analysis failed: {e}", "ERROR")

    # 5. Analyze usage patterns
    try:
        usage_recs = analyze_usage_patterns()
        store_recommendations(deduplicate_recommendations(usage_recs))
    except Exception as e:
        log(f"Usage pattern analysis failed: {e}", "ERROR")

    log("Analysis cycle complete.")


def print_health_report():
    """Print a quick health summary to stdout (for logging/metrics)."""
    rows = _execute("""
        SELECT COUNT(*) as total_tasks,
               COUNT(*) FILTER (WHERE NOT success) as total_errors,
               COUNT(*) FILTER (WHERE success) as total_ok
        FROM assistant_task_log
        WHERE created_at >= NOW() - INTERVAL '24 hours'
    """, fetch=True)

    if rows:
        r = rows[0]
        total = r.get('total_tasks', 0) or 0
        errors = r.get('total_errors', 0) or 0
        ok = r.get('total_ok', 0) or 0
        error_rate = (errors / total * 100) if total > 0 else 0
        log(f"Health: {ok} ok / {errors} errors ({error_rate:.1f}% error rate) in last 24h")

        open_recs = _execute("""
            SELECT COUNT(*) as cnt FROM assistant_improvement_recommendations WHERE status = 'open'
        """, fetch=True)
        if open_recs:
            log(f"Open recommendations: {open_recs[0].get('cnt', 0)}")


# =============================================================
# Main Loop
# =============================================================

def main():
    log(f"Monitor Worker starting — poll={POLL_INTERVAL_SECONDS}s, "
        f"aggregate={AGGREGATE_INTERVAL_SECONDS}s, analysis={ANALYSIS_INTERVAL_SECONDS}s")

    last_aggregate = 0
    last_analysis = 0
    cycle = 0

    while _running:
        cycle += 1
        now = int(time.time())

        # Quick poll: print health
        try:
            print_health_report()
        except Exception as e:
            log(f"Health report failed: {e}", "ERROR")

        # Aggregate metrics (hourly)
        if now - last_aggregate >= AGGREGATE_INTERVAL_SECONDS:
            try:
                aggregate_daily_metrics()
                last_aggregate = now
            except Exception as e:
                log(f"Metric aggregation failed: {e}", "ERROR")
        
        # Check if error rate > threshold and send webhook alert
        try:
            import urllib.request
            import json as alert_json
            webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")
            if webhook_url:
                alert_data = aggregate_daily_metrics()
                if alert_data and alert_data.get("error_rate", 0) > 10:
                    payload = alert_json.dumps({
                        "text": f"⚠️ CAD Digitizer Alert — Error rate at {alert_data['error_rate']:.0f}%"
                    }).encode()
                    urllib.request.urlopen(webhook_url, data=payload, timeout=5)
        except Exception:
            pass
        
        # Full analysis (every 6 hours)
        if now - last_analysis >= ANALYSIS_INTERVAL_SECONDS:
            run_analysis_cycle()
            last_analysis = now

        log(f"Cycle {cycle} complete — sleeping {POLL_INTERVAL_SECONDS}s")
        time.sleep(POLL_INTERVAL_SECONDS)

    log("Monitor Worker shutting down.")


if __name__ == "__main__":
    main()
