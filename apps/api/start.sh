#!/usr/bin/env sh
#
# Production start command for the AssetMind AI backend.
# Applies database migrations, then launches the API. Honors $PORT (Render /
# Railway / Fly set this) and defaults to 8000 locally.
#
set -e

echo "Applying database migrations (alembic upgrade head)..."
alembic upgrade head

echo "Starting API on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
