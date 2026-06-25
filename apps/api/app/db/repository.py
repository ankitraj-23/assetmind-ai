"""Database repository layer for the AssetMind AI knowledge store.

This module provides framework-light CRUD helpers over the SQLAlchemy ORM
models defined in :mod:`app.db.models`. It is intentionally decoupled from
FastAPI and from the existing JSON persistence pipeline: nothing here is wired
into ingestion, search, or any route yet, and importing this module never opens
a database connection.

Conventions
-----------
- Every public function accepts an optional ``session``. When omitted, the
  function opens its own transactional :func:`app.db.session.session_scope`,
  commits on success, and rolls back on error. When a caller supplies a
  session, the function participates in that caller's transaction and does not
  commit (the caller owns the transaction boundary).
- Reads return plain ``dict`` objects (or ``None``) with string IDs and
  ISO-8601 datetime strings, so callers never hold detached ORM instances.
- Document and chunk IDs are supplied by the caller to stay compatible with the
  existing ``uuid4().hex`` document IDs and ``"{document_id}-{chunk_index}"``
  chunk IDs. IDs for pages, entities, assets, and mentions are generated here.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EMBEDDING_DIM,
    Asset,
    AssetMention,
    Document,
    DocumentChunk,
    DocumentPage,
    ExtractedEntity,
)
from app.db.session import session_scope

__all__ = [
    "create_document",
    "list_documents",
    "get_document",
    "update_document_counts",
    "create_document_page",
    "create_document_chunk",
    "list_document_chunks",
    "get_all_chunks_with_embeddings",
    "store_chunk_embedding",
    "store_extracted_entity",
    "list_entities_for_document",
    "upsert_asset_from_tag",
    "list_assets",
    "get_asset_by_tag",
    "create_asset_mention",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@contextmanager
def _unit_of_work(session: Session | None) -> Iterator[Session]:
    """Yield a session, owning the transaction only when none was passed in.

    When ``session`` is provided the caller controls commit/rollback, so this
    helper simply yields it untouched. When ``session`` is ``None`` a new
    transactional scope is opened and committed (or rolled back) here.
    """

    if session is not None:
        yield session
        return

    with session_scope() as owned_session:
        yield owned_session


def _new_id() -> str:
    """Return a fresh opaque identifier compatible with the TEXT id columns."""

    return uuid4().hex


def _iso(value: datetime | None) -> str | None:
    """Render a datetime as an ISO-8601 string, passing through ``None``."""

    return value.isoformat() if value is not None else None


def _document_to_dict(row: Document) -> dict[str, Any]:
    """Convert a :class:`Document` ORM row to a plain dict.

    ``filename`` is included as an alias of ``original_filename`` so callers
    that mirror the existing API ``Document`` schema can consume the dict
    directly without remapping.
    """

    return {
        "id": row.id,
        "original_filename": row.original_filename,
        "filename": row.original_filename,
        "stored_filename": row.stored_filename,
        "storage_path": row.storage_path,
        "content_type": row.content_type,
        "source_type": row.source_type,
        "status": row.status,
        "size_bytes": row.size_bytes,
        "text_char_count": row.text_char_count,
        "chunk_count": row.chunk_count,
        "metadata": dict(row.metadata_json or {}),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _page_to_dict(row: DocumentPage) -> dict[str, Any]:
    return {
        "id": row.id,
        "document_id": row.document_id,
        "page_number": row.page_number,
        "text": row.text,
        "metadata": dict(row.metadata_json or {}),
        "created_at": _iso(row.created_at),
    }


def _chunk_to_dict(row: DocumentChunk) -> dict[str, Any]:
    return {
        "id": row.id,
        "document_id": row.document_id,
        "page_id": row.page_id,
        "chunk_index": row.chunk_index,
        "text": row.text,
        "char_start": row.char_start,
        "char_end": row.char_end,
        "token_count": row.token_count,
        "embedding_model": row.embedding_model,
        "has_embedding": row.embedding is not None,
        "metadata": dict(row.metadata_json or {}),
        "created_at": _iso(row.created_at),
    }


def _entity_to_dict(row: ExtractedEntity) -> dict[str, Any]:
    return {
        "id": row.id,
        "entity_type": row.entity_type,
        "raw_value": row.raw_value,
        "normalized_value": row.normalized_value,
        "confidence": row.confidence,
        "document_id": row.document_id,
        "chunk_id": row.chunk_id,
        "page_number": row.page_number,
        "char_start": row.char_start,
        "char_end": row.char_end,
        "extraction_method": row.extraction_method,
        "metadata": dict(row.metadata_json or {}),
        "created_at": _iso(row.created_at),
    }


def _asset_to_dict(row: Asset) -> dict[str, Any]:
    return {
        "id": row.id,
        "tag": row.tag,
        "asset_type": row.asset_type,
        "display_name": row.display_name,
        "metadata": dict(row.metadata_json or {}),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _asset_mention_to_dict(row: AssetMention) -> dict[str, Any]:
    return {
        "id": row.id,
        "asset_id": row.asset_id,
        "entity_id": row.entity_id,
        "document_id": row.document_id,
        "chunk_id": row.chunk_id,
        "page_number": row.page_number,
        "confidence": row.confidence,
        "created_at": _iso(row.created_at),
    }


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def create_document(
    *,
    id: str,
    filename: str | None = None,
    original_filename: str | None = None,
    content_type: str | None = None,
    size_bytes: int | None = None,
    text_char_count: int | None = None,
    status: str = "processed",
    storage_path: str | None = None,
    stored_filename: str | None = None,
    source_type: str | None = None,
    chunk_count: int | None = None,
    metadata: dict[str, Any] | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Insert a document row and return it as a dict.

    Either ``filename`` or ``original_filename`` must be provided (they are
    aliases for the same column). The caller supplies ``id`` to preserve
    existing ``uuid4().hex`` document identifiers.
    """

    resolved_filename = original_filename or filename
    if not resolved_filename:
        raise ValueError("create_document requires 'filename' or 'original_filename'")

    with _unit_of_work(session) as active:
        document = Document(
            id=id,
            original_filename=resolved_filename,
            stored_filename=stored_filename,
            storage_path=storage_path,
            content_type=content_type,
            source_type=source_type if source_type is not None else "upload",
            status=status,
            size_bytes=size_bytes,
            text_char_count=text_char_count,
            chunk_count=chunk_count,
            metadata_json=metadata or {},
        )
        active.add(document)
        active.flush()
        active.refresh(document)
        return _document_to_dict(document)


