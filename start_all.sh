#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  local exit_code=$?

  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi

  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi

  wait >/dev/null 2>&1 || true
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

echo "Starting backend and frontend together..."

bash "$ROOT_DIR/start_backend.sh" &
BACKEND_PID=$!

sleep 2

bash "$ROOT_DIR/start_frontend.sh" &
FRONTEND_PID=$!

echo
echo "Application is starting."
echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://127.0.0.1:5173"
echo
echo "Press Ctrl+C to stop both services."

wait "$BACKEND_PID" "$FRONTEND_PID"
