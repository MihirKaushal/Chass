#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .venv-scanner/bin/python ]]; then
  echo "Create .venv-scanner first; see scanner/ml/IMPROVEMENTS.md."
  exit 1
fi
echo "Local experimental scanner: http://127.0.0.1:8001"
echo "Open http://localhost:5173/scanner with the frontend running separately."
exec .venv-scanner/bin/python -m uvicorn scanner.service:app --host 127.0.0.1 --port 8001
