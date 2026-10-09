#!/usr/bin/env bash
# ==============================================================================
# BINE Production VPS Deployment & Update Script
# Updates code, installs dependencies, rebuilds frontend & docs, restarts service,
# and verifies /api/health with automatic rollback on failure.
#
# HARD RULES:
# - Zero em-dashes.
# - Never print, copy, or log API keys or secrets.
# ==============================================================================

set -euo pipefail

REPO_DIR="${BINE_REPO_DIR:-/srv/bine}"
BRANCH="${1:-master}"

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  echo "Error: Directory ${REPO_DIR} is not a git repository." >&2
  exit 1
fi

cd "${REPO_DIR}"

PREV_COMMIT=$(git rev-parse HEAD)
echo "Current commit: ${PREV_COMMIT}"
echo "Fetching and pulling branch: ${BRANCH}..."

git fetch origin "${BRANCH}"
git checkout "${BRANCH}"
git pull --ff-only origin "${BRANCH}"

NEW_COMMIT=$(git rev-parse HEAD)
echo "Updated to commit: ${NEW_COMMIT}"

rollback() {
  echo "CRITICAL: Deployment failed! Rolling back to previous commit ${PREV_COMMIT}..."
  git checkout "${PREV_COMMIT}"
  
  if [[ -f "${REPO_DIR}/backend/requirements.txt" ]]; then
    "${REPO_DIR}/backend/.venv/bin/pip" install -r "${REPO_DIR}/backend/requirements.txt" || true
  fi
  npm --prefix "${REPO_DIR}/frontend" run build || true
  npm --prefix "${REPO_DIR}/docs-site" run build || true
  
  sudo systemctl restart bine-api || true
  sudo systemctl reload caddy || true
  echo "Rollback to ${PREV_COMMIT} complete."
  exit 1
}

trap rollback ERR

echo "=== Step 1: Backend Python Environment ==="
if [[ ! -d "${REPO_DIR}/backend/.venv" ]]; then
  echo "Creating virtual environment at ${REPO_DIR}/backend/.venv..."
  python3 -m venv "${REPO_DIR}/backend/.venv"
fi

"${REPO_DIR}/backend/.venv/bin/pip" install --upgrade pip setuptools wheel
"${REPO_DIR}/backend/.venv/bin/pip" install -r "${REPO_DIR}/backend/requirements.txt"
"${REPO_DIR}/backend/.venv/bin/pip" install -e "${REPO_DIR}/backend"

echo "=== Step 2: Build Frontend SPA ==="
npm ci --prefix "${REPO_DIR}/frontend"
npm run build --prefix "${REPO_DIR}/frontend"

echo "=== Step 3: Build Docs Site ==="
npm ci --prefix "${REPO_DIR}/docs-site"
npm run build --prefix "${REPO_DIR}/docs-site"

echo "=== Step 4: Restart API Service & Reload Caddy ==="
sudo systemctl restart bine-api
sudo systemctl reload caddy || sudo systemctl restart caddy

echo "=== Step 5: Health Check Verification ==="
HEALTH_URL="http://127.0.0.1:8000/api/health"
MAX_ATTEMPTS=15
SUCCESS=0

for i in $(seq 1 "${MAX_ATTEMPTS}"); do
  echo "Polling ${HEALTH_URL} (attempt ${i}/${MAX_ATTEMPTS})..."
  if STATUS=$(curl -sS --max-time 2 "${HEALTH_URL}" 2>/dev/null); then
    if echo "${STATUS}" | grep -q '"status":"ok"'; then
      echo "Health check PASSED: ${STATUS}"
      SUCCESS=1
      break
    fi
  fi
  sleep 1
done

if [[ "${SUCCESS}" -ne 1 ]]; then
  echo "Health check failed after ${MAX_ATTEMPTS} attempts."
  # Trigger ERR trap for rollback
  false
fi

trap - ERR

echo "=== Deployment Successful ==="
echo "Commit: ${NEW_COMMIT}"
echo "Health: OK"
exit 0
