#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
}

bootstrap_backend() {
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  if ! python -c "import fastapi, uvicorn, pydantic" >/dev/null 2>&1; then
    echo "Installing backend dependencies..."
    pip install -r "$ROOT_DIR/backend/requirements.txt"
  fi
  deactivate >/dev/null 2>&1 || true
}

bootstrap_frontend() {
  if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
    echo "Installing frontend dependencies..."
    (
      cd "$ROOT_DIR/frontend"
      npm install
    )
  fi
}

cleanup() {
  echo
  echo "Shutting down Chass! services..."
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  wait >/dev/null 2>&1 || true
}

wait_for_first_exit() {
  if (( BASH_VERSINFO[0] >= 4 )); then
    wait -n "$BACKEND_PID" "$FRONTEND_PID"
    return
  fi

  # Bash 3.x fallback (default on older macOS): poll until one process exits.
  while true; do
    if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
      wait "$BACKEND_PID" >/dev/null 2>&1 || true
      return
    fi
    if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
      wait "$FRONTEND_PID" >/dev/null 2>&1 || true
      return
    fi
    sleep 1
  done
}

require_command python3
require_command npm

bootstrap_backend
bootstrap_frontend

trap cleanup INT TERM EXIT

echo "Starting backend on http://localhost:$BACKEND_PORT ..."
(
  cd "$ROOT_DIR"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  uvicorn backend.main:app --reload --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:$FRONTEND_PORT ..."
(
  cd "$ROOT_DIR/frontend"
  VITE_API_URL="http://localhost:$BACKEND_PORT" npm run dev -- --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

echo
echo "Chass! is running:"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo "Press Ctrl+C to stop both."

wait_for_first_exit
