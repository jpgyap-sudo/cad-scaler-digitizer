#!/bin/bash
# =============================================================================
# Daily Analysis — Accuracy Monitoring & Recommendations
# Runs at 2:00 AM via cron. Analyzes comparison results, detects trends,
# and logs improvement recommendations.
#
# Install cron:
#   0 2 * * * /opt/cad-digitizer/scripts/daily-analysis.sh >> /var/log/cad-daily.log 2>&1
# =============================================================================
set -euo pipefail

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DATE=$(date '+%Y-%m-%d')
REPORT_DIR="${REPORT_DIR:-/var/log/cad-reports}"
mkdir -p "${REPORT_DIR}"
REPORT_FILE="${REPORT_DIR}/report-${DATE}.json"
LOG_FILE="${REPORT_DIR}/daily-summary.log"

echo "[${TIMESTAMP}] === CAD Digitizer — Daily Analysis ==="

# ---------------------------------------------------------------------------
# 1. Query comparison results from Postgres
# ---------------------------------------------------------------------------
echo "[1/5] Querying comparison data..."

PG_RESULTS=$(docker compose exec -T postgres psql -U postgres -d cad_reference_library -t -A -F',' <<'SQL'
SELECT 
  COUNT(*) as total,
  ROUND(AVG(overall_score)::numeric, 3) as avg_score,
  ROUND(AVG(edge_overlap_score)::numeric, 3) as avg_edge,
  ROUND(AVG(dimension_deviation_pct)::numeric, 1) as avg_dim_dev
FROM comparison_results
WHERE created_at > NOW() - INTERVAL '7 days';
SQL
)

# ---------------------------------------------------------------------------
# 2. Query error distribution
# ---------------------------------------------------------------------------
echo "[2/5] Analyzing error distribution..."

ERROR_COUNTS=$(docker compose exec -T postgres psql -U postgres -d cad_reference_library -t -A <<'SQL'
WITH errors AS (
  SELECT jsonb_array_elements(errors_json)->>'error_type' as etype
  FROM comparison_results
  WHERE created_at > NOW() - INTERVAL '7 days'
    AND errors_json != '[]'::jsonb
)
SELECT COUNT(*), etype FROM errors GROUP BY etype ORDER BY COUNT(*) DESC;
SQL
)

# ---------------------------------------------------------------------------
# 3. Detect trends (score change over last 30 days)
# ---------------------------------------------------------------------------
echo "[3/5] Detecting trends..."

TREND=$(docker compose exec -T postgres psql -U postgres -d cad_reference_library -t -A <<'SQL'
WITH weekly AS (
  SELECT 
    date_trunc('week', created_at) as week,
    AVG(overall_score) as avg_score,
    COUNT(*) as count
  FROM comparison_results
  WHERE created_at > NOW() - INTERVAL '30 days'
  GROUP BY 1 ORDER BY 1
)
SELECT 
  week::date,
  ROUND(avg_score::numeric, 3),
  count
FROM weekly;
SQL
)

# ---------------------------------------------------------------------------
# 4. Check digitizer parameters for recent changes
# ---------------------------------------------------------------------------
echo "[4/5] Checking parameter changes..."

PARAM_CHANGES=$(docker compose exec -T postgres psql -U postgres -d cad_reference_library -t -A <<'SQL'
SELECT param_key, param_value, updated_at::date
FROM digitizer_parameters
WHERE updated_at > NOW() - INTERVAL '7 days'
ORDER BY updated_at DESC;
SQL
)

# ---------------------------------------------------------------------------
# 5. Generate recommendations
# ---------------------------------------------------------------------------
echo "[5/5] Generating recommendations..."

RECOMMENDATIONS=""

# Read metrics
TOTAL=$(echo "$PG_RESULTS" | cut -d',' -f1)
AVG_SCORE=$(echo "$PG_RESULTS" | cut -d',' -f2)
AVG_EDGE=$(echo "$PG_RESULTS" | cut -d',' -f3)
AVG_DIM_DEV=$(echo "$PG_RESULTS" | cut -d',' -f4)

