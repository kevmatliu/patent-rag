#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_VENV="$BACKEND_DIR/.venv"
BACKEND_ENV_FILE="$BACKEND_DIR/.env"
MOLSCRIBE_MODEL_PATH="$BACKEND_DIR/models/molscribe/swin_base_char_aux_1m680k.pth"
CHEMBERTA_MODEL_DIR="$BACKEND_DIR/models/chemberta"
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

echo "==> Downloading model files if needed"
python - <<EOF
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

molscribe_path = Path(r"$MOLSCRIBE_MODEL_PATH")
chemberta_dir = Path(r"$CHEMBERTA_MODEL_DIR")

molscribe_path.parent.mkdir(parents=True, exist_ok=True)
chemberta_dir.mkdir(parents=True, exist_ok=True)

if molscribe_path.exists():
    print(f"MolScribe checkpoint already present at {molscribe_path}")
else:
    print("Downloading MolScribe checkpoint...")
    downloaded = hf_hub_download(
        repo_id="yujieq/MolScribe",
        filename="swin_base_char_aux_1m680k.pth",
        local_dir=str(molscribe_path.parent),
        local_dir_use_symlinks=False,
    )
    print(f"MolScribe checkpoint downloaded to {downloaded}")

chemberta_required = [
    "config.json",
    "merges.txt",
    "pytorch_model.bin",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "vocab.json",
]
if all((chemberta_dir / name).exists() for name in chemberta_required):
    print(f"ChemBERTa files already present at {chemberta_dir}")
else:
    print("Downloading ChemBERTa model files...")
    downloaded_dir = snapshot_download(
        repo_id="seyonec/ChemBERTa-zinc-base-v1",
        allow_patterns=chemberta_required,
        local_dir=str(chemberta_dir),
        local_dir_use_symlinks=False,
    )
    print(f"ChemBERTa model downloaded to {downloaded_dir}")
EOF

echo "==> Writing backend environment file"
cat > "$BACKEND_ENV_FILE" <<EOF
DATABASE_URL=sqlite:///$BACKEND_DIR/app.db
FAISS_INDEX_PATH=$BACKEND_DIR/faiss_index/index.bin
FAISS_MAPPING_PATH=$BACKEND_DIR/faiss_index/mapping.json
MODEL_DEVICE=cpu
MOLSCRIBE_MODEL_PATH=$MOLSCRIBE_MODEL_PATH
CHEMBERTA_MODEL_PATH=$CHEMBERTA_MODEL_DIR
UPLOAD_DIR=$BACKEND_DIR/uploads
EXTRACTED_IMAGE_DIR=$BACKEND_DIR/uploads/extracted
SEARCH_TMP_DIR=$BACKEND_DIR/uploads/search_tmp
EOF

echo "==> Installing frontend dependencies"
cd "$FRONTEND_DIR"
npm install

echo
echo "Setup complete."
echo "Next:"
echo "  1. Start the backend with:  bash $ROOT_DIR/start_backend.sh"
echo "  2. Start the frontend with: bash $ROOT_DIR/start_frontend.sh"
