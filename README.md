# Chemical Patent Search Monorepo v2

Local-first chemical patent search with FastAPI, React, SQLite, and FAISS. The backend ingests Google Patents URLs, extracts compound images through the included `image_extract.py`, converts images to SMILES with MolScribe, embeds SMILES with ChemBERTa, persists records in SQLite, and serves image-based similarity search through a CPU FAISS index.

If you just want to get the app running locally, start with [SETUP.md](/Users/kevinliu/Desktop/patent-rag-chem/v2/SETUP.md).

## Structure

```text
v2/
  backend/
    app/
    faiss_index/
    requirements.txt
    .env.example
  frontend/
    src/
    package.json
    tsconfig.json
  shared/
  README.md
```

## Setup

### 1. Review the extractor module

The monorepo already includes the extractor at:

```text
v2/backend/image_extract.py
```

This file is intended to be edited locally if you want to tune extraction behavior. The backend wrapper supports these callable shapes:

- `extract_from_patent(url)`
- `extract_from_patent(url, patent_slug)`
- `extract_from_patent(url, patent_slug, pdf_bytes)`
- `extract_from_scanned_pdf(pdf_bytes)`
- `extract_from_scanned_pdf(pdf_bytes, patent_slug)`
- `extract_images_from_patent(...)`
- `extract_images(...)`

Supported return payloads:

- list of image file paths
- list of `bytes`
- list of PIL images
- list of objects exposing `image_bytes`
- object exposing `get_compounds()`
- object exposing `compounds`

### 2. Configure backend environment

```bash
cd v2/backend
cp .env.example .env
```

Edit `.env` and point the model paths at your local model directories:

```env
DATABASE_URL=sqlite:///./app.db
FAISS_INDEX_PATH=./faiss_index/index.bin
FAISS_MAPPING_PATH=./faiss_index/mapping.json
MODEL_DEVICE=cpu
MOLSCRIBE_MODEL_PATH=/absolute/path/to/local/molscribe/model.ckpt
CHEMBERTA_MODEL_PATH=/absolute/path/to/local/chemberta/model
UPLOAD_DIR=./uploads
EXTRACTED_IMAGE_DIR=./uploads/extracted
SEARCH_TMP_DIR=./uploads/search_tmp
```

`MODEL_DEVICE` is device-aware for future GPU support, but this v2 setup is designed for CPU-only local execution.

## Backend run

```bash
cd v2/backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Or from `v2/`:

```bash
bash start_backend.sh
```

Backend API base URL:

```text
http://127.0.0.1:8000
```

Static extracted images are served from:

```text
/static/...
```

## Frontend run

```bash
cd v2/frontend
npm install
npm run dev
```

Or from `v2/`:

```bash
bash start_frontend.sh
```

Optional frontend environment:

```bash
echo "VITE_API_BASE_URL=http://127.0.0.1:8000" > .env
```

Frontend dev URL:

```text
http://127.0.0.1:5173
```

## How to use the system

1. Start the backend.
2. Open the frontend.
3. Paste one or more Google Patents URLs into the Batch Upload page.
4. Submit the batch to create patent and extracted image records.
5. Open the Processing page and process pending images into SMILES and embeddings.
6. Open the Search page, upload a query image, and inspect the top FAISS matches.

## Local extraction tuning workflow

If you want to tune the patent filtering heuristics locally, use the included harness:

```bash
cd v2/backend
PYTHONPATH=. .venv_sys/bin/python scripts/patent_filter_lab.py US20250042916A1
```

This will:

1. fetch the Google Patents PDF for the patent code you pass in
2. save the PDF to `v2/backend/test-uploads/<PATENT_ID>/<PATENT_ID>.pdf`
3. dump raw candidate crops to `v2/backend/test-uploads/<PATENT_ID>/raw/`
4. dump filtered crops to `v2/backend/test-uploads/<PATENT_ID>/filtered/`
5. write `manifest.json` with per-image metadata like page number, bbox, density, and complexity score
6. write `summary.txt` with the active tuning parameters

Useful tuning flags:

```bash
PYTHONPATH=. .venv_sys/bin/python scripts/patent_filter_lab.py US20250042916A1 \
  --min-width 100 \
  --min-height 100 \
  --density-min 0.008 \
  --density-max 0.16 \
  --dilation-kernel-size 10 \
  --skip-filter
```

Main knobs:

- `--min-width`
- `--min-height`
- `--density-min`
- `--density-max`
- `--dilation-kernel-size`
- `--padding`
- `--binary-threshold`
- `--render-scale`
- `--complexity-bins`
- `--complexity-smooth-sigma`

This harness is intentionally local-only and does not write anything into the app database.

## API endpoints

- `POST /api/patents/batch`
- `POST /api/images/process`
- `POST /api/search/image`
- `GET /api/images/unprocessed-count`
- `GET /api/health`

## FAISS persistence

The backend uses CPU FAISS `IndexFlatL2` and stores artifacts in `v2/backend/faiss_index/`.

- `index.bin` stores the binary FAISS index
- `mapping.json` stores the FAISS row to `CompoundImage.id` mapping

Startup behavior:

- if both files exist and are consistent, they are loaded
- if either file is missing or inconsistent, the index is rebuilt from stored embeddings in SQLite

## Notes on local models

- MolScribe is imported lazily
- ChemBERTa is loaded lazily from the local path specified in `CHEMBERTA_MODEL_PATH`
- the health endpoint reports extractor import failures and missing local model paths clearly
- no cloud inference is used

## Future GPU support

The model services already accept a `device` parameter. To extend this stack for GPU use later, keep the same service boundaries and change the model-loading configuration rather than rewriting the API or repository layers.
