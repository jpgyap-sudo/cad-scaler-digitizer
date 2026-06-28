#!/bin/bash
# =============================================================================
# CAD Scaler Digitizer — Deploy Script
# =============================================================================
# NOTE: For DigitalOcean VPS / cloud deployment, use:
#   curl -fsSL https://raw.githubusercontent.com/jpgyap-sudo/cad-scaler-digitizer/master/scripts/deploy-vps.sh | bash
# =============================================================================
set -e

echo "=== CAD Scaler Digitizer — Local Deploy ==="
echo ""
echo "For cloud/VPS deployment, run:"
echo "  bash scripts/deploy-vps.sh"
echo ""

# Check Docker
if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker is not installed."
  echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
  exit 1
fi

# Pull latest
git pull origin master 2>/dev/null || true

# Ensure .env exists
if [ ! -f .env ]; then
  cp .env.production.template .env
  echo "Created .env from template."
  echo "Edit .env before continuing:"
  echo "  nano .env"
  exit 1
fi

# Build and start
echo "Building and starting containers..."
docker compose up -d --build

echo ""
echo "=== Deploy complete ==="
echo "  Frontend: http://localhost:8080"
echo "  Node API: http://localhost:4000/health"
echo "  Python:   http://localhost:8001/health"
echo "  MCP:      http://localhost:3003/health"
echo ""
echo "  API Docs: http://localhost:4000/api/docs"
echo ""
