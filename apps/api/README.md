# AssetMind AI — API

FastAPI backend for AssetMind AI. Implements document ingestion (PDF, TXT, CSV, XLSX),
vector search, RAG query answering, and an asset knowledge-graph layer.

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
-> 70/30 hybrid vector + keyword retrieval
-> metadata boost for answerable_questions and asset_tags
-> reciprocal rank fusion + MMR diversity selection
-> fetch linked raw parent chunks
-> Gemini answer generation using raw parent chunk evidence
-> answer + citations + confidence
```

Follow-up chat flow:

```text
session summary + last few messages + new user message
-> standalone retrieval query rewrite
-> same hybrid retrieval pipeline
-> Gemini answer generation with recent conversation context
-> store user/assistant messages, citations, confidence, and retrieved chunk IDs
```

The chat endpoint stores full message history in Postgres, but it does not send
the full history to Gemini. Rewriting and answer generation use only a compact
session summary plus the most recent messages so long conversations do not keep
growing the prompt. LLM-based session compression starts once the session has
more than 6 stored messages, which is the 4th user question in a normal
user/assistant chat. Older messages are merged into `chat_sessions.summary`,
while the latest 6 messages remain available as raw recent context.

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
$env:GEMINI_GENERATION_MODEL="gemini-2.5-flash"
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

Ask a follow-up aware chat question:

```powershell
curl.exe -X POST http://localhost:8000/rag/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"What could be possible reasons for P-101 to fail?\",\"top_k\":7}"
```

Pass the returned `session_id` for follow-ups:

```powershell
curl.exe -X POST http://localhost:8000/rag/chat `
  -H "Content-Type: application/json" `
  -d "{\"session_id\":\"chat-id-from-previous-response\",\"message\":\"How can we prevent that?\",\"top_k\":7}"
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
## Week 2 — Ingestion & Asset-Scoped Retrieval

This branch (`feature/week2-ingestion-asset-retrieval`) adds:

- **CSV and XLSX ingestion** — `POST /documents` now accepts `.csv` and `.xlsx` files.
  Each spreadsheet row (or cell) becomes a chunk. For XLSX, all sheets are ingested and
  the `sheet_name` is recorded in the facts store.
- **Structured fact extraction** — regex-based extraction of 8 industrial fact types
  from chunk text: `equipment_tag`, `asset_type`, `failure_mode`, `maintenance_action`,
  `inspection_reading`, `sop_reference`, `compliance_reference`, `spare_part`,
  `risk_phrase`, `open_action`. Facts are persisted in `storage/facts.json` (JSON mode).
- **Asset-scoped retrieval** — `POST /query` accepts an optional `asset_tag` field.
  Chunks mentioning the tag receive a `+0.15` similarity boost so they rank above
  equally-similar but unrelated chunks.
- **Query intent detection** — six deterministic intent classes (`procedure`,
  `failure_rca`, `maintenance_history`, `inspection`, `compliance`, `general`).
  Source documents matching the intent receive a `+0.08` score boost.
- **Citation deduplication & source diversity** — no chunk_id appears twice in
  results; at most 3 chunks come from any single document.
- **`related_assets`** — `QueryResponse` now includes a list of other equipment tags
  found in the retrieved chunks (excluding the queried `asset_tag`).
- **`page_number`** on citations — PDF chunks carry a page number extracted from
  `[Page N]` markers embedded during ingestion.

### Verify ingestion & retrieval

```bash
cd apps/api
# 1. Verify CSV/XLSX/TXT ingestion and fact extraction
PERSISTENCE_BACKEND=json .venv/Scripts/python -m scripts.verify_ingestion

# 2. Verify asset-scoped search, intent detection, and full query pipeline
PERSISTENCE_BACKEND=json .venv/Scripts/python -m scripts.verify_asset_scoped_retrieval
```

Both scripts print `ALL CHECKS PASSED` on success and exit non-zero on any failure.

---

## Week 2 — Knowledge Graph

This branch adds a read-only **asset knowledge-graph** layer over the ingested corpus:

- Repository helpers that derive an asset → document/chunk/entity graph, a per-asset
  timeline (with `event_type` / `severity` / `reason_tags`), a deterministic risk
  summary, and a dashboard v2 summary.
- Read-only asset/graph/risk/dashboard routes (see
  [docs/api-contract.md](../../docs/api-contract.md), Week 2 section).
- Idempotent `KnowledgeEdge` rows materialized alongside asset mentions, plus a
  backfill script for pre-existing mentions.

These features require `PERSISTENCE_BACKEND=postgres` and a `DATABASE_URL`. In
JSON/local mode the endpoints return safe, empty responses. See
[docs/week2-knowledge-graph.md](../../docs/week2-knowledge-graph.md) for the model and
heuristics.

All commands below are run from `apps/api/`.

### Run migrations

```bash
PERSISTENCE_BACKEND=postgres DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind .venv/bin/python -m alembic upgrade head
```

### Backfill knowledge edges

Creates any missing `KnowledgeEdge` rows from existing `AssetMention` rows. Safe to run
repeatedly (only inserts edges that are absent).

```bash
PERSISTENCE_BACKEND=postgres DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind .venv/bin/python -m scripts.backfill_knowledge_edges
```

### Verify the knowledge graph (read-only)

Prints the dashboard summary, discovered assets, and a `P-101` inspection (related
documents, classified timeline sample, graph counts, and risk summary).

```bash
PERSISTENCE_BACKEND=postgres DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind .venv/bin/python -m scripts.verify_knowledge_graph
```

### Verify the dashboard summary (read-only)

Prints the dashboard counts, risk breakdown, top assets by mentions, and top risky
assets.

```bash
PERSISTENCE_BACKEND=postgres DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind .venv/bin/python -m scripts.verify_dashboard_summary
```

### Useful curl commands

With the server running against Postgres:

```bash
# Dashboard summary (v2 risk fields included)
curl http://127.0.0.1:8000/dashboard/summary

# Top risky assets (deterministic heuristics)
curl "http://127.0.0.1:8000/assets/risk-summary?limit=10"

# Documents, timeline, and facts for one asset
curl http://127.0.0.1:8000/assets/P-101/documents
curl http://127.0.0.1:8000/assets/P-101/timeline
curl http://127.0.0.1:8000/assets/P-101/facts

# Derived graph and its summary
curl "http://127.0.0.1:8000/assets/P-101/graph?include_chunks=false"
curl "http://127.0.0.1:8000/assets/P-101/graph?relation_type=mentioned_in"
curl http://127.0.0.1:8000/assets/P-101/graph/summary
```
