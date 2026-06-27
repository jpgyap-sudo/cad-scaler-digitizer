"""
Training Feedback System
=========================
Uses the Comparison Agent's accumulated error data to:
  1. Aggregate errors by type + furniture type → detect systematic biases
  2. Auto-adjust digitizer parameters (Canny thresholds, scale factors)
  3. Generate correction hints for the OpenCV pipeline
  4. Build calibration reports showing historical improvement

This closes the loop:
  Digitize → Compare → Detect Errors → Adjust Parameters → Digitize Better
"""

import os
import json
import math
import logging
from typing import Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger("training_feedback")

# ---------------------------------------------------------------------------
# Error Aggregation
# ---------------------------------------------------------------------------

# Current parameter state (stored in Postgres, loaded at startup)
_parameter_state: dict[str, Any] = {
    "canny_low": 50,
    "canny_high": 150,
    "edge_dilation_kernel": 3,
    "min_contour_area": 50,
    "scale_correction_factor": 1.0,
    "ocr_confidence_threshold": 0.5,
    "line_merge_distance": 10,
    "correction_history": [],
}

# Furniture-type-specific correction factors
_furniture_corrections: dict[str, dict[str, float]] = defaultdict(dict)

def load_parameter_state():
    """Load parameter state from Postgres."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("SELECT param_key, param_value FROM digitizer_parameters ORDER BY updated_at DESC LIMIT 50")
        for row in cur.fetchall():
            _parameter_state[row[0]] = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        cur.close()
        conn.close()
        logger.info(f"Loaded {len(_parameter_state)} parameters from DB")
    except Exception as e:
        logger.warning(f"Could not load parameters from DB: {e}")


def save_parameter_state():
    """Save parameter state to Postgres."""
    try:
        import psycopg2, json
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS digitizer_parameters (
                id SERIAL PRIMARY KEY,
                param_key TEXT UNIQUE NOT NULL,
                param_value JSONB NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        for key, value in _parameter_state.items():
            if key == "correction_history":
                continue
            cur.execute("""
                INSERT INTO digitizer_parameters (param_key, param_value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (param_key) DO UPDATE SET param_value = EXCLUDED.param_value, updated_at = NOW()
            """, (key, json.dumps(value) if not isinstance(value, str) else value))
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Parameter state saved to DB")
    except Exception as e:
        logger.warning(f"Could not save parameters: {e}")


def aggregate_comparison_errors(
    days_back: int = 7,
    limit: int = 100,
) -> dict[str, Any]:
    """Fetch recent comparison results and aggregate errors.
    
    Returns:
        {
            "total_comparisons": N,
            "error_counts": { error_type: count },
            "error_by_type": { error_type: [(score, description), ...] },
            "avg_score": float,
            "by_furniture_type": { furniture_type: { avg_score, error_counts } },
            "systematic_biases": [ { bias_description, correction_factor, confidence } ]
        }
    """
    result = {
        "total_comparisons": 0,
        "avg_score": 0.0,
        "error_counts": defaultdict(int),
        "error_by_type": defaultdict(list),
        "by_furniture_type": defaultdict(lambda: {"count": 0, "total_score": 0.0, "error_counts": defaultdict(int)}),
        "systematic_biases": [],
        "errors_by_dimension": defaultdict(list),
    }

    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("PG_HOST", "postgres"),
            port=int(os.environ.get("PG_PORT", 5432)),
            dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
            user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "postgres"),
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT product_id, overall_score, edge_overlap_score, entity_match_score,
                   dimension_deviation_pct, errors_json, dimension_comparisons_json
            FROM comparison_results
            WHERE created_at > NOW() - INTERVAL %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (f"{days_back} days", limit))

        scores = []
        for row in cur.fetchall():
            product_id = row[0]
            overall_score = row[1] or 0
            errors = row[5] if isinstance(row[5], (list, dict)) else (json.loads(row[5]) if row[5] else [])
            dim_comparisons = row[6] if isinstance(row[6], (list, dict)) else (json.loads(row[6]) if row[6] else [])

            scores.append(overall_score)
            result["total_comparisons"] += 1

            # Aggregate errors
            for err in errors:
                etype = err.get("error_type", "unknown")
                result["error_counts"][etype] += 1
                result["error_by_type"][etype].append((overall_score, err.get("description", "")))

            # Aggregate dimension deviations
            for dc in dim_comparisons:
                dim_key = dc.get("dimension", "unknown")
                dev = dc.get("deviation_pct", 0)
                if dev > 0:
                    result["errors_by_dimension"][dim_key].append(dev)

        cur.close()
        conn.close()

        result["avg_score"] = sum(scores) / max(len(scores), 1)

        # Detect systematic biases
        for dim_key, deviations in result["errors_by_dimension"].items():
            if len(deviations) >= 3:
                avg_dev = sum(deviations) / len(deviations)
                if avg_dev > 20:
                    direction = "overestimated" if avg_dev > 0 else "underestimated"
                    result["systematic_biases"].append({
                        "dimension": dim_key,
                        "avg_deviation_pct": round(avg_dev, 1),
                        "direction": direction,
                        "sample_count": len(deviations),
                        "correction_factor": round(1.0 - avg_dev / 100, 3),
                        "confidence": min(1.0, len(deviations) / 10),
                    })

    except Exception as e:
        logger.error(f"Failed to aggregate comparison errors: {e}")

    return dict(result)


def generate_correction_hints(
    furniture_type: str = "all",
) -> list[dict[str, Any]]:
    """Generate actionable correction hints from comparison error data.
    
    These hints can be applied to the digitizer's OpenCV pipeline
    or surfaced in the UI for the user to review.
    """
    hints = []
    aggregation = aggregate_comparison_errors(days_back=30, limit=200)

    # Hint 1: Edge overlap too low → adjust Canny thresholds
    if aggregation["total_comparisons"] >= 3:
        avg_edge = sum(
            err.get("edge_overlap_score", 0) for err in []  # need edge score per product
        )
        # Actually get edge scores from recent comparisons
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=os.environ.get("PG_HOST", "postgres"),
                port=int(os.environ.get("PG_PORT", 5432)),
                dbname=os.environ.get("PG_DATABASE", "cad_reference_library"),
                user=os.environ.get("PG_USER", "postgres"),
                password=os.environ.get("PG_PASSWORD", "postgres"),
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT edge_overlap_score FROM comparison_results
                WHERE created_at > NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC LIMIT 20
            """)
            edge_scores = [r[0] for r in cur.fetchall() if r[0] is not None]
            cur.close()
            conn.close()

            if edge_scores:
                avg_edge = sum(edge_scores) / len(edge_scores)
                if avg_edge < 0.2:
                    current_low = _parameter_state.get("canny_low", 50)
                    current_high = _parameter_state.get("canny_high", 150)
                    hints.append({
                        "type": "parameter_adjustment",
                        "parameter": "canny_low",
                        "current_value": current_low,
                        "suggested_value": max(10, current_low - 5),
                        "reason": f"Edge overlap avg {avg_edge:.1%} — lowering Canny threshold to capture more edges",
                        "confidence": min(1.0, len(edge_scores) / 20),
                        "applied": False,
                    })
                    hints.append({
                        "type": "parameter_adjustment",
                        "parameter": "canny_high",
                        "current_value": current_high,
                        "suggested_value": max(30, current_high - 10),
                        "reason": f"Edge overlap avg {avg_edge:.1%} — lowering Canny high threshold",
                        "confidence": min(1.0, len(edge_scores) / 20),
                        "applied": False,
                    })
        except Exception as e:
            logger.warning(f"Edge score fetch failed: {e}")

    # Hint 2: Systematic dimension bias → apply scale correction
    for bias in aggregation.get("systematic_biases", []):
        if bias["confidence"] > 0.5:
            hints.append({
                "type": "scale_correction",
                "dimension": bias["dimension"],
                "avg_deviation_pct": bias["avg_deviation_pct"],
                "correction_factor": bias["correction_factor"],
                "reason": f"Systematic {bias['direction']} by {bias['avg_deviation_pct']}% across {bias['sample_count']} samples",
                "confidence": bias["confidence"],
                "applied": False,
            })

    # Hint 3: Frequent missing lines → reduce min_contour_area
    missing_line_count = aggregation["error_counts"].get("missing_line", 0)
    if missing_line_count >= 5 and aggregation["total_comparisons"] > 0:
        ratio = missing_line_count / aggregation["total_comparisons"]
        if ratio > 0.3:
            current_min = _parameter_state.get("min_contour_area", 50)
            hints.append({
                "type": "parameter_adjustment",
                "parameter": "min_contour_area",
                "current_value": current_min,
                "suggested_value": max(10, int(current_min * 0.7)),
                "reason": f"{ratio:.0%} of comparisons have missing lines — reducing min contour area",
                "confidence": min(1.0, missing_line_count / 20),
                "applied": False,
            })

    return hints


