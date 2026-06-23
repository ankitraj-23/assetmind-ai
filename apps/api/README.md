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