if [ -z "$TOTAL" ] || [ "$TOTAL" -eq 0 ]; then
  RECOMMENDATIONS="${RECOMMENDATIONS}- No comparisons in last 7 days. Run digitizations to generate training data.\n"
else
  # Score-based recommendations
  if [ "$(echo "$AVG_SCORE < 0.6" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
    RECOMMENDATIONS="${RECOMMENDATIONS}- CRITICAL: Avg score (${AVG_SCORE}) is below 0.6. Check digitizer calibration.\n"
  elif [ "$(echo "$AVG_SCORE < 0.8" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
    RECOMMENDATIONS="${RECOMMENDATIONS}- WARNING: Avg score (${AVG_SCORE}) is below 0.8. Review calibration report.\n"
  fi

  # Edge-overlap recommendations
  if [ "$(echo "$AVG_EDGE < 0.1" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
    RECOMMENDATIONS="${RECOMMENDATIONS}- Edge overlap (${AVG_EDGE}) is very low. Consider adding AI segmentation.\n"
  fi

  # Dimension deviation recommendations
  if [ "$(echo "$AVG_DIM_DEV > 50" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
    RECOMMENDATIONS="${RECOMMENDATIONS}- High dimension deviation (${AVG_DIM_DEV}%). Check unit conversion in dimension extraction.\n"
  fi

  # Error-type recommendations
  while IFS='|' read -r count etype; do
    [ -z "$count" ] && continue
    if [ "$count" -gt 10 ] && echo "$etype" | grep -q "edge"; then
      RECOMMENDATIONS="${RECOMMENDATIONS}- ${count} edge_mismatch errors — lower Canny thresholds or add SAM segmentation.\n"
    fi
    if [ "$count" -gt 5 ] && echo "$etype" | grep -q "dim"; then
      RECOMMENDATIONS="${RECOMMENDATIONS}- ${count} dimension errors — check unit conversion (mm→cm).\n"
    fi
  done <<< "$ERROR_COUNTS"
fi

# Apply calibration if enough data
if [ -n "$TOTAL" ] && [ "$TOTAL" -ge 3 ]; then
  echo "  Applying calibration corrections..."
  docker compose exec -T python-worker python -c "
import urllib.request
r = urllib.request.urlopen('http://localhost:8001/api/calibration/apply', data=b'', timeout=30)
print('Calibration:', r.read().decode()[:200])
" 2>/dev/null || echo "  Calibration skipped"
fi

# ---------------------------------------------------------------------------
# Save report
# ---------------------------------------------------------------------------
cat > "$REPORT_FILE" <<EOF
{
  "date": "$DATE",
  "timestamp": "$TIMESTAMP",
  "comparisons_7d": ${TOTAL:-0},
  "avg_score_7d": ${AVG_SCORE:-0},
  "avg_edge_overlap": ${AVG_EDGE:-0},
  "avg_dim_deviation_pct": ${AVG_DIM_DEV:-0},
  "error_counts": "$(echo "$ERROR_COUNTS" | head -10)",
  "trend_30d": "$(echo "$TREND" | head -10)",
  "parameter_changes": "$(echo "$PARAM_CHANGES" | head -10)",
  "recommendations": "${RECOMMENDATIONS:-No issues detected.}"
}
EOF

echo ""
echo "============================================"
echo "DAILY ANALYSIS COMPLETE — ${DATE}"
echo "  Comparisons (7d): ${TOTAL:-0}"
echo "  Avg Score:       ${AVG_SCORE:-N/A}"
echo "  Avg Edge:        ${AVG_EDGE:-N/A}"
echo "  Avg Dim Dev:     ${AVG_DIM_DEV:-N/A}%"
echo ""
echo "Recommendations:"
printf "%s" "$RECOMMENDATIONS"
echo ""
echo "Report saved: ${REPORT_FILE}"
echo "============================================"

# Log summary
echo "[${TIMESTAMP}] total=${TOTAL:-0} score=${AVG_SCORE:-0} edge=${AVG_EDGE:-0} dim_dev=${AVG_DIM_DEV:-0}" >> "$LOG_FILE"
