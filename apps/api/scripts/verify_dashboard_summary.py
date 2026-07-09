"""Read-only inspection of the dashboard summary v2 (Postgres mode).

Prints the live dashboard counts, the derived risk breakdown (high/medium/low
plus estimated compliance gaps and repeated-failure patterns), the top assets by
mention count, and the top risky assets from the risk summary. It mutates no data
and calls no external APIs.

It requires ``DATABASE_URL`` and the baseline Alembic migration to be applied.

Usage
-----
    cd apps/api
    PERSISTENCE_BACKEND=postgres \
        DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
        python -m scripts.verify_dashboard_summary
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

    summary = repo.get_dashboard_summary()

    # Core counts ----------------------------------------------------------
    print("Dashboard summary counts:")
    for key in (
        "documents_indexed",
        "chunks_created",
        "assets_discovered",
        "entities_extracted",
        "asset_mentions",
        "knowledge_edges",
    ):
        print(f"  {key:26s}: {summary.get(key)}")

    # Risk counts ----------------------------------------------------------
    print("\nRisk counts:")
    for key in (
        "high_risk_assets",
        "medium_risk_assets",
        "low_risk_assets",
        "open_compliance_gaps",
        "repeated_failure_patterns",
    ):
        print(f"  {key:26s}: {summary.get(key)}")

    # Top assets by mentions ----------------------------------------------
    print("\nTop assets by mentions:")
    for item in summary.get("top_assets_by_mentions", [])[:5]:
        print(f"  - {_compact(item, ('asset_tag', 'asset_type', 'mention_count'))}")

    # Top risk summary assets ---------------------------------------------
    print("\nTop risk summary assets:")
    for item in summary.get("risk_summary", [])[:5]:
        print(f"  - {_compact(item, ('asset_tag', 'risk_score', 'risk_level'))}")
        for reason in item.get("risk_reasons", []):
            print(f"      · {reason}")

    print("\nDashboard summary v2 inspection: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
