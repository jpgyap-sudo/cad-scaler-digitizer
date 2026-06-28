#!/bin/bash
# =============================================================================
# CAD Scaler Digitizer — One-Click VPS Deploy Script
# Copy-paste this into your DigitalOcean Droplet Console.
# =============================================================================
set -euo pipefail

echo "=========================================="
echo "🚀 CAD Scaler Digitizer — VPS Deploy"
echo "=========================================="

# --- Config (edit these) ---
DOMAIN="cad.abcx124.xyz"
REPO="https://github.com/jpgyap-sudo/cad-scaler-digitizer.git"
BRANCH="master"

# --- 1. Install Docker if missing ---
if ! command -v docker &>/dev/null; then
  echo "📦 Installing Docker..."
  curl -fsSL https://get.docker.com | bash
  usermod -aG docker "$SUDO_USER" 2>/dev/null || true
fi

# --- 2. Install Docker Compose if missing ---
if ! command -v docker compose &>/dev/null; then
  echo "📦 Installing Docker Compose..."
  DOCKER_CONFIG=${DOCKER_CONFIG:-/usr/local/lib/docker/cli-plugins}
  mkdir -p "$DOCKER_CONFIG"
  curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o "$DOCKER_CONFIG/docker-compose"
  chmod +x "$DOCKER_CONFIG/docker-compose"
fi

# --- 3. Clone project ---
echo "📦 Cloning project..."
cd /opt
if [ -d "cad-digitizer" ]; then
  cd cad-digitizer && git pull
else
  git clone "$REPO" cad-digitizer
  cd cad-digitizer
fi

# --- 4. Create .env from template ---
if [ ! -f .env ]; then
  echo "📝 Creating .env (fill in secrets below)..."
  cat > .env << 'EOF'
# =============================================================================
# CAD Scaler Digitizer — Production Environment Variables
# =============================================================================
FRONTEND_PORT=443
NODE_API_PORT=4000
PYTHON_WORKER_PORT=8001
DOMAIN=cad.abcx124.xyz
AUTH_TOKEN=change-this-to-a-random-64-char-hex-string

# PostgreSQL
PG_USER=cad_app
PG_PASSWORD=change-this-to-a-strong-password
PG_DATABASE=cad_reference_library

# Redis
REDIS_PASSWORD=change-this-to-another-strong-password

# DigitalOcean Spaces
SPACES_ENDPOINT=https://sgp1.digitaloceanspaces.com
SPACES_REGION=sgp1
SPACES_BUCKET=homeatelierspaces
SPACES_KEY=REPLACE_WITH_YOUR_SPACES_KEY
SPACES_SECRET=REPLACE_WITH_YOUR_SPACES_SECRET
SPACES_CDN_BASE=https://homeatelierspaces.sgp1.cdn.digitaloceanspaces.com/cad-reference-library

# Qdrant
QDRANT_URL=http://qdrant:6333

# Python Engine
PYTHON_ENGINE_URL=http://python-worker:8001
PYTHON_WORKER_URL=http://python-worker:8001

# CORS (comma-separated allowed origins)
CORS_ORIGIN=https://cad.abcx124.xyz
EOF
  echo "  ✅ .env created"
  echo "  ⚠️  IMPORTANT: Edit .env and set AUTH_TOKEN, PG_PASSWORD, REDIS_PASSWORD"
  echo "     Run: nano /opt/cad-digitizer/.env"
  if [ -t 0 ]; then
    nano .env
  fi
fi

# --- 5. Get SSL certificate ---
echo "🔐 Setting up SSL for $DOMAIN..."
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  docker run --rm -p 80:80 -v /etc/letsencrypt:/etc/letsencrypt \
    certbot/certbot certonly --standalone \
    -d "$DOMAIN" --non-interactive --agree-tos \
    --email admin@"$DOMAIN" || true
  if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo "  ⚠️ SSL failed. Set up DNS A record for $DOMAIN → $(curl -s ifconfig.me)"
    echo "  Then re-run: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
  fi
else
  echo "  ✅ SSL cert exists"
fi

# --- 6. Pull images and start ---
echo "🐳 Pulling images and starting services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# --- 7. Auto-renew SSL (cron) ---
if ! crontab -l 2>/dev/null | grep -q certbot; then
  (crontab -l 2>/dev/null; echo "0 3 * * * docker run --rm -v /etc/letsencrypt:/etc/letsencrypt certbot/certbot renew && docker compose -f /opt/cad-digitizer/docker-compose.yml -f /opt/cad-digitizer/docker-compose.prod.yml restart frontend") | crontab -
  echo "  ✅ SSL auto-renew cron added"
fi

# --- 8. Verify ---
echo ""
echo "=========================================="
echo "✅ DEPLOY COMPLETE"
echo "=========================================="
echo ""
echo "  Frontend: https://$DOMAIN"
echo "  API Docs: https://$DOMAIN/api/docs"
echo "  Node API: http://localhost:4000/health"
echo "  Python:   http://localhost:8001/health"
echo ""
echo "  📊 Check status: docker compose -f /opt/cad-digitizer/docker-compose.yml ps"
echo "  📜 View logs:    docker compose -f /opt/cad-digitizer/docker-compose.yml logs -f"
echo ""
EOF
