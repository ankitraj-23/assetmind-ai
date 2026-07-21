# AssetMind AI — Deployment

Smallest reproducible production setup. **No real credentials appear in this repo**
— everything sensitive is supplied as platform environment variables.

## Target architecture

| Layer | Service | Notes |
|-------|---------|-------|
| Frontend | **Vercel** | Next.js app in `apps/web` |
| Backend | **Render / Railway / Fly.io** | FastAPI container from `apps/api/Dockerfile` |
| Database | **Hosted Postgres + pgvector** (Neon / Supabase) | `pgvector` extension required |

## Backend container

Build from the **repository root** (the image needs the `data/` directory):

```bash
docker build -f apps/api/Dockerfile -t assetmind-api .
```

> Host caveat: on machines where the Docker daemon cannot create default-bridge
> veth pairs (`failed to set up container networking … operation not supported`),
> build and run with host networking: `docker build --network=host …` and
> `docker run --network host …`. This is a daemon/kernel limitation, not a
> Dockerfile issue. Managed platforms (Render/Railway/Fly) are unaffected.

The image preserves the repo layout (`/app/apps/api` + `/app/data`) so the seed,
benchmark and `/evaluation/latest` relative paths resolve unchanged.

### Start command (production)

`apps/api/start.sh` (the image `CMD`) runs migrations, then serves:

```sh
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

- **Migration command** (if your platform runs migrations separately):
  `alembic upgrade head`
- **Health check:** `GET /health` → `{"status":"ok"}`. The Dockerfile also
  declares a container `HEALTHCHECK` hitting `/health`.

### Run locally against host Postgres

```bash
docker run --rm -p 8000:8000 \
  -e PERSISTENCE_BACKEND=postgres \
  -e DATABASE_URL='postgresql+psycopg://assetmind:assetmind@host.docker.internal:5432/assetmind' \
  -e CORS_ORIGINS='["http://localhost:3000"]' \
  assetmind-api
```

### Seeding a deployed database

Seeding is a one-off admin task, not part of normal startup. Run it once against
the production database (locally or via a platform one-off job):

```bash
PERSISTENCE_BACKEND=postgres DATABASE_URL='<prod-url>' python -m scripts.seed_demo
```

## Required environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `PERSISTENCE_BACKEND` | yes | Must be `postgres` in production |
| `DATABASE_URL` | yes | `postgresql+psycopg://…` to pgvector Postgres |
| `CORS_ORIGINS` | yes | JSON array incl. the deployed frontend origin, e.g. `["https://assetmind.vercel.app"]` |
| `STORAGE_DIR` | no | Upload/export dir (default `storage`) |
| `GEMINI_API_KEY` | no | Enables Gemini embeddings/answers; unset ⇒ deterministic local mode |
| `GEMINI_EMBEDDING_MODEL` / `GEMINI_GENERATION_MODEL` | no | Gemini model names |
| `LLM_PROVIDER` | no | `gemini` enables LLM RCA reasoning |
| `BENCHMARK_RESULTS_PATH` | no | Override the file served by `/evaluation/latest` |
| `PORT` | injected | Set by Render/Railway/Fly; honored by `start.sh` |

Full annotated list: [apps/api/.env.example](../apps/api/.env.example).

## CORS

`app/main.py` reads `CORS_ORIGINS` (a JSON array) and configures FastAPI's
`CORSMiddleware`. In production set it to your Vercel domain(s). Do **not** use a
wildcard with credentials.

## Frontend (Vercel)

`apps/web` is a standard Next.js app — Vercel auto-detects the build. Set:

```
NEXT_PUBLIC_API_BASE_URL=https://<your-backend-host>
```

No extra Vercel config file is required. (`src/lib/api.ts` falls back to a
Render URL in production and `http://127.0.0.1:8000` in dev.)

## Evidence-package storage limitation (important)

Evidence packages are written to **`$STORAGE_DIR/exports/` on the local
filesystem**. On container platforms this filesystem is **ephemeral**:

- Generated Markdown packages **do not persist across container restarts or
  redeploys**, and are not shared between multiple instances.
- The generate → download flow works within a single running instance because the
  package is created and fetched from the same container.

For this hackathon build we intentionally do **not** add object storage. If
durable exports are needed later, mount a persistent volume or push the Markdown
to S3/GCS. Until then: **regenerate on demand** (the package is deterministic from
persisted evidence), or return the Markdown inline. We do **not** claim durable
export persistence.

## Live deployment (current)

| Layer | URL / service | Notes |
|-------|---------------|-------|
| Frontend | https://assetmind-ai.tech (Vercel) | apex serves 308→canonical; CORS-allowed origin |
| Backend | https://api.assetmind-ai.tech (Render, onrender.com origin) | FastAPI container |
| Database | Neon Postgres + pgvector (`neondb`, `ap-southeast-1`, SSL required) | 8 demo docs / 497 chunks |

### Exact Render (backend) settings

