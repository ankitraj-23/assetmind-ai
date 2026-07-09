# AssetMind AI — API

Minimal FastAPI backend skeleton for AssetMind AI. At this stage it exposes only a
health check; RAG, database, and document processing are not yet implemented.

## Project layout

```
apps/api/
├── app/
│   ├── core/        # configuration & cross-cutting concerns (empty)
│   ├── routes/      # API routers (empty)
│   ├── services/    # business logic (empty)
│   ├── models/      # pydantic / data models (empty)
│   ├── db/          # database access layer (empty)
│   └── main.py      # FastAPI app + /health
├── requirements.txt
└── README.md
```

## Local setup

Run all commands from `apps/api/`.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the development server
uvicorn app.main:app --reload --port 8000
```

## Verify

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","service":"assetmind-ai-api"}
```

Interactive docs are available at http://127.0.0.1:8000/docs.

## Week 1 RAG backend

Strategy name:

```text
Summary-indexed, layout-aware parent-child RAG over normalized document elements
```

The Gemini-backed RAG API is exposed under `/rag/*` and uses PostgreSQL +
pgvector. It is separate from the existing local JSON `/documents`, `/search`,
and `/query` demo pipeline.

Ingestion flow:

```text
Document
-> normalized DocumentElements
-> atomic visual summaries for non-CSV/non-Markdown sources (no question metadata)
-> layout-aware parent chunks
-> parent summaries with asset_tags + answerable_questions metadata
-> Gemini embeddings for parent summaries
-> PostgreSQL + pgvector storage
```

Retrieval/query flow:

```text
Question
-> Gemini query embedding
-> vector search over parent summary embeddings
-> fetch linked raw parent chunks
-> Gemini answer generation using raw parent chunk evidence
-> answer + citations + confidence
```

CSV rows are extracted as text elements, with each non-empty cell rendered as
`'Column name': value.` and no atomic visual summaries. Atomic visual elements
from non-CSV/non-Markdown sources are summarized before parent summarization.
Those atomic summaries do not carry generated questions. Parent summaries are
then generated from text elements plus atomic visual summaries, and parent
summary metadata includes asset tags plus answerable questions for the parent
chunk. The original visual element evidence is retained separately on the
parent chunk. Only parent summaries are embedded. The final LLM answer is
grounded in raw parent chunks plus original visual element evidence, not in
generated summaries, so citations point back to original sources.

For CSV files, each row becomes its own parent chunk so each work-order record
can be summarized, embedded, retrieved, and cited independently.

PDF visual extraction currently supports:

- embedded PDF images
- table regions detected by PyMuPDF
- significant vector drawing regions rendered from the page

Direct image files (`.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`)
are ingested as visual elements and copied into
`storage/extracted_visuals/<document_id>/` for visual summarization and
answer-time Gemini vision evidence.

Extracted visuals are saved under `storage/extracted_visuals/<document_id>/` by
default. Override with `RAG_VISUAL_STORAGE_DIR` when needed. Simple divider
lines and tiny drawing artifacts are filtered out. Visual summaries are used for
indexing/parent summaries; the original extracted visual files are attached to
Gemini during final answer generation when retrieved.

The current database uses the existing `document_chunks` table for parent
chunks. Raw parent text is stored in `document_chunks.text`; retrieval summary
text, retrieval IDs, parent summary metadata, atomic element summaries, strategy,
element metadata, and source metadata are stored in the JSON metadata column;
the vector column stores the parent summary embedding.
This keeps the schema backward-compatible and avoids a migration.

Required environment variables for RAG:

```powershell
$env:PERSISTENCE_BACKEND="postgres"
$env:DATABASE_URL="postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind"
$env:GEMINI_API_KEY="your_real_key"
```

Optional model overrides:

```powershell
$env:GEMINI_EMBEDDING_MODEL="gemini-embedding-2"
$env:GEMINI_GENERATION_MODEL="gemini-3.5-flash"
$env:RAG_VISUAL_STORAGE_DIR="storage/extracted_visuals"
```

Start Postgres from the repo root:

```powershell
cd C:\Users\vishk\Projects\assetmind-ai
docker compose up -d db
```

Run migrations from `apps/api`:

```powershell
cd C:\Users\vishk\Projects\assetmind-ai\apps\api
alembic upgrade head
```

Ingest the Week 1 dataset after setting `GEMINI_API_KEY`:

```powershell
cd C:\Users\vishk\Projects\assetmind-ai\apps\api
python -m scripts.ingest_week1_dataset
```

Ingest with externally generated parent summaries and replace previous
embeddings:

```powershell
cd C:\Users\vishk\Projects\assetmind-ai\apps\api
.\.venv\Scripts\python.exe -m scripts.ingest_week1_dataset --force-reingest --parent-summaries .\storage\manual_summary_exports\parent_summaries_completed.jsonl
```

Start the backend:

```powershell
uvicorn app.main:app --reload --port 8000
```

Query the RAG API:

```powershell
curl.exe -X POST http://localhost:8000/rag/query `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"What is the maximum allowable vibration velocity for P-101 per OISD-137?\",\"top_k\":5}"
```

Retrieval-only debug endpoint:

```powershell
curl.exe "http://localhost:8000/rag/search?q=P-101%20vibration%20limit&top_k=5"
```

Run source-hit benchmark evaluation:

```powershell
python -m scripts.eval_rag
```

Run answer-generation benchmark evaluation when Gemini quota allows:

```powershell
python -m scripts.eval_rag --generate-answers
```

If `GEMINI_API_KEY` is missing, only the Gemini-dependent RAG scripts/endpoints
return an error. Normal backend startup remains available.

- OCR/scanned PDF extraction is not implemented in Week 1.
- Chart/graph extraction is heuristic: embedded images and significant vector
  regions are captured as atomic regions when possible.
- Parent summary quality depends on `GEMINI_API_KEY`; deterministic passthrough
  parent summaries are used as a fallback.
- Final answers still require retrieved raw text evidence. If raw parent chunks
  do not support an answer, `/rag/query` returns the insufficient-evidence
  response.
