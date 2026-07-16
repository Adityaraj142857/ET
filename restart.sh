#!/usr/bin/env bash
#
# restart.sh — full restart of the Compound Risk Detection project.
#
# Stops any dev server already running on the frontend port, re-syncs the
# Python environment and regenerates the synthetic data + scene.json, makes
# sure frontend deps are installed, then starts the Vite dev server.
#
# Usage:
#   ./restart.sh          # restart on the default port (5173)
#   ./restart.sh 5180     # restart on a specific port

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

PORT="${1:-5173}"

echo "==> Compound Risk Detection: full restart"
echo "    project root: $PROJECT_ROOT"
echo "    port:         $PORT"
echo

# --- 1. Stop anything already running --------------------------------------
echo "==> Stopping any existing dev server on port $PORT..."
EXISTING_PIDS="$(lsof -ti "tcp:$PORT" 2>/dev/null || true)"
if [ -n "$EXISTING_PIDS" ]; then
  kill $EXISTING_PIDS 2>/dev/null || true
  sleep 1
  echo "    stopped pid(s): $EXISTING_PIDS"
else
  echo "    nothing running on port $PORT"
fi
# Belt-and-suspenders: sweep any stray Vite process for this project even if
# it ended up on a different port than expected.
pkill -f "$PROJECT_ROOT/frontend/node_modules/.bin/vite" 2>/dev/null || true

# --- 2. Python side: sync deps + regenerate synthetic data ------------------
echo
echo "==> Syncing Python environment (uv sync)..."
uv sync

echo
echo "==> Regenerating synthetic data + risk engine output + scene.json..."
uv run python main.py

# --- 3. Frontend deps --------------------------------------------------
cd "$PROJECT_ROOT/frontend"
echo
if [ -d node_modules ]; then
  echo "==> Frontend dependencies already installed, skipping npm install."
else
  echo "==> Installing frontend dependencies (first run)..."
  # package.json currently pins vite@^8 alongside @vitejs/plugin-react@^4.3.2,
  # whose peerDependencies only go up to vite ^7 -- a plain install ERESOLVEs
  # on a truly fresh node_modules. Fall back to --legacy-peer-deps rather than
  # hard-failing; this is a pre-existing package.json mismatch worth fixing
  # upstream, not something this script should silently mask beyond unblocking.
  npm install || {
    echo "    plain npm install failed (peer dependency conflict) -- retrying with --legacy-peer-deps"
    npm install --legacy-peer-deps
  }
fi

# --- 4. Start the dev server ------------------------------------------
echo
echo "==> Starting frontend dev server on http://localhost:$PORT ..."
echo "    press Ctrl+C to stop"
echo
exec npm run dev -- --port "$PORT"
