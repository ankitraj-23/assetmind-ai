"""Seed the database with standard assets and ingest documents for the AssetMind AI Demo Plant.

Usage:
------
    PERSISTENCE_BACKEND=postgres \
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
    .venv/bin/python -m scripts.seed_demo_plant
"""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path
from fastapi import UploadFile

from app.core import config
from app.db.session import get_database_url, session_scope

# Force Postgres
config.settings.persistence_backend = "postgres"

async def main_async() -> int:
    try:
        get_database_url()
    except Exception as exc:
        print(f"Database error: {exc}")
        return 1

    from app.db import repository as repo
    from app.services.ingestion import ingest_upload

    # 1. Seed assets
    assets_to_seed = [
        {"tag": "P-101", "asset_type": "pump", "display_name": "Centrifugal Pump P-101"},
        {"tag": "P-102", "asset_type": "pump", "display_name": "Centrifugal Pump P-102"},
        {"tag": "V-101", "asset_type": "vessel", "display_name": "Separation Vessel V-101"},
        {"tag": "HX-302", "asset_type": "heat_exchanger", "display_name": "Shell & Tube Exchanger HX-302"},
        {"tag": "C-220", "asset_type": "compressor", "display_name": "Reciprocating Compressor C-220"},
        {"tag": "TK-482", "asset_type": "vessel", "display_name": "Chemical Storage Tank TK-482"},
        {"tag": "BLR-118", "asset_type": "boiler", "display_name": "Package Steam Boiler BLR-118"},
    ]

    print("Seeding demo assets into Postgres...")
    with session_scope() as session:
        for a in assets_to_seed:
            asset = repo.upsert_asset_from_tag(
                tag=a["tag"],
                asset_type=a["asset_type"],
                display_name=a["display_name"],
                session=session,
            )
            print(f"  Upserted asset: {asset['tag']} (type: {asset['asset_type']})")

    # 2. Ingest document files from data/documents/
    root = Path(__file__).resolve().parents[3]
    docs_dir = root / "data" / "documents"

    if not docs_dir.exists():
        print(f"Documents directory not found at {docs_dir}")
        return 1

    files_to_ingest = list(docs_dir.glob("*"))
    print(f"\nFound {len(files_to_ingest)} document(s) in {docs_dir}. Starting ingestion...")

    # Load existing docs from database to avoid double-ingesting
    with session_scope() as session:
        existing_filenames = {
            doc["original_filename"] for doc in repo.list_documents(session=session)
        }

    for filepath in files_to_ingest:
        if filepath.is_dir() or filepath.name.startswith("."):
            continue

        filename = filepath.name
        if filename in existing_filenames:
            print(f"  Skipping: '{filename}' (already ingested)")
            continue

        print(f"  Ingesting: '{filename}'...")
        try:
            raw_bytes = filepath.read_bytes()
            upload = UploadFile(
                filename=filename,
                file=io.BytesIO(raw_bytes),
                headers=None
            )
            document = await ingest_upload(upload)
            print(f"    SUCCESS: Created document ID: {document.id} with {document.chunk_count} chunks.")
        except Exception as err:
            print(f"    FAILED: Could not ingest '{filename}'. Error: {err}")

    # 3. Backfill knowledge graph edges
    print("\nStarting knowledge graph backfill step...")
    from scripts import backfill_knowledge_edges
    backfill_knowledge_edges.main()

    print("\nSeeding & Ingestion complete.")
    return 0

def main() -> int:
    return asyncio.run(main_async())

if __name__ == "__main__":
    sys.exit(main())
