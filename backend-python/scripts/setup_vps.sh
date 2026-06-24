#!/bin/bash
# VPS setup script for CAD Scaler Digitizer
set -e

echo "=== Setting up PostgreSQL ML tables ==="
su - postgres -c "psql -d cad_digitizer -f /opt/cad-digitizer/backend-python/scripts/create_ml_tables.sql"

echo "=== Tables created ==="
su - postgres -c "psql -d cad_digitizer -c '\dt'"

echo "=== Starting Node.js backend ==="
cd /opt/cad-digitizer/backend
npm install
nohup node server.js > /var/log/cad-digitizer-node.log 2>&1 &
echo "Node.js backend started on port 5001"

echo "=== Running initial ML training ==="
cd /opt/cad-digitizer
pip install -q scikit-learn skl2onnx onnxruntime 2>/dev/null || true
PYTHONPATH=/opt/cad-digitizer/backend-python python backend-python/scripts/train_classifier.py

echo "=== Setup Complete ==="
