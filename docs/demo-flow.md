# AssetMind AI — Week 1 Demo Flow

A short, repeatable runbook for the Week 1 demo: ingest an industrial document and ask
the Copilot a question that returns a citation-backed answer.

**Demo path:** Upload → Documents → Document Detail → Copilot

## Prerequisites

- Python 3.11+
- Node.js 18+
- Two terminals (one for the backend, one for the frontend)

## 1. Start the backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Verify it is up:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","service":"assetmind-ai-api"}
```

Interactive API docs: http://127.0.0.1:8000/docs

## 2. Start the frontend

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000

> If the backend is not on `http://localhost:8000`, set `NEXT_PUBLIC_API_BASE_URL`
> before starting the frontend.

## 3. Upload the sample document

1. Go to the **Upload** page.
2. Upload `sample-data/demo_plant/pump_p101_note.txt`.
3. Confirm the upload succeeds (the document is sent to `POST /documents`).

## 4. Inspect Documents

1. Go to the **Documents** page (`GET /documents`).
2. Confirm `pump_p101_note.txt` appears in the list with its metadata.

## 5. Open the Document Detail

1. Click into the document to open the **Document Detail** page.
2. Confirm the text **chunks** are shown (`GET /documents/{id}/chunks`).
3. Confirm the **embedding** previews are shown
   (`GET /documents/{id}/embeddings`, model `local-hashing-v1`, dimension 384).

## 6. Ask the Copilot

1. Go to the **Copilot** page.
2. Ask: **"Why is Pump P-101 vibrating?"** (sent to `POST /query`).
3. Confirm an answer is returned describing the likely cause (shaft misalignment after
   the recent mechanical seal replacement, leading to bearing wear).
4. **Verify the citation:** the answer should cite `pump_p101_note.txt` by filename.

## Notes

- Uploaded originals and ingestion metadata are written to local `storage/`, which is
  **gitignored** — nothing is committed.
- Embeddings and the query answer are **deterministic local placeholders** (no external
  model calls). They are designed to be swapped for real models later without changing
  the API contract — see [api-contract.md](api-contract.md).
