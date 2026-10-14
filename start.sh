#!/usr/bin/env bash
set -euo pipefail

# ── fun-karaoke startup ───────────────────────────────────────────
# Usage:
#   ./start.sh              → production mode (podman-compose.prod.yml)
#   ./start.sh dev          → development mode with hot-reload
#   ./start.sh build        → rebuild images then start production
#   ./start.sh down         → stop and remove containers
#   ./start.sh logs         → tail logs from all services
# ────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="podman-compose.yml"
COMPOSE_PROD="podman-compose.prod.yml"

# ── helpers ────────────────────────────────────────────────────────

require_podman() {
  if ! command -v podman-compose &>/dev/null; then
    echo "❌ podman-compose not found. Install: pip install podman-compose"
    exit 1
  fi
}

check_env() {
  if [ ! -f "backend/youtube-auth/youtube_cookies.txt" ]; then
    echo "⚠️  backend/youtube-auth/youtube_cookies.txt not found — YouTube downloads may fail (see YOUTUBE_AUTH.md)"
  fi
  if [ ! -d "data" ]; then
    mkdir -p data
    echo "📁 created data/ directory"
  fi
}

# ── commands ───────────────────────────────────────────────────────

cmd_dev() {
  require_podman
  check_env
  echo "🔥 starting development mode (hot-reload)..."
  podman-compose -f "$COMPOSE_FILE" up --build
}

cmd_prod() {
  require_podman
  check_env
  echo "🚀 starting production mode..."
  podman-compose -f "$COMPOSE_PROD" up -d --build
  echo "✅ services running:"
  podman-compose -f "$COMPOSE_PROD" ps
  echo ""
  echo "  Frontend : http://localhost:3000"
  echo "  Backend  : http://localhost:8000"
  echo "  Health   : http://localhost:8000/health"
}

cmd_build() {
  require_podman
  check_env
  echo "🔨 rebuilding images..."
  podman-compose -f "$COMPOSE_PROD" build --no-cache
  echo "🚀 starting..."
  podman-compose -f "$COMPOSE_PROD" up -d --force-recreate
  echo "✅ done"
}

cmd_down() {
  require_podman
  echo "🛑 stopping services..."
  podman-compose -f "$COMPOSE_PROD" down 2>/dev/null || true
  podman-compose -f "$COMPOSE_FILE" down 2>/dev/null || true
  echo "✅ stopped"
}

cmd_logs() {
  require_podman
  podman-compose -f "$COMPOSE_PROD" logs -f 2>/dev/null || \
  podman-compose -f "$COMPOSE_FILE" logs -f
}

cmd_restart() {
  cmd_down
  cmd_prod
}

cmd_status() {
  require_podman
  podman-compose -f "$COMPOSE_PROD" ps 2>/dev/null || \
  podman-compose -f "$COMPOSE_FILE" ps 2>/dev/null || \
  echo "no services running"
}

# ── dispatch ───────────────────────────────────────────────────────

case "${1:-}" in
  dev)      cmd_dev ;;
  down)     cmd_down ;;
  build)    cmd_build ;;
  logs)     cmd_logs ;;
  restart)  cmd_restart ;;
  status)   cmd_status ;;
  prod|"")  cmd_prod ;;
  *)
    echo "Usage: $0 {dev|prod|build|down|logs|restart|status}"
    exit 1
    ;;
esac
