"""Read-only inspection of the Week 2 asset knowledge graph (Postgres mode).

Exercises the repository helpers behind the new asset intelligence endpoints
against a live Postgres database without mutating any data or calling external
APIs. It prints the dashboard summary, the first few assets, and an inspection
of the ``P-101`` sample asset (related documents, timeline events, and graph
node/edge counts plus a compact sample of nodes/edges).

It requires ``DATABASE_URL`` and the baseline Alembic migration to be applied.

Usage
-----
    cd apps/api
    PERSISTENCE_BACKEND=postgres \
        DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
        python -m scripts.verify_knowledge_graph
"""

from __future__ import annotations

import sys
from typing import Any

# Force the Postgres backend regardless of any ambient PERSISTENCE_BACKEND.
from app.core.config import settings

settings.persistence_backend = "postgres"

from app.db.session import (  # noqa: E402
    DatabaseNotConfiguredError,
    get_database_url,
)

SAMPLE_TAG = "P-101"


def _compact(item: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    """Project a dict down to a few keys for compact, readable printing."""
    return {key: item.get(key) for key in keys}


def main() -> int:
    try:
        get_database_url()
    except DatabaseNotConfiguredError as exc:
        print(f"ERROR: {exc}")
        print("Set DATABASE_URL and PERSISTENCE_BACKEND=postgres before running.")
        return 1

    from app.db import repository as repo

    # Dashboard summary ----------------------------------------------------
    summary = repo.get_dashboard_summary()
    print("Dashboard summary:")
    for key in (
        "documents_indexed",
        "chunks_created",
        "assets_discovered",
        "entities_extracted",
        "asset_mentions",
        "knowledge_edges",
    ):
        print(f"  {key:20s}: {summary.get(key)}")

    # First 10 assets ------------------------------------------------------
    assets = repo.list_assets()
    print(f"\nAssets discovered: {len(assets)} (showing first 10)")
    for asset in assets[:10]:
        print(f"  - {_compact(asset, ('tag', 'asset_type', 'display_name'))}")

    # Inspect the sample tag ----------------------------------------------
    print(f"\nInspecting tag {SAMPLE_TAG!r}:")
    facts = repo.get_asset_facts_by_tag(SAMPLE_TAG)
    if facts is None:
        print(f"  {SAMPLE_TAG} not found.")
        print(
            "  Upload/ingest the sample docs first "
            "(run the ingestion pipeline against Postgres), then rerun."
        )
        return 0

    documents = repo.list_asset_documents_by_tag(SAMPLE_TAG)
    events = repo.list_asset_timeline_by_tag(SAMPLE_TAG)
    graph = repo.get_asset_graph_by_tag(SAMPLE_TAG) or {}
    counts = graph.get("counts", {})

    print(f"  mention_count   : {facts.get('mention_count')}")
    print(f"  related documents: {len(documents)}")
    print(f"  timeline events : {len(events)}")
    print(
        f"  graph nodes/edges: {counts.get('nodes', 0)}/{counts.get('edges', 0)}"
    )

    print("  sample nodes:")
    for node in graph.get("nodes", [])[:5]:
        print(f"    - {_compact(node, ('id', 'type', 'label'))}")
    print("  sample edges:")
    for edge in graph.get("edges", [])[:5]:
        print(f"    - {_compact(edge, ('source', 'relation_type', 'target'))}")

    print(f"\n{SAMPLE_TAG} knowledge graph inspection: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
