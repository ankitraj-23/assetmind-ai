"""Dashboard routes — live counts over the ingested knowledge base.

Live summary counts (documents, chunks, assets, entities, mentions, knowledge
edges) only exist when ``PERSISTENCE_BACKEND=postgres``. In JSON mode nothing is
persisted, so this endpoint returns a safe, empty response and never touches a
database.
"""

from typing import Any

from fastapi import APIRouter

from app.core import config

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary() -> dict[str, Any]:
    """Return live dashboard counts (empty, DB-free response in JSON mode)."""
    if not config.use_postgres():
        return {
            "documents_indexed": 0,
            "chunks_created": 0,
            "assets_discovered": 0,
            "entities_extracted": 0,
            "asset_mentions": 0,
            "knowledge_edges": 0,
            "recent_documents": [],
            "high_risk_assets": 0,
            "medium_risk_assets": 0,
            "low_risk_assets": 0,
            "open_compliance_gaps": 0,
            "repeated_failure_patterns": 0,
            "top_assets_by_mentions": [],
            "risk_summary": [],
            "mode": "json",
            "message": "Live dashboard summary is available in Postgres mode.",
        }
    # Imported lazily so JSON mode never touches the database layer.
    from app.db import repository as repo

    summary = repo.get_dashboard_summary()
    summary["mode"] = "postgres"
    return summary


@router.get("/failure-hotspots")
def get_failure_hotspots(limit: int = 10) -> dict[str, Any]:
    """Return assets ranked by documented failure-event count (evidence-backed).

    Only assets with at least one failure-bearing mention are listed, each with
    its failure count, top/repeated failure modes, document count, most recent
    failure date, and supporting citations. In JSON mode nothing is persisted, so
    this returns a safe, empty, DB-free response.
    """
    if not config.use_postgres():
        return {
            "count": 0,
            "total_assets_with_failures": 0,
            "hotspots": [],
            "mode": "json",
            "message": "Failure hotspots are available in Postgres mode.",
        }
    # Imported lazily so JSON mode never touches the database layer.
    from app.db import repository as repo

    result = repo.get_failure_hotspots(limit=limit)
    result["mode"] = "postgres"
    return result