def list_documents(session: Session | None = None) -> list[dict[str, Any]]:
    """Return all documents, most recently created first."""

    with _unit_of_work(session) as active:
        rows = (
            active.execute(
                select(Document).order_by(
                    Document.created_at.desc(), Document.id.desc()
                )
            )
            .scalars()
            .all()
        )
        return [_document_to_dict(row) for row in rows]


def get_document(
    document_id: str, session: Session | None = None
) -> dict[str, Any] | None:
    """Return one document by id, or ``None`` if it does not exist."""

    with _unit_of_work(session) as active:
        row = active.get(Document, document_id)
        return _document_to_dict(row) if row is not None else None


def update_document_counts(
    document_id: str,
    chunk_count: int | None = None,
    text_char_count: int | None = None,
    status: str | None = None,
    session: Session | None = None,
) -> dict[str, Any] | None:
    """Update mutable document counters/status; only non-None fields change.

    Returns the updated document dict, or ``None`` if the document is absent.
    """

    with _unit_of_work(session) as active:
        row = active.get(Document, document_id)
        if row is None:
            return None
        if chunk_count is not None:
            row.chunk_count = chunk_count
        if text_char_count is not None:
            row.text_char_count = text_char_count
        if status is not None:
            row.status = status
        active.flush()
        active.refresh(row)
        return _document_to_dict(row)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def create_document_page(
    *,
    document_id: str,
    page_number: int,
    text: str,
    id: str | None = None,
    metadata: dict[str, Any] | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Insert a page of text linked to a document and return it as a dict."""

    with _unit_of_work(session) as active:
        page = DocumentPage(
            id=id or _new_id(),
            document_id=document_id,
            page_number=page_number,
            text=text,
            metadata_json=metadata or {},
        )
        active.add(page)
        active.flush()
        active.refresh(page)
        return _page_to_dict(page)


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------


def create_document_chunk(
    *,
    id: str,
    document_id: str,
    chunk_index: int,
    text: str,
    char_start: int | None = None,
    char_end: int | None = None,
    token_count: int | None = None,
    page_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Insert a chunk row and return it as a dict.

    The caller supplies ``id`` to preserve existing
    ``"{document_id}-{chunk_index}"`` chunk identifiers.
    """

    with _unit_of_work(session) as active:
        chunk = DocumentChunk(
            id=id,
            document_id=document_id,
            page_id=page_id,
            chunk_index=chunk_index,
            text=text,
            char_start=char_start,
            char_end=char_end,
            token_count=token_count,
            metadata_json=metadata or {},
        )
        active.add(chunk)
        active.flush()
        active.refresh(chunk)
        return _chunk_to_dict(chunk)


def list_document_chunks(
    document_id: str, session: Session | None = None
) -> list[dict[str, Any]]:
    """Return all chunks of a document, ordered by ``chunk_index``."""

    with _unit_of_work(session) as active:
        rows = (
            active.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index.asc())
            )
            .scalars()
            .all()
        )
        return [_chunk_to_dict(row) for row in rows]