def apply_correction_hints(hints: list[dict]) -> int:
    """Apply auto-acceptable correction hints and update parameter state.
    
    Returns number of hints applied.
    """
    applied = 0
    for hint in hints:
        if hint.get("type") == "parameter_adjustment" and hint.get("confidence", 0) > 0.3:
            param = hint["parameter"]
            suggested = hint["suggested_value"]
            old_val = _parameter_state.get(param)
            _parameter_state[param] = suggested
            _parameter_state.setdefault("correction_history", []).append({
                "parameter": param,
                "old_value": old_val,
                "new_value": suggested,
                "reason": hint.get("reason", ""),
                "confidence": hint.get("confidence", 0),
                "applied_at": datetime.utcnow().isoformat(),
            })
            applied += 1
            logger.info(f"Applied correction: {param} {old_val} → {suggested}")

        elif hint.get("type") == "scale_correction" and hint.get("confidence", 0) > 0.6:
            dim = hint["dimension"]
            factor = hint["correction_factor"]
            key = f"scale_correction_{dim}"
            old_val = _parameter_state.get(key, 1.0)
            _parameter_state[key] = old_val * factor
            _parameter_state.setdefault("correction_history", []).append({
                "parameter": key,
                "old_value": old_val,
                "new_value": old_val * factor,
                "reason": hint.get("reason", ""),
                "confidence": hint.get("confidence", 0),
                "applied_at": datetime.utcnow().isoformat(),
            })
            applied += 1
            logger.info(f"Applied correction: {key} {old_val} → {old_val * factor}")

    if applied > 0:
        save_parameter_state()

    return applied


