#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_VENV="$BACKEND_DIR/.venv"
BACKEND_ENV_FILE="$BACKEND_DIR/.env"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed. Please install Python 3 first."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "node is not installed or not on PATH. Please install Node.js first."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not installed or not on PATH. Please install Node.js and npm first."
  exit 1
fi

echo "==> Setting up backend virtual environment"
if [ ! -d "$BACKEND_VENV" ]; then
  python3 -m venv "$BACKEND_VENV"
fi

source "$BACKEND_VENV/bin/activate"
python -m pip install -r "$BACKEND_DIR/requirements.txt"

echo "==> Writing backend environment file"
cat > "$BACKEND_ENV_FILE" <<EOF
DATABASE_URL=sqlite:///$BACKEND_DIR/app.db
FAISS_INDEX_PATH=$BACKEND_DIR/faiss_index/index.bin
FAISS_MAPPING_PATH=$BACKEND_DIR/faiss_index/mapping.json
MODEL_DEVICE=cpu
MOLSCRIBE_MODEL_PATH=$BACKEND_DIR/models/molscribe/swin_base_char_aux_1m680k.pth
CHEMBERTA_MODEL_PATH=$BACKEND_DIR/models/chemberta
UPLOAD_DIR=$BACKEND_DIR/uploads
EXTRACTED_IMAGE_DIR=$BACKEND_DIR/uploads/extracted
SEARCH_TMP_DIR=$BACKEND_DIR/uploads/search_tmp
EOF

if [ ! -f "$BACKEND_DIR/models/molscribe/swin_base_char_aux_1m680k.pth" ]; then
  echo "WARNING: MolScribe model checkpoint was not found at:"
  echo "  $BACKEND_DIR/models/molscribe/swin_base_char_aux_1m680k.pth"
fi

if [ ! -d "$BACKEND_DIR/models/chemberta" ]; then
  echo "WARNING: ChemBERTa model directory was not found at:"
  echo "  $BACKEND_DIR/models/chemberta"
fi

echo "==> Installing frontend dependencies"
cd "$FRONTEND_DIR"
npm install

echo
echo "Setup complete."
echo "Next:"
echo "  1. Start the backend with:  bash $ROOT_DIR/start_backend.sh"
echo "  2. Start the frontend with: bash $ROOT_DIR/start_frontend.sh"
