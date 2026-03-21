#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not installed. Please install Node.js and npm first."
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Frontend dependencies are missing."
  echo "Run: bash $ROOT_DIR/setup_local.sh"
  exit 1
fi

cd "$FRONTEND_DIR"

echo "Starting frontend on http://127.0.0.1:5173"
exec npm run dev -- --host 127.0.0.1 --port 5173
