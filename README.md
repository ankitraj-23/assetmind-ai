# AssetMind AI

AI-powered Industrial Knowledge Intelligence platform — ET AI Hackathon 2026, PS 8
(Unified Asset & Operations Brain). See [docs/project-brief.md](docs/project-brief.md)
for full context.

## Overview

AssetMind AI turns scattered industrial documents (maintenance records, inspection
reports, operating notes, PDFs) into an asset-centric "operations brain" that is
queryable and citation-backed. The Week 1 build establishes the RAG foundation:
ingest documents, extract and chunk text, embed the chunks, and answer questions with
citations back to the source files.

## Week 1 capabilities

**Backend (`apps/api`, FastAPI):**

- `POST /documents` — upload a PDF/text file; extract, chunk, and embed it.
- `GET /documents` — list ingested documents.
- `GET /documents/{id}/chunks` — view a document's text chunks.
- `GET /documents/{id}/embeddings` — view embedding metadata + vector previews.
- `GET /search?q=...` — retrieve the most similar chunks for a query.
- `POST /query` — citation-backed answer assembled from retrieved chunks.

See [docs/api-contract.md](docs/api-contract.md) for the full endpoint contract.

**Frontend (`apps/web`, Next.js + TypeScript + Tailwind):**

- **Upload** page wired to `POST /documents`.
- **Documents** page wired to `GET /documents`.
- **Document Detail** page showing chunks and embeddings.
- **Copilot** page wired to `POST /query` with filename-based citations.
- **Dashboard / Assets / RCA / Compliance** pages as mock demo views.

## Repository structure

- `apps/api/` — FastAPI backend (document ingestion + RAG endpoints).
- `apps/web/` — Next.js frontend.
- `docs/` — project brief, API contract, and demo flow.
- `sample-data/` — small synthetic industrial sample data for demos.
- `infra/` — deployment and infrastructure notes.

## Backend setup & run

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Health check: `curl http://127.0.0.1:8000/health`
- Interactive docs: http://127.0.0.1:8000/docs

## Frontend setup & run

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000. Set `NEXT_PUBLIC_API_BASE_URL` if the backend is not on
`http://localhost:8000`.

## Demo flow

**Upload → Documents → Document Detail → Copilot**

1. Start the backend and frontend (above).
2. **Upload** `sample-data/demo_plant/pump_p101_note.txt`.
3. Open **Documents** and confirm it appears.
4. Open the **Document Detail** to view its chunks and embeddings.
5. On the **Copilot** page, ask: *"Why is Pump P-101 vibrating?"*
6. Confirm the answer cites `pump_p101_note.txt` by filename.

A step-by-step runbook is in [docs/demo-flow.md](docs/demo-flow.md).

## Notes

- **Local storage is gitignored.** Uploaded originals and ingestion metadata are
  written to local `storage/` directories that are excluded from version control —
  nothing is committed.
- **Deterministic local placeholders.** The current embeddings (`local-hashing-v1`,
  384-dim) and the query answer are deterministic local placeholders with no external
  model calls. They are designed to be swapped for real embedding/RAG models later
  without changing the API contract.
