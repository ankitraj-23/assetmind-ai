"""End-to-end verification of deterministic equipment-tag extraction (Stage 5).

Drives the real ingestion pipeline with ``PERSISTENCE_BACKEND=postgres`` and a
live Postgres database, ingesting a small sample note and confirming that the
asset graph landed correctly:

    1. extracted tags for the chunk are exactly P-101, V-101, HX-302,
    2. the repeated P-101 is deduplicated within the same chunk,
    3. the assets table contains P-101, V-101, HX-302 (with inferred types),
    4. asset_mentions link each asset back to the source document/chunk,
    5. existing search still returns a citation-backed result for "P-101 vibration".

It requires ``DATABASE_URL`` and the baseline Alembic migration to be applied.
It is safe to rerun: the document it creates (and its local raw file) are
removed at the end, so repeated runs do not accumulate rows.

Usage
-----
    cd apps/api
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
        .venv/bin/python -m scripts.verify_equipment_extraction
"""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

from starlette.datastructures import Headers, UploadFile

# Force the Postgres backend regardless of any ambient PERSISTENCE_BACKEND.
from app.core.config import settings

settings.persistence_backend = "postgres"

from app.db.session import (  # noqa: E402
    DatabaseNotConfiguredError,
    get_database_url,
)
from app.services import chunking, entity_extraction, ingestion  # noqa: E402
from app.services import search as search_service  # noqa: E402

SAMPLE_FILENAME = "p101-equipment-note.txt"
SAMPLE_TEXT = "Pump P-101 feeds valve V-101 through HX-302. P-101 has repeated vibration."

EXPECTED_TAGS = {"P-101", "V-101", "HX-302"}
EXPECTED_TYPES = {"P-101": "pump", "V-101": "valve", "HX-302": "heat_exchanger"}


def _build_upload() -> UploadFile:
    return UploadFile(
        file=io.BytesIO(SAMPLE_TEXT.encode("utf-8")),
        filename=SAMPLE_FILENAME,
        headers=Headers({"content-type": "text/plain"}),
    )


def _cleanup_document(document_id: str, storage_path: str | None) -> None:
    """Delete the test document (cascades to chunks/entities/mentions) + raw file.

    Assets are deduplicated by tag and shared across documents, so they are left
    in place; only the per-document rows (which cascade) and the local raw file
    are removed.
    """
    from sqlalchemy import delete

    from app.db.models import Document
    from app.db.session import session_scope

    with session_scope() as session:
        session.execute(delete(Document).where(Document.id == document_id))

    if storage_path:
        Path(storage_path).unlink(missing_ok=True)


def main() -> int:
    try:
        get_database_url()
    except DatabaseNotConfiguredError as exc:
        print(f"ERROR: {exc}")
        return 1

    # 0. Pure extractor sanity check (no DB): dedup within a single chunk.
    extracted = entity_extraction.extract_equipment_tags(SAMPLE_TEXT)
    normalized = [t.normalized_value for t in extracted]
    assert set(normalized) == EXPECTED_TAGS, (
        f"extractor returned {set(normalized)}, expected {EXPECTED_TAGS}"
    )
    assert len(normalized) == len(set(normalized)), (
        "repeated P-101 was not deduplicated within the chunk"
    )
    assert normalized.count("P-101") == 1, "P-101 appeared more than once"

    document = asyncio.run(ingestion.ingest_upload(_build_upload()))
    doc_id = document.id

    try:
        from app.db import repository as repo

        # 1 & 2. Entities persisted for the document, deduplicated per chunk.
        entities = repo.list_entities_for_document(doc_id)
        equipment = [e for e in entities if e["entity_type"] == "equipment_tag"]
        assert equipment, "no equipment_tag entities were persisted"
        # The sample fits in a single chunk, so each tag appears exactly once.
        by_chunk: dict[str, list[str]] = {}
        for e in equipment:
            by_chunk.setdefault(e["chunk_id"], []).append(e["normalized_value"])
        for chunk_id, values in by_chunk.items():
            assert len(values) == len(set(values)), (
                f"duplicate tags persisted within chunk {chunk_id}: {values}"
            )
        entity_tags = {e["normalized_value"] for e in equipment}
        assert EXPECTED_TAGS <= entity_tags, (
            f"persisted entities {entity_tags} missing some of {EXPECTED_TAGS}"
        )
        assert all(
            e["extraction_method"] == "regex_equipment_tag_v1" for e in equipment
        ), "unexpected extraction_method on persisted entities"

        # 3. Assets table contains the tags with inferred types.
        for tag, expected_type in EXPECTED_TYPES.items():
            asset = repo.get_asset_by_tag(tag)
            assert asset is not None, f"asset {tag} missing from assets table"
            assert asset["asset_type"] == expected_type, (
                f"asset {tag} has type {asset['asset_type']!r}, "
                f"expected {expected_type!r}"
            )

        # 4. Asset mentions link each asset to the source document/chunk.
        chunk_ids = {c.id for c in chunking.get_chunks(doc_id)}
        for tag in EXPECTED_TAGS:
            asset = repo.get_asset_by_tag(tag)
            mentions = [
                m
                for m in _mentions_for_asset(asset["id"])
                if m["document_id"] == doc_id
            ]
            assert mentions, f"no asset_mentions linking {tag} to document {doc_id}"
            assert all(m["chunk_id"] in chunk_ids for m in mentions), (
                f"asset_mentions for {tag} reference a chunk not in this document"
            )

        # 5. Existing search still returns a citation-backed result.
        results = search_service.search("P-101 vibration", top_k=5)
        assert results, "search returned no results"
        top = results[0]
        assert top.citation is not None, "top result has no citation"
        assert top.citation.document_id == top.document_id
        assert top.citation.chunk_id == top.chunk_id
        assert any(r.document_id == doc_id for r in results), (
            "search results did not include the ingested document"
        )

        # Summary ---------------------------------------------------------
        print("Equipment extraction verification: SUCCESS")
        print(f"  document      : {doc_id} ({document.filename})")
        print(f"  chunks        : {sorted(chunk_ids)}")
        print(f"  entities      : {sorted(entity_tags)} ({len(equipment)} rows)")
        print(
            "  assets        : "
            + ", ".join(
                f"{tag}->{repo.get_asset_by_tag(tag)['asset_type']}"
                for tag in sorted(EXPECTED_TAGS)
            )
        )
        print(
            f"  search top    : score={top.score} chunk={top.chunk_id} "
            f"file={top.filename!r}"
        )
        return 0
    finally:
        _cleanup_document(doc_id, document.storage_path)


def _mentions_for_asset(asset_id: str) -> list[dict]:
    """Read asset_mentions for one asset (no repository helper exists for this)."""
    from sqlalchemy import select

    from app.db.models import AssetMention
    from app.db.session import session_scope

    with session_scope() as session:
        rows = (
            session.execute(
                select(AssetMention).where(AssetMention.asset_id == asset_id)
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": r.id,
                "asset_id": r.asset_id,
                "entity_id": r.entity_id,
                "document_id": r.document_id,
                "chunk_id": r.chunk_id,
                "page_number": r.page_number,
            }
            for r in rows
        ]


if __name__ == "__main__":
    sys.exit(main())
