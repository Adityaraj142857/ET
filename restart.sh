#!/usr/bin/env bash
#
# restart.sh — full restart of the Compound Risk Detection project.
#
# Stops any dev server already running on the frontend port and the RAG
# backend port, re-syncs the Python environment (including the `rag` dep
# group -- fastapi/uvicorn/faiss/sentence-transformers -- so the Safety
# Intelligence Assistant doesn't 502 because a plain `uv sync` dropped it)
# and regenerates the synthetic data + scene.json, makes sure frontend deps
# are installed, starts the RAG backend, then starts the Vite dev server.
#
# Usage:
#   ./restart.sh          # restart on the default port (5173)
#   ./restart.sh 5180     # restart on a specific port
#
# RAG backend logs: logs/rag_server.log
# Ctrl+C stops both the frontend and the RAG backend.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

PORT="${1:-5173}"
RAG_PORT=8000

echo "==> Compound Risk Detection: full restart"
echo "    project root: $PROJECT_ROOT"
echo "    frontend port: $PORT"
echo "    RAG backend port: $RAG_PORT"
echo

RAG_PID=""
cleanup() {
  if [ -n "$RAG_PID" ] && kill -0 "$RAG_PID" 2>/dev/null; then
    echo
    echo "==> Stopping RAG backend (pid $RAG_PID)..."
    kill "$RAG_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

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

echo "==> Stopping any existing RAG backend on port $RAG_PORT..."
EXISTING_RAG_PIDS="$(lsof -ti "tcp:$RAG_PORT" 2>/dev/null || true)"
if [ -n "$EXISTING_RAG_PIDS" ]; then
  kill $EXISTING_RAG_PIDS 2>/dev/null || true
  sleep 1
  echo "    stopped pid(s): $EXISTING_RAG_PIDS"
else
  echo "    nothing running on port $RAG_PORT"
fi

# --- 2. Python side: sync deps + regenerate synthetic data ------------------
# --all-groups pulls in both `dev` and `rag` groups. A plain `uv sync` only
# installs the default group and will silently uninstall fastapi/uvicorn/
# faiss/sentence-transformers if they were previously present, which is
# exactly what caused the RAG chatbot to 502 (backend process couldn't start
# because `uvicorn` was gone from .venv).
echo
echo "==> Syncing Python environment (uv sync --all-groups)..."
uv sync --all-groups

echo
echo "==> Regenerating synthetic data + risk engine output + scene.json..."
uv run python main.py

# --- 2b. Start the RAG backend ----------------------------------------------
echo
mkdir -p logs
echo "==> Starting RAG backend on http://localhost:$RAG_PORT ..."
uv run uvicorn rag_pipeline.server:app --port "$RAG_PORT" > logs/rag_server.log 2>&1 &
RAG_PID=$!

echo "    waiting for it to become ready (loads the embedding model, can take ~15-30s)..."
READY=0
for _ in $(seq 1 60); do
  if curl -s -o /dev/null -m 1 "http://127.0.0.1:$RAG_PORT/docs"; then
    READY=1
    break
  fi
  if ! kill -0 "$RAG_PID" 2>/dev/null; then
    break
  fi
  sleep 1
done
if [ "$READY" = "1" ]; then
  echo "    RAG backend ready (pid $RAG_PID)"
else
  echo "    WARNING: RAG backend did not come up within 60s -- check logs/rag_server.log"
fi

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
echo "    press Ctrl+C to stop (also stops the RAG backend)"
echo
# Not exec'd: the RAG backend cleanup trap needs this shell to still be
# around to run when the frontend dev server exits or is interrupted.
npm run dev -- --port "$PORT"
