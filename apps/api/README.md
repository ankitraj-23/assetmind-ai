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
-> layout-aware parent chunks
-> retrieval summaries
-> Gemini embeddings for summaries
-> PostgreSQL + pgvector storage
```

Retrieval/query flow:

```text
Question
-> Gemini query embedding
-> vector search over retrieval summary embeddings
-> fetch linked raw parent chunks
-> Gemini answer generation using raw parent chunk evidence
-> answer + citations + confidence
```

Only retrieval summaries are embedded. They are generated to make search better:
they include asset tags, procedures, thresholds, dates, statuses, actions, and
likely query synonyms. The final LLM answer is grounded in raw parent chunks,
not in generated summaries, so citations point back to original source text.

The current database uses the existing `document_chunks` table for parent
chunks. Raw parent text is stored in `document_chunks.text`; retrieval summary
text, retrieval IDs, strategy, element metadata, and source metadata are stored
in the JSON metadata column; the vector column stores the summary embedding.
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

Known limitations:

- OCR/scanned PDF extraction is not implemented in Week 1.
- Image support is schema-ready only (`image_caption` / `ocr_text` elements can
  be added later).
- Retrieval summary quality depends on `GEMINI_API_KEY` for unstructured chunks;
  deterministic passthrough summaries are used as a fallback.
- Final answers still require retrieved raw text evidence. If raw parent chunks
  do not support an answer, `/rag/query` returns the insufficient-evidence
  response.