def get_all_chunks_with_embeddings(
    session: Session | None = None,
) -> list[dict[str, Any]]:
    """Return every embedded chunk plus the document metadata search needs.

    Only chunks whose ``embedding`` is populated are returned. The embedding
    vector itself is included (as a list of floats) alongside the citation
    fields (filename, storage path) needed to render search results.
    """

    with _unit_of_work(session) as active:
        rows = active.execute(
            select(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.embedding.isnot(None))
            .order_by(
                DocumentChunk.document_id.asc(), DocumentChunk.chunk_index.asc()
            )
        ).all()

        results: list[dict[str, Any]] = []
        for chunk, document in rows:
            embedding = chunk.embedding
            record = _chunk_to_dict(chunk)
            record["embedding"] = (
                [float(value) for value in embedding]
                if embedding is not None
                else None
            )
            record["document"] = {
                "id": document.id,
                "filename": document.original_filename,
                "original_filename": document.original_filename,
                "storage_path": document.storage_path,
                "content_type": document.content_type,
            }
            results.append(record)
        return results


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


def store_chunk_embedding(
    chunk_id: str,
    vector: list[float],
    embedding_model: str,
    session: Session | None = None,
) -> dict[str, Any]:
    """Store an embedding vector on a chunk after validating its dimension.

    The vector length must equal :data:`app.db.models.EMBEDDING_DIM` (384); a
    mismatch raises :class:`ValueError` rather than being silently accepted.
    """

    vector = list(vector)
    if len(vector) != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding for chunk '{chunk_id}' has dimension {len(vector)}, "
            f"expected {EMBEDDING_DIM}."
        )

    with _unit_of_work(session) as active:
        chunk = active.get(DocumentChunk, chunk_id)
        if chunk is None:
            raise ValueError(f"Chunk '{chunk_id}' does not exist.")
        chunk.embedding = vector
        chunk.embedding_model = embedding_model
        active.flush()
        active.refresh(chunk)
        return _chunk_to_dict(chunk)


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


