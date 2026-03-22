# Local Setup

This guide is written for someone who just wants to `git pull` and run the app locally.

## Before you start

You need these tools installed on your machine:

- `git`
- `python3`
- `npm`

Quick checks:

```bash
git --version
python3 --version
npm --version
```

If all three commands print versions, you are ready.

## 1. Get the latest code

From your repo folder:

```bash
git pull
cd v2
```

## 2. Run the one-time setup script

This installs backend Python packages, downloads the MolScribe and ChemBERTa model files, installs frontend packages, and rewrites `backend/.env` with the local MolScribe-only configuration.

```bash
bash setup_local.sh
```

What this does:

- creates `v2/backend/.venv` if needed
- installs `v2/backend/requirements.txt`
- downloads the MolScribe checkpoint into `v2/backend/models/molscribe/`
- downloads the ChemBERTa model files into `v2/backend/models/chemberta/`
- installs frontend packages in `v2/frontend/node_modules`
- writes `v2/backend/.env` using your local folder paths

## 3. Start the backend

Open one terminal tab or window and run:

```bash
bash start_backend.sh
```

When it is ready, the backend will be available at:

```text
http://127.0.0.1:8000
```

Useful backend page:

```text
http://127.0.0.1:8000/api/health
```

## 4. Start the frontend

Open a second terminal tab or window and run:

```bash
bash start_frontend.sh
```

When it is ready, open:

```text
http://127.0.0.1:5173
```

## 5. Use the app

Suggested first run:

1. Open the `Batch Upload` tab
2. Paste one or more Google Patents links
3. Wait for extraction logs to finish
4. Open `Processing` and process pending compounds
5. Open `Compounds` or `Patents` to inspect what was saved
6. Open `Search` to search by image or SMILES

## Common fixes

### `No backend virtual environment found`

Run:

```bash
bash setup_local.sh
```

### `Backend .env file is missing`

Run:

```bash
bash setup_local.sh
```

### `npm is not installed`

Install Node.js, then open a new terminal and run:

```bash
npm --version
```

### The backend health page says a model path is missing

Open:

```text
v2/backend/.env
```

Make sure these paths point to real files/folders on your machine:

- `MOLSCRIBE_MODEL_PATH`
- `CHEMBERTA_MODEL_PATH`

## Useful commands

Run backend tests:

```bash
cd /path/to/repo
PYTHONPATH=v2/backend v2/backend/.venv/bin/python -m pytest v2/backend/tests -q
```

Run the local patent extraction tuning harness:

```bash
cd /path/to/repo/v2/backend
PYTHONPATH=. .venv/bin/python scripts/patent_filter_lab.py US20250042916A1
```
