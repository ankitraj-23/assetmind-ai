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
