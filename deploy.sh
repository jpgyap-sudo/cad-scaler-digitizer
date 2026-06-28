#!/bin/bash
# Deploy script for CAD Scaler Digitizer - runs on VPS
set -e

cd /opt/cad-digitizer

echo "=== Pulling latest code ==="
git pull

echo "=== Setting up PostgreSQL ML tables ==="
su - postgres -c "psql -d cad_digitizer -f /opt/cad-digitizer/backend-python/scripts/create_ml_tables.sql" 2>/dev/null || true

echo "=== Setting up PostgreSQL monitoring tables ==="
su - postgres -c "psql -d cad_digitizer -f /opt/cad-digitizer/backend-python/scripts/create_monitoring_tables.sql" 2>/dev/null || true

echo "=== Rebuilding Docker containers ==="
OPENAI_API_KEY=$(cat .env | grep OPENAI_API_KEY | cut -d= -f2-)
docker compose up -d --build

echo "=== Running tests ==="
PYTHONPATH=/opt/cad-digitizer/backend-python python3 -m pytest /opt/cad-digitizer/backend-python/tests/ -v 2>/dev/null || \
PYTHONPATH=/opt/cad-digitizer/backend-python python3 /opt/cad-digitizer/backend-python/tests/test_dxf_exporter.py

echo "=== Training ML model ==="
docker exec cad-python-worker pip install -q scikit-learn skl2onnx onnxruntime 2>/dev/null || true
docker exec -e PYTHONPATH=/app cad-python-worker python /app/scripts/train_classifier.py

echo "=== Verifying API ==="
sleep 3
curl -s http://localhost:8001/health
echo ""
curl -s http://localhost:8000/api/ml/status
echo ""

echo "=== Deploy complete ==="
