# AssetMind AI

**AssetMind AI** turns scattered industrial documents — maintenance work orders,
inspection reports, OEM manuals, SOPs, compliance checklists, datasheets and RCA
findings — into an **asset-centric operations brain**: queryable, citation-backed,
and explainable. Built for the ET AI Hackathon 2026 (PS 8 — Unified Asset &
Operations Brain). See [docs/project-brief.md](docs/project-brief.md).

Everything below runs **fully locally and deterministically** — no external API
keys required. Adding a `GEMINI_API_KEY` upgrades embeddings and answer
generation to Gemini without any code change (see [Modes](#modes)).

---

## What it does

- **Canonical ingestion** — one pipeline for PDF / TXT / CSV / XLSX. Uploads via
  `POST /documents` and the demo seed use the *same* code path and the *same*
  embedding contract, so uploaded documents are immediately visible to Copilot.
- **Knowledge graph** — extracts equipment tags → assets, entities, mentions and
  `asset → document / chunk / entity` edges in Postgres + pgvector.
- **Copilot (RAG)** — hybrid vector + keyword retrieval (RRF → rerank → MMR) with
  grounded, filename-level citations. `POST /rag/chat` and a compatible `POST /query`.
- **Agents** — evidence-backed **RCA**, deterministic **compliance** gap analysis,
  and a real Markdown **evidence package** with a working download.
- **Evaluation** — a genuine benchmark runner that reuses the production retrieval
  path, plus `GET /evaluation/latest` and a live Evaluation page.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Liveness probe |
| `GET`  | `/dashboard/summary` | Live corpus / risk counts |
| `POST` | `/documents` | Upload + ingest a document |
| `GET`  | `/assets/{tag}` `/documents` `/timeline` `/facts` `/graph` | Asset views |
| `POST` | `/rag/chat` | Copilot answer with citations |
| `POST` | `/query` | Backward-compatible RAG answer |
| `POST` | `/agents/rca` | Root-cause analysis |
| `GET`  | `/agents/compliance/assets/{tag}` | Compliance gaps for an asset |
| `POST` | `/agents/evidence-package` | Generate a citation-backed package |
| `GET`  | `/evaluation/latest` | Latest genuine benchmark result |

Full contract: [docs/api-contract.md](docs/api-contract.md).
Architecture + diagram: [docs/architecture.md](docs/architecture.md).

---

## Setup — the one authoritative path

Prerequisites: **Python 3.12+**, **Node 18+**, **Docker** (for local Postgres),
`curl` and `jq` (for the smoke test).

```bash
# 1. Clone
git clone <this-repo> assetmind-ai && cd assetmind-ai

# 2. Create the backend virtual environment
cd apps/api
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate

# 3. Install runtime + dev requirements
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Start Postgres (pgvector) — from the repo root, in another shell
cd ../.. && docker compose up -d db

# 5. Configure env + migrate  (placeholder local credentials only)
export PERSISTENCE_BACKEND=postgres
export DATABASE_URL=postgresql+psycopg://assetmind:assetmind@127.0.0.1:5432/assetmind
cd apps/api && alembic upgrade head

# 6. Seed the demo corpus (idempotent; --reset for a demo-only clean)
python -m scripts.seed_demo

# 7. Run the backend
uvicorn app.main:app --reload --port 8000     # http://127.0.0.1:8000/docs

# 8. Run the frontend (another shell)
cd ../../apps/web && npm install && npm run dev  # http://localhost:3000

# 9. Run the genuine benchmark (writes data/benchmark/results_sample.json)
cd ../../apps/api && python -m scripts.run_benchmark

# 10. Run the end-to-end smoke test (backend must be running)
cd ../.. && API_BASE_URL=http://127.0.0.1:8000 ./scripts/final_smoke_test.sh
```

A copy-paste demo walkthrough is in
[docs/final-demo-runbook.md](docs/final-demo-runbook.md).

---

## Modes

| | Deterministic local (default) | Gemini |
|---|---|---|
| Trigger | `GEMINI_API_KEY` unset | `GEMINI_API_KEY` set |
| Embeddings | `local-hashing-v1` (384-dim) | `gemini-embedding-2` |
| Answers | extractive, no LLM | `gemini-2.5-flash` |
| External calls | none | Gemini API |

The **embedding contract is unified**: whatever provider indexes a document is
the provider used to query it, so uploads are always retrievable. Switching modes
requires **no re-code** — only re-seeding/re-indexing under the new provider.

---

## Benchmark (genuine, deterministic local mode)

Retrieval is measured with the *same* production pipeline as `/rag/chat`; no
metrics are fabricated. Latest run over the full 8-document demo corpus:

| Metric | All 40 questions | Answerable (40) |
|--------|------------------|-----------------|
| Top-1 source hit | 35.0% | 35.0% |
| Top-3 source hit | 72.5% | 72.5% |
| Asset hit | 87.5% (35/40) | 87.5% |
| Absent-corpus questions | 0 | — |

See [docs/evaluation.md](docs/evaluation.md) for methodology and the corpus decision.

---

## Synthetic demo data

The demo plant is **synthetic hackathon data**. Three documents complete the
compressor (C-220) and RCA scenarios and are generated reproducibly by
[data/generate_extended_corpus.py](data/generate_extended_corpus.py):

- `compressor_datasheet.xlsx`, `rca_findings_2025.csv`, `sop_compressor_operations.pdf`

The pump PDFs are generated by [data/generate_pdfs.py](data/generate_pdfs.py).
No proprietary or copyrighted standard text is reproduced — standards (API 617,
ISO 10816, OISD-137, Factories Act) are referenced by number only.

---

## Repository structure

```
apps/
  api/          FastAPI backend (ingestion, RAG, agents, evaluation)
    scripts/    seed_demo.py, run_benchmark.py, verify_*.py, backfill_*.py
    alembic/    database migrations
  web/          Next.js + TypeScript + Tailwind frontend
data/
  documents/    the 8-document demo corpus (5 real synthetic + 3 extended)
  benchmark/    questions.json + results_sample.json (genuine benchmark output)
  generate_*.py reproducible document generators
docs/           architecture, deployment, runbook, deck outline, evaluation
scripts/        final_smoke_test.sh
docker-compose.yml   local Postgres (pgvector)
```

---

## Deployment

Backend Dockerfile, migration/start commands, health check, CORS and the
ephemeral evidence-export limitation are documented in
[docs/deployment.md](docs/deployment.md).

## Security

No secrets are committed. `.env` files are gitignored; the demo uses placeholder
local Postgres credentials only. Set real credentials via environment variables
on your platform.

Keep exact presentation narration, judge-preparation notes and internal team
strategy outside the repository.
