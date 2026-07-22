# AssetMind AI — Final Demo Runbook

Copy-paste steps to bring the full demo up from a clean checkout and verify it end
to end. All commands run in **deterministic local mode** (no API keys).

## 0. Prerequisites

Python 3.12+, Node 18+, Docker, `curl`, `jq`.

## 1. Backend environment

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

## 2. Database

```bash
cd ../.. && docker compose up -d db          # Postgres + pgvector on :5432
export PERSISTENCE_BACKEND=postgres
export DATABASE_URL=postgresql+psycopg://assetmind:assetmind@127.0.0.1:5432/assetmind
cd apps/api && alembic upgrade head
```

## 3. Seed the demo corpus

```bash
python -m scripts.seed_demo          # idempotent
# python -m scripts.seed_demo --reset  # demo-only clean + reseed
```

Expect a counts block: **documents 8**, plus chunks / assets / entities /
mentions / edges and the embedding provider (`local` / `local-hashing-v1`).

## 4. Benchmark (genuine)

```bash
python -m scripts.run_benchmark
```

Expect: Top-3 ≈ 72.5%, Asset hit ≈ 87.5%, absent-corpus **0**, corpus documents 8.
Writes `data/benchmark/results_sample.json`.

## 5. Run backend + frontend

```bash
# shell A
uvicorn app.main:app --reload --port 8000    # docs at /docs

# shell B
cd apps/web && npm install && npm run dev     # http://localhost:3000
```

## 6. Smoke test (backend must be running)

```bash
cd ../.. && API_BASE_URL=http://127.0.0.1:8000 ./scripts/final_smoke_test.sh
```

Expect **All 14 smoke-test checks passed.**

## 7. Click-through

1. **Dashboard** — live counts, risk breakdown.
2. **Assets → P-101** — documents, timeline, facts, graph.
3. **Copilot** — ask *"Why is P-101 repeatedly failing?"* → cited answer.
4. **RCA** — run for P-101; inspect likely causes + evidence.
5. **Compliance** — P-101 gaps with evidence.
6. **Evidence package** — generate + download the Markdown.
7. **Evaluation** — live benchmark, all-vs-answerable, failure categories.

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| `Database error` / connection refused | `docker compose up -d db`; check `DATABASE_URL` |
| Evaluation page: "No benchmark results yet" | run `python -m scripts.run_benchmark` |
| Copilot returns nothing | re-run `python -m scripts.seed_demo` |
| Smoke test `jq` not found | install `jq` |
| Duplicate documents after re-seed | none — seed is idempotent by filename; use `--reset` to rebuild |
