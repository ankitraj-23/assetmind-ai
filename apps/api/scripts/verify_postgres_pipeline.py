"""End-to-end verification of the Postgres persistence backend.

This script drives the real ingestion / chunking / embedding / search services
with ``PERSISTENCE_BACKEND=postgres`` and a live Postgres database. It ingests a
small sample text file and confirms the full pipeline landed in Postgres:

    1. the document row exists,
    2. chunk rows exist,
    3. embeddings exist and are 384-dimensional,
    4. listing documents works,
    5. chunk retrieval works,
    6. search returns a citation-backed result for "P-101 vibration".

It requires ``DATABASE_URL`` and the baseline Alembic migration to be applied.
It is safe to rerun: the document it creates (and its local raw file) are
removed at the end, so repeated runs do not accumulate rows.

Usage
-----
    cd apps/api
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
        .venv/bin/python -m scripts.verify_postgres_pipeline
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

from app.db.models import EMBEDDING_DIM  # noqa: E402
from app.db.session import (  # noqa: E402
    DatabaseNotConfiguredError,
    get_database_url,
)
from app.services import chunking, embeddings, ingestion  # noqa: E402
from app.services import search as search_service  # noqa: E402

SAMPLE_FILENAME = "p101-vibration-note.txt"
SAMPLE_TEXT = (
    "Maintenance note for centrifugal pump P-101.\n"
    "On the last inspection, P-101 vibration exceeded the alarm threshold of "
    "7.1 mm/s at the drive-end bearing. Elevated P-101 vibration was attributed "
    "to a suspected misalignment between the motor and the pump shaft.\n"
    "Recommended action: perform laser shaft alignment on P-101 and recheck "
    "vibration after restart. Continue monitoring P-101 vibration trend.\n"
)


def _build_upload() -> UploadFile:
    return UploadFile(
        file=io.BytesIO(SAMPLE_TEXT.encode("utf-8")),
        filename=SAMPLE_FILENAME,
        headers=Headers({"content-type": "text/plain"}),
    )


def _cleanup_document(document_id: str, storage_path: str | None) -> None:
    """Delete the test document (cascades to chunks) and its local raw file."""
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
        # 1. Document row exists (via repository read path).
        documents = ingestion.list_documents()
        listed = next((d for d in documents if d.id == doc_id), None)
        assert listed is not None, "ingested document not returned by list_documents"
        assert listed.filename == SAMPLE_FILENAME
        assert listed.storage_path and Path(listed.storage_path).exists(), (
            "raw uploaded file was not kept in local storage"
        )

        # 2. Chunk rows exist.
        chunks = chunking.get_chunks(doc_id)
        assert chunks, "no chunks were stored for the document"
        assert all(c.id == f"{doc_id}-{c.chunk_index}" for c in chunks), (
            "chunk ids do not follow the '{document_id}-{chunk_index}' format"
        )

        # 3. Embeddings exist and are 384-dimensional.
        stored_embeddings = embeddings.get_embeddings(doc_id)
        assert len(stored_embeddings) == len(chunks), (
            "embedding count does not match chunk count"
        )
        assert all(len(e.vector) == EMBEDDING_DIM for e in stored_embeddings), (
            f"stored embeddings are not all {EMBEDDING_DIM}-dimensional"
        )

        # 4 & 5 already covered (list documents + chunk retrieval).

        # 6. Search returns a citation-backed result for "P-101 vibration".
        results = search_service.search("P-101 vibration", top_k=5)
        assert results, "search returned no results"
        top = results[0]
        assert top.citation is not None, "top result has no citation"
        assert top.citation.document_id == top.document_id
        assert top.citation.chunk_id == top.chunk_id
        from_our_doc = any(r.document_id == doc_id for r in results)
        assert from_our_doc, "search results did not include the ingested document"

        # Summary ---------------------------------------------------------
        print("Postgres pipeline verification: SUCCESS")
        print(f"  document     : {doc_id} ({listed.filename})")
        print(f"  storage_path : {listed.storage_path}")
        print(f"  chunks       : {len(chunks)} -> {[c.id for c in chunks]}")
        print(
            f"  embeddings   : {len(stored_embeddings)} chunks, "
            f"dim={EMBEDDING_DIM} each"
        )
        print(
            f"  search top   : score={top.score} chunk={top.chunk_id} "
            f"file={top.filename!r}"
        )
        print(f"  citation     : {top.citation.model_dump()}")
        return 0
    finally:
        _cleanup_document(doc_id, document.storage_path)


if __name__ == "__main__":
    sys.exit(main())
