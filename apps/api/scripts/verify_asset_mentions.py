"""End-to-end verification of asset-centric evidence retrieval (Stage 6).

Drives the real ingestion pipeline with ``PERSISTENCE_BACKEND=postgres`` and a
live Postgres database, then exercises the repository helper behind
``GET /assets/{tag}/mentions`` to confirm that asset evidence is retrievable
with search-compatible citations:

    1. ingesting the sample note creates at least one P-101 mention,
    2. every mention carries document_id, chunk_id, chunk_index, filename, text,
       and a citation object,
    3. the citation shape matches the existing search Citation style
       (document_id, chunk_id, chunk_index, filename),
    4. a lowercase ``p-101`` lookup returns the same mentions as ``P-101``.

It requires ``DATABASE_URL`` and the baseline Alembic migration to be applied.
It is safe to rerun: the document it creates (and its local raw file) are
removed at the end, so repeated runs do not accumulate rows.

Usage
-----
    cd apps/api
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
        .venv/bin/python -m scripts.verify_asset_mentions
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
from app.services import ingestion  # noqa: E402

SAMPLE_FILENAME = "p101-asset-mentions-note.txt"
SAMPLE_TEXT = "Pump P-101 feeds valve V-101 through HX-302. P-101 has repeated vibration."

CITATION_KEYS = {"document_id", "chunk_id", "chunk_index", "filename"}
REQUIRED_FIELDS = ("document_id", "chunk_id", "chunk_index", "filename", "text")


def _build_upload() -> UploadFile:
    return UploadFile(
        file=io.BytesIO(SAMPLE_TEXT.encode("utf-8")),
        filename=SAMPLE_FILENAME,
        headers=Headers({"content-type": "text/plain"}),
    )


def _cleanup_document(document_id: str, storage_path: str | None) -> None:
    """Delete the test document (cascades to chunks/entities/mentions) + raw file."""
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

    document = asyncio.run(ingestion.ingest_upload(_build_upload()))
    doc_id = document.id

    try:
        from app.db import repository as repo

        # 1. The asset has at least one mention for the ingested document.
        mentions = repo.list_asset_mentions_by_tag("P-101")
        doc_mentions = [m for m in mentions if m["document_id"] == doc_id]
        assert doc_mentions, "no P-101 mentions linked to the ingested document"

        # 2 & 3. Each mention has the evidence fields and a search-style citation.
        for m in doc_mentions:
            for field in REQUIRED_FIELDS:
                assert m.get(field) is not None, f"mention missing {field}: {m}"
            assert m["tag"] == "P-101", f"unexpected tag on mention: {m['tag']}"
            citation = m.get("citation")
            assert isinstance(citation, dict), "mention has no citation object"
            assert set(citation) == CITATION_KEYS, (
                f"citation keys {set(citation)} != search style {CITATION_KEYS}"
            )
            assert citation["document_id"] == m["document_id"]
            assert citation["chunk_id"] == m["chunk_id"]
            assert citation["chunk_index"] == m["chunk_index"]
            assert citation["filename"] == m["filename"]

        # 4. Lowercase lookup resolves to the same asset and mentions.
        lower = repo.list_asset_mentions_by_tag("p-101")
        assert [m["id"] for m in lower] == [m["id"] for m in mentions], (
            "lowercase p-101 returned different mentions than uppercase P-101"
        )

        # Summary ---------------------------------------------------------
        top = doc_mentions[0]
        print("Asset mentions verification: SUCCESS")
        print(f"  document      : {doc_id} ({document.filename})")
        print(f"  P-101 mentions: {len(mentions)} (this doc: {len(doc_mentions)})")
        print(
            f"  sample mention: chunk_index={top['chunk_index']} "
            f"chunk={top['chunk_id']} file={top['filename']!r}"
        )
        print(f"  citation      : {top['citation']}")
        print(f"  text          : {top['text']!r}")
        print("  case-insensitive p-101 == P-101: OK")
        return 0
    finally:
        _cleanup_document(doc_id, document.storage_path)


if __name__ == "__main__":
    sys.exit(main())
