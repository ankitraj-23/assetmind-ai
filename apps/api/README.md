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
