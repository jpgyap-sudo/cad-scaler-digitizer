#!/bin/sh
# =============================================================================
# Python Worker Entrypoint
# Starts both:
#   1. FastAPI HTTP server (port 8001) — handles direct requests
#   2. RQ Worker — consumes CAD processing jobs from Redis queue
# =============================================================================
set -e

echo "=== Python Worker Entrypoint ==="

# ---- Wait for Redis ----
echo "Waiting for Redis to be ready..."
for i in $(seq 1 30); do
  if redis-cli -h "${REDIS_HOST:-redis}" ping 2>/dev/null | grep -q PONG; then
    echo "Redis is ready!"
    break
  fi
  echo "Waiting for Redis... ($i/30)"
  sleep 2
done

# ---- Wait for Postgres ----
echo "Waiting for Postgres to be ready..."
for i in $(seq 1 30); do
  if pg_isready -h "${PG_HOST:-postgres}" -p "${PG_PORT:-5432}" -U "${PG_USER:-postgres}" 2>/dev/null; then
    echo "Postgres is ready!"
    break
  fi
  echo "Waiting for Postgres... ($i/30)"
  sleep 2
done

echo "Starting FastAPI server on port ${PORT:-8001}..."
echo "Starting RQ Worker for queue: cad-processing..."

# Start the FastAPI server in background
cd /app
uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8001} --loop asyncio &
FASTAPI_PID=$!

# Start the RQ worker for CAD processing queue
# The worker consumes jobs from 'cad-processing' Redis queue
python -m app.queue_worker &
WORKER_PID=$!

echo "=== Both processes started ==="
echo "  FastAPI: PID $FASTAPI_PID"
echo "  RQ Worker: PID $WORKER_PID"

# Trap and forward signals
trap "echo 'Shutting down...'; kill $FASTAPI_PID $WORKER_PID 2>/dev/null; wait $FASTAPI_PID $WORKER_PID; exit 0" SIGTERM SIGINT

# Watch both processes — exit if one dies
while true; do
  if ! kill -0 $FASTAPI_PID 2>/dev/null; then
    echo "FastAPI server died. Shutting down."
    kill $WORKER_PID 2>/dev/null
    exit 1
  fi
  if ! kill -0 $WORKER_PID 2>/dev/null; then
    echo "Worker died. Shutting down."
    kill $FASTAPI_PID 2>/dev/null
    exit 1
  fi
  sleep 5
done
