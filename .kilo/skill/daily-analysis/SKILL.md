# Daily Analysis Skill — CAD Digitizer Accuracy Monitoring

## Purpose
Analyzes comparison results, detects accuracy trends, and logs improvement recommendations every 24h.

## Location
- Script: `scripts/daily-analysis.sh`
- Reports: `/var/log/cad-reports/`
- Log: `/var/log/cad-reports/daily-summary.log`

## What It Checks
1. Comparison results from Postgres (last 7 days)
2. Error distribution (edge_mismatch, misaligned_dim, etc.)
3. Score trends (weekly avg over last 30 days)
4. Digitizer parameter changes
5. Auto-applies calibration corrections when enough data available

## Install Cron
```bash
# Add to crontab on VPS:
0 2 * * * /opt/cad-digitizer/scripts/daily-analysis.sh >> /var/log/cad-reports/cron.log 2>&1

# Or via docker exec (if using host cron):
0 2 * * * docker exec cad-python-worker /app/scripts/daily-analysis.sh
```

## Recommendations Generated
- When avg score < 0.6 → CRITICAL: check digitizer calibration
- When edge overlap < 0.1 → Add AI segmentation (SAM)
- When dimension deviation > 50% → Check unit conversion
- When >10 edge_mismatch errors → Lower Canny thresholds

## Frontend Tabs
- **Analytics**: accuracy trends, error breakdown, score distribution
- **Improvements**: known bugs, ranked improvement categories, effort estimates
