# AssetMind AI — Project State Audit

- **Audit timestamp:** 2026-07-21T22:57Z
- **Branch audited:** `dev` → working branch `feature/final-12-day-completion`
- **Base commit:** `c4c05f8` (Merge PR #33 — final AssetMind hackathon release)
- **Working-tree state at audit:** one uncommitted change — `data/benchmark/results_sample.json`
  (a genuine benchmark re-run: `answerable_top1_source_hit_rate` 0.35 → 0.40, newer
  `generated_at`). Preserved, not discarded.

## Branch state

- `dev` (`c4c05f8`) holds the newest complete implementation. `origin/main` (`97266fb`)
  already merged `dev` via PR #34, so production `main` is current. Local `main`
  (`9b53f6a`) is a stale ref only.
- All feature branches (`week3-agent-ui-live-integration`, `rca-maintenance-agent`,
  `rag-ingestion`, `csv-ingestion-performance`, etc.) are already merged into `dev`.
  `git log --left-right --cherry-pick dev...feature/week3-agent-ui-live-integration`
  shows only the merge commit unique to `dev` — no unmerged valuable work left behind.
- No work exists only locally except the benchmark re-run above.

## Architecture summary

- **Backend:** FastAPI (`apps/api/app`). Routers: health, documents, search, query,
  rag, agents, assets, dashboard, evaluation. Persistence via SQLAlchemy + pgvector
  (`PERSISTENCE_BACKEND=postgres`), Alembic migrations present.
- **Canonical embedding contract:** `app/rag/embeddings.py` is the single seam used by
  ingestion, retrieval, query, benchmark, reindex, RCA evidence. It wraps the
  deterministic `app/services/embeddings.py` (`local-hashing-v1`, 384-dim) for local
  mode and Gemini (`gemini-embedding-2`) when `GEMINI_API_KEY` is set. Not a duplicate —
  a layered fallback. Retrieval filters to compatible vectors by `embedding_model`.
- **Frontend:** Next.js 16 (`apps/web`). Pages: `/`, assets, `assets/[id]`, compliance,
  copilot, documents, `documents/[id]`, evaluation, rca, upload. `lib/api.ts` centralizes
  API calls; `NEXT_PUBLIC_API_BASE_URL` with a hosted production fallback.

## Database (host category: **Neon**, no credentials shown)

- Host: managed Postgres (Neon, `ap-southeast-1`), SSL: **yes**. (Specific endpoint
  and credentials are kept out of the repo.)
- Active embedding provider/model: **local / local-hashing-v1** (no Gemini key locally).
- Counts: documents **8**, pages **7**, chunks **497**, entities **896**, assets **60**,
  mentions **896**, knowledge edges **2688**.
- Chunks by embedding_model: `local-hashing-v1: 497` (single model — internally
  comparable). Null embeddings: **0**. Duplicate filenames: **0**. 8 unique demo docs.
- `reindex_documents --dry-run`: re-index 0, skipped(already local) 497, no-embedding 0,
  **failures 0** → **0 incompatible chunks** (the previously-reported 173+2 incompatible
  chunks are already resolved).

## Tests / build

- Backend: `compileall app scripts` OK; `pytest -q` → **53 passed**.
- Frontend: `tsc --noEmit` → **pass**; `next build` → **pass** (10 routes).
- `next lint` is **broken** under Next 16 (command removed; no ESLint configured). Day-10 fix.

## Public deployment

- `GET /health` → `{"status":"ok"}`.
- `GET /dashboard/summary` → 8 docs / 497 chunks / 60 assets / 896 entities / 896
  mentions / 2688 edges — **matches the DB and repo** (deployment is current).
- `GET /evaluation/latest` → available, `results_sample.json`, provider `local`, model
  `local-hashing-v1`, answer_provider `deterministic-fallback`.
- Frontend `https://assetmind-ai.tech` → 308 (apex redirect, healthy). CORS
  `access-control-allow-origin: https://assetmind-ai.tech` present.
- Note: public eval serves the committed benchmark (top1 0.35 / top3 0.725). The local
  re-run (top1 0.40) is not yet deployed.

## Benchmark metrics (committed `results_sample.json`)

- 40 total / 40 answerable, absent-corpus 0, top1 0.35, **top3 0.725**, **asset-hit 0.875**,
  avg latency 207 ms, p95 222 ms, 11 failed, provider local / local-hashing-v1,
  answer_provider deterministic-fallback. Meets floor (top3 ≥ 0.65, asset ≥ 0.85).

## Security

- Tracked env files: only `apps/api/.env.example`, `apps/web/.env.example` (placeholders).
- Real `apps/api/.env` is gitignored. Secret scan (excluding examples/docs) → **no leaks**.

## Milestone matrix

| Milestone | Required outcome | Existing evidence | Gap | Required files | Acceptance test | Status |
|---|---|---|---|---|---|---|
| D1–2 Ingestion unification | One canonical ingestion + embedding contract, formats TXT/MD/PDF/CSV/XLSX, 0 incompatible chunks | `rag/embeddings.py` seam; 497/497 local-hashing-v1; dry-run 0 incompatible | none material | — | reindex --dry-run failures=0 | ✅ Done (verify) |
| D3–4 RCA | Generic evidence-grounded RCA, safe unknown asset, no cross-asset leak | `routes/agents.py:/rca`, `services/rca.py`, `tests/test_rca.py` | none material | — | pytest test_rca | ✅ Done (verify) |
| D5–6 Compliance + evidence pkg | Grounded gaps, downloadable substantive package | `/compliance/gaps`, `/compliance/assets/{tag}`, `/evidence-package(+download)`, `tests/test_compliance.py` | none material | — | pytest test_compliance | ✅ Done (verify) |
| D7–8 Retrieval + evaluation | Benchmark on prod path, live `/evaluation/latest`, live eval page | benchmark uses `/rag/chat`; eval endpoint live; eval page fetches live | commit improved re-run | data/benchmark | curl /evaluation/latest | ✅ Done (verify) |
| D9 Failure intelligence | `/assets/{tag}/failure-intelligence`, `/dashboard/failure-hotspots`, evidence-backed, UI | **absent** | **build endpoints + tests + UI** | routes/assets.py, routes/dashboard.py, services, web | pytest + verifier | ❌ Missing |
| D10 Testing + cleanup | tests/build pass, working lint, no dead/mock/secret | tests+build pass | broken `next lint` | apps/web/package.json | npm run lint | ⚠️ Lint fix |
| D11 Deployment | Verified Vercel+Render+Neon, docs | live + current; `docs/deployment.md` | verify smoke test | docs/deployment.md | final_smoke_test.sh | ✅ Verify |
| D12 Submission materials | architecture/deck/runbook/checklists | architecture, deck-outline, runbook present | 3 checklists missing | docs/*.md | files exist | ⚠️ 3 docs |

## Remaining gaps (actionable)

1. **Day 9** — Add evidence-backed failure-intelligence (`GET /assets/{tag}/failure-intelligence`,
   `GET /dashboard/failure-hotspots`) + tests + verifier + minimal UI surface.
2. **Day 10** — Repair the broken `next lint` script (Next 16 removed `next lint`).
3. **Day 12** — Create `final-submission-checklist.md`, `screenshot-checklist.md`.
4. Commit the preserved benchmark re-run and refresh the served results.

No critical blockers: DB identity confirmed (Neon), no secret exposure, no destructive
migration required, ≤15 files per milestone.
