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

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
BACKEND_PID=0
FRONTEND_PID=0

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
  echo -e "${CYAN}[backend]  Starting FastAPI on :8000${NC}"
  cd "$ROOT/web/backend"
  "$ROOT/.venv/bin/python" -m uvicorn main:app --reload --port 8000 &
  BACKEND_PID=$!
  echo $BACKEND_PID > "$CONTROL_DIR/backend.pid"
  cd "$ROOT"
}

start_frontend() {
  echo -e "${CYAN}[frontend] Starting Vite on :5173${NC}"
  cd "$ROOT/web/frontend"
  npx vite --host &
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
echo -e "${GREEN}Backend:   http://localhost:8000${NC}"
echo -e "${GREEN}Frontend:  http://localhost:5173${NC}"
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
