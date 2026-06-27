#!/bin/sh
# =============================================================================
# Node API Entrypoint
# Starts both servers:
#   1. Backend-Node (Prisma/Express) on port 4000 — Reference Library CRUD
#   2. Backend (Express/PG) on port 5001 — Session management + upload proxy
# =============================================================================
set -e

echo "=== Node API Entrypoint ==="

# ---- Wait for Postgres using TCP socket check ----
echo "Waiting for Postgres to be ready..."
for i in $(seq 1 30); do
  if node -e "require('net').connect({host:'${PG_HOST:-postgres}',port:${PG_PORT:-5432}}).on('connect',()=>process.exit(0)).on('error',()=>process.exit(1)).setTimeout(2000,()=>process.exit(1))" 2>/dev/null; then
    echo "Postgres is ready!"
    break
  fi
  echo "Waiting for Postgres... ($i/30)"
  sleep 2
done

echo "Running database migrations..."
cd /app/node-api

# Run Prisma migrations (or push on first deploy)
# The database might still be initializing - retry a couple times
for i in 1 2 3; do
  if npx prisma migrate deploy 2>/dev/null || npx prisma db push 2>/dev/null; then
    echo "Database schema is up to date."
    break
  fi
  echo "Migration attempt $i failed, retrying in 3s..."
  sleep 3
done

echo "Starting servers..."

# Start the backend-node (Reference Library API) on port 4000
cd /app/node-api
echo "Starting Reference Library API on port 4000..."
npx tsx src/server.ts &
PID1=$!

# Start the legacy backend (Session management) on port 5001
cd /app/backend
echo "Starting Session Management API on port 5001..."
PORT=5001 node server.js &
PID2=$!

echo "=== Both servers started ==="
echo "  Reference Library API: http://localhost:4000"
echo "  Session Management:    http://localhost:5001"

# Trap and forward signals (use signal names without SIG prefix for POSIX sh)
trap "echo 'Shutting down...'; kill $PID1 $PID2 2>/dev/null; wait $PID1 $PID2; exit 0" TERM INT

# Watch both processes — exit if one dies (Docker will restart the container)
while true; do
  if ! kill -0 $PID1 2>/dev/null; then
    echo "Reference API died. Shutting down."
    kill $PID2 2>/dev/null
    exit 1
  fi
  if ! kill -0 $PID2 2>/dev/null; then
    echo "Session API died. Shutting down."
    kill $PID1 2>/dev/null
    exit 1
  fi
  sleep 5
done