def get_calibration_report() -> dict[str, Any]:
    """Generate a full calibration report for the UI.
    
    Shows: current parameters, recent comparisons, systematic biases,
    correction history, and recommended actions.
    """
    # Load latest from DB
    load_parameter_state()

    aggregation = aggregate_comparison_errors(days_back=30, limit=200)

    # Run auto-adjust
    hints = generate_correction_hints()
    applied = 0  # don't auto-apply in report mode

    return {
        "current_parameters": {k: v for k, v in _parameter_state.items() if k != "correction_history"},
        "comparison_stats": {
            "total": aggregation["total_comparisons"],
            "avg_score": round(aggregation["avg_score"], 3),
            "error_counts": dict(aggregation["error_counts"]),
        },
        "systematic_biases": aggregation.get("systematic_biases", []),
        "correction_hints": hints,
        "correction_history": _parameter_state.get("correction_history", [])[-20:],
        "recommended_action": "apply" if any(h.get("confidence", 0) > 0.5 for h in hints) else "collect_more_data",
    }


def apply_calibration() -> dict[str, Any]:
    """Auto-apply high-confidence corrections from comparison data.
    
    Returns summary of what was applied.
    """
    hints = generate_correction_hints()
    applied = apply_correction_hints(hints)
    return {
        "hints_generated": len(hints),
        "hints_applied": applied,
        "parameters": {k: v for k, v in _parameter_state.items() if k != "correction_history"},
    }
