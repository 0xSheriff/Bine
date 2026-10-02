#!/usr/bin/env bash
# Starts the standalone BINE Sampler worker, FastAPI backend (port 8000), and Vite frontend (port 5173).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() {
  echo ""
  echo "Stopping BINE sampler, backend, and frontend..."
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "⏱️  Starting BINE Standalone Sampler Worker ..."
(
  cd "$ROOT_DIR/backend"
  DEV_DNS_FALLBACK="${DEV_DNS_FALLBACK:-true}" .venv/bin/python -m bine.sampler
) &

echo "🚀 Starting BINE Backend (FastAPI) on http://127.0.0.1:8000 ..."
(
  cd "$ROOT_DIR/backend"
  DEV_DNS_FALLBACK="${DEV_DNS_FALLBACK:-true}" .venv/bin/uvicorn bine.app:app --host 127.0.0.1 --port 8000
) &

echo "🌐 Starting BINE Frontend (Vite) on http://localhost:5173 ..."
(
  cd "$ROOT_DIR/frontend"
  npm run dev
) &

wait
