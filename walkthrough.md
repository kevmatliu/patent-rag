# v2 Walkthrough

## What is installed

- Backend code lives in `v2/backend/app`
- Frontend code lives in `v2/frontend`
- ChemBERTa model files live in `v2/backend/models/chemberta`
- MolScribe checkpoint files live under `v2/backend/models/molscribe`
- Backend runtime env file lives at `v2/backend/.env`
- Recommended Python env for this machine is `v2/backend/.venv_sys`

## Why `.venv_sys`

This workspace already has a conda Python with the large scientific stack installed. The local backend virtualenv `v2/backend/.venv_sys` uses `--system-site-packages` so it can reuse those packages while still isolating the backend-specific additions such as:

- `sqlmodel`
- `pydantic-settings``
- `MolScribe`
- backend test/runtime helpers

## Backend setup

```bash
cd /Users/kevinliu/Desktop/patent-rag-chem
source v2/backend/.venv_sys/bin/activate
export PYTHONPATH=/Users/kevinliu/Desktop/patent-rag-chem/v2/backend
cd v2/backend
```

The backend already has a concrete `.env` checked in for this workspace:

```bash
cat /Users/kevinliu/Desktop/patent-rag-chem/v2/backend/.env
```

## Model locations

ChemBERTa:

```text
/Users/kevinliu/Desktop/patent-rag-chem/v2/backend/models/chemberta
```

MolScribe:

- point `MOLSCRIBE_MODEL_PATH` at a local MolScribe checkpoint file

## Run the backend

```bash
cd /Users/kevinliu/Desktop/patent-rag-chem/v2/backend
source .venv_sys/bin/activate
export PYTHONPATH=/Users/kevinliu/Desktop/patent-rag-chem/v2/backend
uvicorn app.main:app --reload --port 8000 --reload-dir app
```

Health endpoint:

```text
http://127.0.0.1:8000/api/health
```

## Run the frontend

```bash
cd /Users/kevinliu/Desktop/patent-rag-chem/v2/frontend
npm install
npm run dev
```

## Run backend tests

```bash
cd /Users/kevinliu/Desktop/patent-rag-chem
source v2/backend/.venv_sys/bin/activate
PYTHONPATH=v2/backend v2/backend/.venv_sys/bin/pytest v2/backend/tests -q
```

## Expected flow

1. Paste Google Patents URLs into the Batch Upload page.
2. The backend downloads each patent PDF.
3. `v2/backend/image_extract.py` extracts candidate compound crops.
4. Each crop is stored as a `CompoundImage` row.
5. The Processing page runs MolScribe and ChemBERTa over pending images.
6. Embeddings are saved in SQLite and added to the FAISS index.
7. The Search page runs the same image-to-SMILES-to-embedding path for the query image and returns nearest matches.

## Notes from this machine

- ChemBERTa downloads completed successfully.
- MolScribe package and checkpoint are the only OCR dependency path now.
- The backend code was updated to avoid importing the transformer stack too early, which keeps startup and tests more stable.
