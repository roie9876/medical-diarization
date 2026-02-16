#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# run_all.sh — Start backend + frontend with restart support
#
# Usage:  ./run_all.sh
# ──────────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CONTROL_DIR="/tmp/medical_diarization_ctl"
mkdir -p "$CONTROL_DIR"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; NC='\033[0m'
BACKEND_PID=0
FRONTEND_PID=0

# ── Port helpers ──────────────────────────────────────────────

is_port_free() {
  # Returns 0 (true) if the port is free, 1 (false) if in use
  ! lsof -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1
}

find_free_port() {
  local preferred=$1
  local port=$preferred
  local max_attempts=20
  local attempt=0

  while ! is_port_free "$port"; do
    echo -e "${YELLOW}  Port $port is in use, trying next...${NC}" >&2
    port=$((port + 1))
    attempt=$((attempt + 1))
    if [[ $attempt -ge $max_attempts ]]; then
      echo -e "${RED}  Could not find a free port after $max_attempts attempts (started at $preferred)${NC}" >&2
      exit 1
    fi
  done
  echo "$port"
}

# Resolve available ports
BACKEND_PORT=$(find_free_port 8000)
FRONTEND_PORT=$(find_free_port 5173)

export BACKEND_PORT FRONTEND_PORT

cleanup() {
  echo -e "\n${CYAN}Shutting down...${NC}"
  [[ $BACKEND_PID -gt 0 ]]  && kill $BACKEND_PID  2>/dev/null || true
  [[ $FRONTEND_PID -gt 0 ]] && kill $FRONTEND_PID 2>/dev/null || true
  rm -f "$CONTROL_DIR/restart-backend" "$CONTROL_DIR/restart-frontend"
  rm -f "$CONTROL_DIR/backend.pid" "$CONTROL_DIR/frontend.pid"
  wait 2>/dev/null || true
  echo -e "${GREEN}Stopped.${NC}"
  exit 0
}
trap cleanup EXIT INT TERM

# ── Start helpers ─────────────────────────────────────────────

start_backend() {
  echo -e "${CYAN}[backend]  Starting FastAPI on :${BACKEND_PORT}${NC}"
  cd "$ROOT/web/backend"
  FRONTEND_PORT="$FRONTEND_PORT" "$ROOT/.venv/bin/python" -m uvicorn main:app --reload --port "$BACKEND_PORT" &
  BACKEND_PID=$!
  echo $BACKEND_PID > "$CONTROL_DIR/backend.pid"
  cd "$ROOT"
}

start_frontend() {
  echo -e "${CYAN}[frontend] Starting Vite on :${FRONTEND_PORT}${NC}"
  cd "$ROOT/web/frontend"
  VITE_BACKEND_PORT="$BACKEND_PORT" VITE_PORT="$FRONTEND_PORT" npx vite --host --port "$FRONTEND_PORT" &
  FRONTEND_PID=$!
  echo $FRONTEND_PID > "$CONTROL_DIR/frontend.pid"
  cd "$ROOT"
}

restart_backend() {
  echo -e "${CYAN}[backend]  Restarting...${NC}"
  [[ $BACKEND_PID -gt 0 ]] && kill $BACKEND_PID 2>/dev/null || true
  wait $BACKEND_PID 2>/dev/null || true
  sleep 0.5
  start_backend
}

restart_frontend() {
  echo -e "${CYAN}[frontend] Restarting...${NC}"
  [[ $FRONTEND_PID -gt 0 ]] && kill $FRONTEND_PID 2>/dev/null || true
  wait $FRONTEND_PID 2>/dev/null || true
  sleep 0.5
  start_frontend
}

# ── Main ──────────────────────────────────────────────────────

start_backend
start_frontend

echo ""
echo -e "${GREEN}Backend:   http://localhost:${BACKEND_PORT}${NC}"
echo -e "${GREEN}Frontend:  http://localhost:${FRONTEND_PORT}${NC}"
echo -e "${GREEN}Control:   $CONTROL_DIR${NC}"
echo ""

# Watch for restart signal files (written by the backend /api/admin/* endpoints)
while true; do
  if [[ -f "$CONTROL_DIR/restart-backend" ]]; then
    rm -f "$CONTROL_DIR/restart-backend"
    restart_backend
  fi

  if [[ -f "$CONTROL_DIR/restart-frontend" ]]; then
    rm -f "$CONTROL_DIR/restart-frontend"
    restart_frontend
  fi

  # If either process dies unexpectedly, restart it
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}[backend]  Process died — restarting${NC}"
    start_backend
  fi
  if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}[frontend] Process died — restarting${NC}"
    start_frontend
  fi

  sleep 1
done