- **Environment:** Docker. **Dockerfile path:** `apps/api/Dockerfile`.
- **Build context / root directory:** repository root (`.`) — the image needs `data/`.
- **Start command:** provided by the image `CMD` (`./start.sh`); no override needed.
- **Health check path:** `/health`.
- **Instance:** free tier is sufficient for the demo (see limitations below).
- **Environment variables:** `PERSISTENCE_BACKEND=postgres`, `DATABASE_URL` (Neon,
  with `sslmode=require`), `CORS_ORIGINS=["https://assetmind-ai.tech"]`. `PORT` is
  injected by Render and honored by `start.sh`. Leave `GEMINI_API_KEY`/`LLM_PROVIDER`
  unset to keep deterministic local mode (the mode the published benchmark reflects).

### Exact Vercel (frontend) settings

- **Root directory:** `apps/web`. Framework auto-detected (Next.js).
- **Environment variable:** `NEXT_PUBLIC_API_BASE_URL=https://api.assetmind-ai.tech`.
- **Custom domains:** `assetmind-ai.tech` (+ `www`) attached to the Vercel project.

## Migration procedure

Migrations run automatically at container start (`alembic upgrade head` in
`start.sh`). To run them manually against the production DB:

```bash
PERSISTENCE_BACKEND=postgres DATABASE_URL='<prod-url>' alembic upgrade head
```

## Safe production reindex procedure

The reindex re-embeds chunks with the **active** embedding model only; it never
deletes source documents and commits in batches. Always dry-run first and confirm
the host before writing.

```bash
# 1. Confirm host + provider/model and see what WOULD change (no writes):
PERSISTENCE_BACKEND=postgres DATABASE_URL='<prod-url>' \
  python -m scripts.reindex_documents --dry-run

# 2. Only if incompatible chunks > 0, apply (idempotent, resumable, batched):
PERSISTENCE_BACKEND=postgres DATABASE_URL='<prod-url>' \
  python -m scripts.reindex_documents

# 3. Re-run the dry-run — expect: incompatible chunks = 0, failures = 0.
```

Current Neon state: **0 incompatible chunks** (all 497 chunks `local-hashing-v1`),
so no production reindex is required.

## Rollback procedure

- **Backend (Render):** open the service → **Deploys** → pick the previous green
  deploy → **Rollback**. Or push a revert commit to the deploy branch.
- **Frontend (Vercel):** **Deployments** → previous production deployment →
  **Promote to Production** (instant rollback).
- **Database:** migrations are additive; to undo the most recent one use
  `alembic downgrade -1` against `DATABASE_URL` (review the migration first).

## Public smoke test

```bash
API_BASE_URL=https://api.assetmind-ai.tech scripts/final_smoke_test.sh
```

Requires `curl` + `jq`. Exercises health, dashboard, asset views, `/rag/chat`,
RCA, compliance, evidence-package generate+download, `/evaluation/latest`, and the
`/query` compatibility route.

## Render free-tier limitations

- **Cold starts:** free web services spin down after ~15 min idle; the first
  request then takes ~30–60 s. Warm the API before a live demo (hit `/health`).
- **Ephemeral disk:** see the evidence-package limitation above.
- **Shared CPU:** local→Neon and Render→Neon network latency dominates benchmark
  timing; the ~3.8 s average latency measured locally is network round-trips to
  Neon, **not** the app's compute cost. Judge in-region latency separately.

## DNS / custom-domain troubleshooting

- Apex `assetmind-ai.tech` returning **308** is expected (redirect to the
  canonical host) — not an error.
- Backend must terminate TLS for `api.assetmind-ai.tech`; verify the Render custom
  domain shows **Certificate Issued**.
- If the browser blocks calls with a CORS error, `CORS_ORIGINS` on Render must list
  the **exact** frontend origin (scheme + host, no trailing slash) and the backend
  must have been redeployed after the change.
- DNS: apex `A`/`ALIAS` → Vercel; `api` `CNAME` → the Render `onrender.com` host.

## Deployment status vs. this branch (known gap)

> **The public Render backend is running an older build than this branch.** The
> public smoke test fails at `POST /rag/chat` ("Why is P-101 repeatedly failing?"
> → empty citations), while the **same query against the same Neon DB returns 7
> citations on the current code**. The retrieval-quality hardening (commit
> `d8a9e0d`) and the failure-intelligence endpoints are not yet live. **Action:
> trigger a manual Render redeploy from the latest `main`** (and confirm Vercel is
> on the latest frontend). No code change is required — only a redeploy. Until then
> do not claim the public site reflects the current benchmark or feature set.

## Verified locally

- Backend Docker image builds: `docker build -f apps/api/Dockerfile -t assetmind-api .` ✅
  (all runtime deps present: PyMuPDF/pandas/openpyxl/pgvector; `pytest` absent).
- Frontend production build + typecheck: `cd apps/web && npm run build && npm run lint` ✅
- Full smoke test against the current code (local server + Neon): **14/14 PASS** ✅
- Public smoke test: 7/14 pass then fails at `/rag/chat` — **deployment lag**, see above.