def store_extracted_entity(
    *,
    entity_type: str,
    raw_value: str,
    normalized_value: str | None = None,
    confidence: float | None = None,
    document_id: str | None = None,
    chunk_id: str | None = None,
    page_number: int | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
    extraction_method: str | None = None,
    id: str | None = None,
    metadata: dict[str, Any] | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Insert one extracted entity and return it as a dict.

    ``normalized_value`` defaults to the uppercased, stripped ``raw_value`` when
    not supplied, matching the asset-tag normalization used elsewhere.
    """

    resolved_normalized = (
        normalized_value if normalized_value is not None else raw_value.strip().upper()
    )

    with _unit_of_work(session) as active:
        entity = ExtractedEntity(
            id=id or _new_id(),
            entity_type=entity_type,
            raw_value=raw_value,
            normalized_value=resolved_normalized,
            confidence=confidence,
            document_id=document_id,
            chunk_id=chunk_id,
            page_number=page_number,
            char_start=char_start,
            char_end=char_end,
            extraction_method=extraction_method,
            metadata_json=metadata or {},
        )
        active.add(entity)
        active.flush()
        active.refresh(entity)
        return _entity_to_dict(entity)


def list_entities_for_document(
    document_id: str, session: Session | None = None
) -> list[dict[str, Any]]:
    """Return all extracted entities linked to a document, oldest first."""

    with _unit_of_work(session) as active:
        rows = (
            active.execute(
                select(ExtractedEntity)
                .where(ExtractedEntity.document_id == document_id)
                .order_by(ExtractedEntity.created_at.asc(), ExtractedEntity.id.asc())
            )
            .scalars()
            .all()
        )
        return [_entity_to_dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


def upsert_asset_from_tag(
    tag: str,
    asset_type: str | None = None,
    display_name: str | None = None,
    metadata: dict[str, Any] | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Return the asset for ``tag``, creating it if it does not yet exist.

    The tag is normalized to uppercase (and stripped) before lookup/insert, so
    ``"p-101"`` and ``"P-101"`` resolve to the same asset. An existing asset is
    returned unchanged; only a genuinely new tag triggers an insert.
    """

    normalized_tag = tag.strip().upper()
    if not normalized_tag:
        raise ValueError("upsert_asset_from_tag requires a non-empty tag.")

    with _unit_of_work(session) as active:
        existing = active.execute(
            select(Asset).where(Asset.tag == normalized_tag)
        ).scalar_one_or_none()
        if existing is not None:
            return _asset_to_dict(existing)

        asset = Asset(
            id=_new_id(),
            tag=normalized_tag,
            asset_type=asset_type,
            display_name=display_name,
            metadata_json=metadata or {},
        )
        active.add(asset)
        active.flush()
        active.refresh(asset)
        return _asset_to_dict(asset)


def list_assets(session: Session | None = None) -> list[dict[str, Any]]:
    """Return all assets ordered by tag."""

    with _unit_of_work(session) as active:
        rows = (
            active.execute(select(Asset).order_by(Asset.tag.asc())).scalars().all()
        )
        return [_asset_to_dict(row) for row in rows]


def get_asset_by_tag(
    tag: str, session: Session | None = None
) -> dict[str, Any] | None:
    """Return one asset by tag (normalized to uppercase), or ``None``."""

    normalized_tag = tag.strip().upper()
    with _unit_of_work(session) as active:
        row = active.execute(
            select(Asset).where(Asset.tag == normalized_tag)
        ).scalar_one_or_none()
        return _asset_to_dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Asset mentions
# ---------------------------------------------------------------------------


def create_asset_mention(
    *,
    asset_id: str,
    entity_id: str | None = None,
    document_id: str | None = None,
    chunk_id: str | None = None,
    page_number: int | None = None,
    confidence: float | None = None,
    id: str | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Link an asset to its supporting entity/document/chunk/page evidence."""

    with _unit_of_work(session) as active:
        mention = AssetMention(
            id=id or _new_id(),
            asset_id=asset_id,
            entity_id=entity_id,
            document_id=document_id,
            chunk_id=chunk_id,
            page_number=page_number,
            confidence=confidence,
        )
        active.add(mention)
        active.flush()
        active.refresh(mention)
        return _asset_mention_to_dict(mention)
