"""Manual verification of the database repository layer.

This script exercises every repository write/read path against a real
Postgres database. It requires ``DATABASE_URL`` to be set and the baseline
Alembic migration to have been applied.

It is safe to rerun: it deletes its own test rows (by deterministic ids /
tag) before inserting, so repeated runs do not accumulate fixtures or fail on
unique constraints.

Usage
-----
    cd apps/api
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
        .venv/bin/python -m scripts.verify_db_repository
"""

from __future__ import annotations

import sys

from sqlalchemy import delete, select

from app.db import repository as repo
from app.db.models import EMBEDDING_DIM, Asset, AssetMention, Document
from app.db.session import (
    DatabaseNotConfiguredError,
    get_database_url,
    session_scope,
)

DOC_ID = "repo-test-doc-001"
CHUNK_IDS = [f"{DOC_ID}-0", f"{DOC_ID}-1"]
ASSET_TAG = "P-101"


def _cleanup() -> None:
    """Remove any rows left by a previous run of this script.

    Cascades from the document delete remove its chunks, entities, and
    mentions; the asset (which has no document FK) is deleted explicitly.
    """

    with session_scope() as session:
        # Drop mentions referencing our asset first in case the asset row is
        # orphaned from a half-completed earlier run.
        asset_id = session.execute(
            select(Asset.id).where(Asset.tag == ASSET_TAG)
        ).scalar_one_or_none()
        if asset_id is not None:
            session.execute(
                delete(AssetMention).where(AssetMention.asset_id == asset_id)
            )
            session.execute(delete(Asset).where(Asset.id == asset_id))
        session.execute(delete(Document).where(Document.id == DOC_ID))


def main() -> int:
    try:
        get_database_url()
    except DatabaseNotConfiguredError as exc:
        print(f"ERROR: {exc}")
        return 1

    _cleanup()

    # 1. Document --------------------------------------------------------
    document = repo.create_document(
        id=DOC_ID,
        original_filename="repo-test.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        text_char_count=120,
        status="processed",
        storage_path=f"storage/{DOC_ID}.pdf",
        chunk_count=2,
        metadata={"source": "verify_db_repository"},
    )
    assert document["id"] == DOC_ID
    assert document["filename"] == "repo-test.pdf"

    # 2. Chunks ----------------------------------------------------------
    for index, chunk_id in enumerate(CHUNK_IDS):
        repo.create_document_chunk(
            id=chunk_id,
            document_id=DOC_ID,
            chunk_index=index,
            text=f"Pump P-101 reading sample chunk {index}.",
            char_start=index * 60,
            char_end=index * 60 + 40,
            token_count=8,
        )

    # 3. Embeddings (384-dim) -------------------------------------------
    for position, chunk_id in enumerate(CHUNK_IDS):
        vector = [float(position)] * EMBEDDING_DIM
        repo.store_chunk_embedding(
            chunk_id=chunk_id,
            vector=vector,
            embedding_model="local-hashing-v1",
        )

    # Negative check: a wrong-dimension vector must be rejected.
    try:
        repo.store_chunk_embedding(
            chunk_id=CHUNK_IDS[0],
            vector=[0.0] * (EMBEDDING_DIM - 1),
            embedding_model="local-hashing-v1",
        )
    except ValueError:
        wrong_dim_rejected = True
    else:
        wrong_dim_rejected = False

    # 4. Entity ----------------------------------------------------------
    entity = repo.store_extracted_entity(
        entity_type="equipment_tag",
        raw_value="P-101",
        document_id=DOC_ID,
        chunk_id=CHUNK_IDS[0],
        page_number=1,
        extraction_method="manual-verify",
        confidence=0.99,
    )

    # 5. Asset (upsert) --------------------------------------------------
    asset = repo.upsert_asset_from_tag(
        ASSET_TAG, asset_type="pump", display_name="Feed Pump 101"
    )
    # Re-upsert must return the same row (idempotent).
    asset_again = repo.upsert_asset_from_tag("p-101")
    assert asset_again["id"] == asset["id"]

    # 6. Asset mention ---------------------------------------------------
    mention = repo.create_asset_mention(
        asset_id=asset["id"],
        entity_id=entity["id"],
        document_id=DOC_ID,
        chunk_id=CHUNK_IDS[0],
        page_number=1,
        confidence=0.99,
    )

    # 7. Read everything back -------------------------------------------
    read_document = repo.get_document(DOC_ID)
    read_chunks = repo.list_document_chunks(DOC_ID)
    embedded_chunks = [
        c for c in repo.get_all_chunks_with_embeddings() if c["document_id"] == DOC_ID
    ]
    read_entities = repo.list_entities_for_document(DOC_ID)
    read_asset = repo.get_asset_by_tag(ASSET_TAG)

    # Assertions ---------------------------------------------------------
    assert read_document is not None
    assert len(read_chunks) == 2
    assert [c["id"] for c in read_chunks] == CHUNK_IDS
    assert len(embedded_chunks) == 2
    assert all(len(c["embedding"]) == EMBEDDING_DIM for c in embedded_chunks)
    assert all(c["document"]["filename"] == "repo-test.pdf" for c in embedded_chunks)
    assert len(read_entities) == 1
    assert read_entities[0]["normalized_value"] == "P-101"
    assert read_asset is not None
    assert read_asset["asset_type"] == "pump"
    assert wrong_dim_rejected, "wrong-dimension embedding was not rejected"

    # Summary ------------------------------------------------------------
    print("Database repository verification: SUCCESS")
    print(f"  document        : {read_document['id']} ({read_document['filename']})")
    print(f"  chunks          : {len(read_chunks)} -> {[c['id'] for c in read_chunks]}")
    print(
        f"  embeddings      : {len(embedded_chunks)} chunks, "
        f"dim={EMBEDDING_DIM} each"
    )
    print(
        f"  wrong-dim guard : rejected {EMBEDDING_DIM - 1}-dim vector "
        f"({'ok' if wrong_dim_rejected else 'FAILED'})"
    )
    print(
        f"  entity          : {read_entities[0]['normalized_value']} "
        f"({read_entities[0]['entity_type']})"
    )
    print(
        f"  asset           : {read_asset['tag']} "
        f"({read_asset['asset_type']}) id={read_asset['id']}"
    )
    print(f"  asset mention   : {mention['id']} -> asset {mention['asset_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
