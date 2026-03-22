#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

if [ -d "$BACKEND_DIR/.venv" ]; then
  VENV_DIR="$BACKEND_DIR/.venv"
elif [ -d "$BACKEND_DIR/.venv_sys" ]; then
  VENV_DIR="$BACKEND_DIR/.venv_sys"
else
  echo "No backend virtual environment found."
  echo "Run: bash $ROOT_DIR/setup_local.sh"
  exit 1
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "Backend .env file is missing."
  echo "Run: bash $ROOT_DIR/setup_local.sh"
  exit 1
fi

set -a
source "$BACKEND_DIR/.env"
set +a

if [ ! -f "$MOLSCRIBE_MODEL_PATH" ]; then
  echo "MolScribe model file was not found:"
  echo "  $MOLSCRIBE_MODEL_PATH"
  echo "Update backend/.env or run bash $ROOT_DIR/setup_local.sh"
  exit 1
fi

if [ ! -d "$CHEMBERTA_MODEL_PATH" ]; then
  echo "ChemBERTa model directory was not found:"
  echo "  $CHEMBERTA_MODEL_PATH"
  echo "Update backend/.env or run bash $ROOT_DIR/setup_local.sh"
  exit 1
fi

export PYTHONPATH="$BACKEND_DIR"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

cd "$BACKEND_DIR"

echo "Starting backend on http://127.0.0.1:8000"
exec "$VENV_DIR/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
