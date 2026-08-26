#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

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
  if ! python -c "import fastapi, uvicorn, pydantic, sqlalchemy, psycopg, firebase_admin" >/dev/null 2>&1; then
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

bootstrap_stockfish() {
  local engine_setting="${MATCH_PREDICTOR_ENGINE_ENABLED:-true}"
  case "$engine_setting" in
    0|false|False|FALSE|no|No|NO|off|Off|OFF)
      return
      ;;
  esac

  local engine_path="${STOCKFISH_PATH:-$ROOT_DIR/.stockfish/stockfish}"
  if [[ -x "$engine_path" ]] || command -v stockfish >/dev/null 2>&1; then
    return
  fi

  echo "Installing the optional Classic Match Predictor engine..."
  if ! STOCKFISH_INSTALL_PATH="$engine_path" "$ROOT_DIR/scripts/install_stockfish.sh"; then
    echo "Warning: Stockfish was not installed. Chass! will run without live Match Predictor results."
  fi
}

bootstrap_fairy_stockfish() {
  local engine_setting="${MATCH_PREDICTOR_ENGINE_ENABLED:-true}"
  case "$engine_setting" in
    0|false|False|FALSE|no|No|NO|off|Off|OFF)
      return
      ;;
  esac

  local engine_path="${FAIRY_STOCKFISH_PATH:-$ROOT_DIR/.stockfish/fairy-stockfish}"
  if [[ -x "$engine_path" ]] || command -v fairy-stockfish >/dev/null 2>&1; then
    return
  fi

  echo "Installing the optional static-variant Match Predictor engine..."
  if ! FAIRY_STOCKFISH_INSTALL_PATH="$engine_path" "$ROOT_DIR/scripts/install_fairy_stockfish.sh"; then
    echo "Warning: Fairy-Stockfish was not installed. Standard Stockfish analysis and gameplay remain available."
  fi
}

cleanup() {
  if [[ "${CLEANUP_COMPLETE:-0}" == "1" ]]; then
    return
  fi
  CLEANUP_COMPLETE=1
  trap - INT TERM EXIT

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
bootstrap_stockfish
bootstrap_fairy_stockfish

trap cleanup INT TERM EXIT

echo "Starting backend on http://localhost:$BACKEND_PORT ..."
(
  cd "$ROOT_DIR"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  uvicorn backend.main:app --reload --reload-dir "$ROOT_DIR/backend" --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:$FRONTEND_PORT ..."
(
  cd "$ROOT_DIR/frontend"
  VITE_API_URL="${VITE_API_URL:-http://localhost:$BACKEND_PORT}" npm run dev -- --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

echo
echo "Chass! is running:"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo "Press Ctrl+C to stop both."

wait_for_first_exit
