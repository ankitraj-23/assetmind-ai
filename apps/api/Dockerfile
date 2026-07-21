# AssetMind AI backend image.
#
# Build from the REPOSITORY ROOT so the demo data directory is in context:
#     docker build -f apps/api/Dockerfile -t assetmind-api .
#
# The repo layout (apps/api + data) is preserved inside the image so the
# in-repo relative paths used by the seed, benchmark and evaluation endpoint
# resolve exactly as they do in development.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PERSISTENCE_BACKEND=postgres \
    STORAGE_DIR=/app/apps/api/storage

WORKDIR /app

# Runtime dependencies first, for layer caching.
COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt

# Application code and the (synthetic) demo corpus + benchmark results.
COPY apps/api ./apps/api
COPY data ./data

WORKDIR /app/apps/api
RUN chmod +x start.sh && mkdir -p storage/exports

EXPOSE 8000

# Container-level liveness probe (no curl in slim image — use urllib).
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import os,sys,urllib.request; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health', timeout=4).status==200 else 1)"

# Migrate, then serve. DATABASE_URL must be provided at runtime.
CMD ["./start.sh"]
