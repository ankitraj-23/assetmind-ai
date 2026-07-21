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

## Verified locally

- Backend Docker image builds: `docker build -f apps/api/Dockerfile -t assetmind-api .` ✅
- Frontend production build: `cd apps/web && npm run build` ✅
