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

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    EMBEDDING_DIM,
    Asset,
    AssetMention,
    Document,
    DocumentChunk,
    DocumentPage,
    ExtractedEntity,
    KnowledgeEdge,
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
    "list_chunk_embeddings_for_document",
    "get_all_chunks_with_embeddings",
    "store_chunk_embedding",
    "store_extracted_entity",
    "list_entities_for_document",
    "upsert_asset_from_tag",
    "list_assets",
    "get_asset_by_tag",
    "create_asset_mention",
    "list_asset_mentions_by_tag",
    "upsert_knowledge_edge",
    "list_edges_for_asset",
    "list_asset_documents_by_tag",
    "get_asset_facts_by_tag",
    "list_asset_timeline_by_tag",
    "get_asset_graph_by_tag",
    "get_dashboard_summary",
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


def _text_preview(text: str | None, limit: int = 200) -> str | None:
    """Return a single-line, length-capped preview of ``text`` (or ``None``)."""

    if text is None:
        return None
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "…"


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


def _knowledge_edge_to_dict(row: KnowledgeEdge) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "relation_type": row.relation_type,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "evidence_chunk_id": row.evidence_chunk_id,
        "confidence": row.confidence,
        "metadata": dict(row.metadata_json or {}),
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


def list_chunk_embeddings_for_document(
    document_id: str, session: Session | None = None
) -> list[dict[str, Any]]:
    """Return the embedded chunks of one document, ordered by ``chunk_index``.

    Only chunks whose ``embedding`` is populated are returned. Each dict carries
    the embedding vector (as a list of floats) plus the identifiers needed to
    rebuild the existing :class:`ChunkEmbedding` API shape.
    """

    with _unit_of_work(session) as active:
        rows = (
            active.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .where(DocumentChunk.embedding.isnot(None))
                .order_by(DocumentChunk.chunk_index.asc())
            )
            .scalars()
            .all()
        )
        results: list[dict[str, Any]] = []
        for chunk in rows:
            embedding = chunk.embedding
            results.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "embedding_model": chunk.embedding_model,
                    "embedding": (
                        [float(value) for value in embedding]
                        if embedding is not None
                        else None
                    ),
                }
            )
        return results


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
# Knowledge edges
# ---------------------------------------------------------------------------


def upsert_knowledge_edge(
    *,
    source_type: str,
    source_id: str,
    relation_type: str,
    target_type: str,
    target_id: str,
    evidence_chunk_id: str | None = None,
    confidence: float | None = None,
    metadata: dict[str, Any] | None = None,
    id: str | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Create a :class:`KnowledgeEdge` only if an equivalent one is absent.

    Uniqueness is determined by the tuple ``(source_type, source_id,
    relation_type, target_type, target_id, evidence_chunk_id)``. When a matching
    edge already exists it is returned unchanged; otherwise a new edge is
    inserted. The return value is always a plain dict.
    """

    with _unit_of_work(session) as active:
        if evidence_chunk_id is None:
            evidence_predicate = KnowledgeEdge.evidence_chunk_id.is_(None)
        else:
            evidence_predicate = KnowledgeEdge.evidence_chunk_id == evidence_chunk_id

        existing = active.execute(
            select(KnowledgeEdge)
            .where(KnowledgeEdge.source_type == source_type)
            .where(KnowledgeEdge.source_id == source_id)
            .where(KnowledgeEdge.relation_type == relation_type)
            .where(KnowledgeEdge.target_type == target_type)
            .where(KnowledgeEdge.target_id == target_id)
            .where(evidence_predicate)
        ).scalar_one_or_none()
        if existing is not None:
            return _knowledge_edge_to_dict(existing)

        edge = KnowledgeEdge(
            id=id or _new_id(),
            source_type=source_type,
            source_id=source_id,
            relation_type=relation_type,
            target_type=target_type,
            target_id=target_id,
            evidence_chunk_id=evidence_chunk_id,
            confidence=confidence,
            metadata_json=metadata or {},
        )
        active.add(edge)
        active.flush()
        active.refresh(edge)
        return _knowledge_edge_to_dict(edge)


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
    """Link an asset to its supporting entity/document/chunk/page evidence.

    Besides the ``asset_mentions`` row, this also materialises idempotent
    ``knowledge_edges`` rows so the derived asset graph stays in sync as
    mentions are ingested:

    * ``asset -> document`` (``mentioned_in``) when ``document_id`` is set,
    * ``asset -> chunk`` (``supported_by_chunk``) when ``chunk_id`` is set,
    * ``asset -> entity`` (``has_entity``) when ``entity_id`` is set.

    All edge writes share the same active session/transaction as the mention,
    and :func:`upsert_knowledge_edge` guarantees no duplicate edges.
    """

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

        if document_id is not None:
            upsert_knowledge_edge(
                session=active,
                source_type="asset",
                source_id=asset_id,
                relation_type="mentioned_in",
                target_type="document",
                target_id=document_id,
                evidence_chunk_id=chunk_id,
                confidence=confidence,
            )
        if chunk_id is not None:
            upsert_knowledge_edge(
                session=active,
                source_type="asset",
                source_id=asset_id,
                relation_type="supported_by_chunk",
                target_type="chunk",
                target_id=chunk_id,
                evidence_chunk_id=chunk_id,
                confidence=confidence,
            )
        if entity_id is not None:
            upsert_knowledge_edge(
                session=active,
                source_type="asset",
                source_id=asset_id,
                relation_type="has_entity",
                target_type="entity",
                target_id=entity_id,
                evidence_chunk_id=chunk_id,
                confidence=confidence,
            )

        return _asset_mention_to_dict(mention)


def list_asset_mentions_by_tag(
    tag: str, session: Session | None = None
) -> list[dict[str, Any]]:
    """Return evidence-rich mentions of an asset, newest source document first.

    The tag is normalized case-insensitively (matching
    :func:`get_asset_by_tag`). When the asset is unknown or has no mentions an
    empty list is returned. Each mention joins the asset, its supporting entity,
    and the source document/chunk, and carries a ``citation`` object whose shape
    matches the existing search :class:`app.models.search.Citation` style so the
    backend can render asset evidence with the same citation rendering as search.

    Results are ordered by source document ``created_at`` descending, then by
    chunk ``chunk_index`` ascending, then by mention ``created_at`` descending,
    so the most recently ingested evidence appears first.
    """

    normalized_tag = tag.strip().upper()
    if not normalized_tag:
        return []

    with _unit_of_work(session) as active:
        asset = active.execute(
            select(Asset).where(Asset.tag == normalized_tag)
        ).scalar_one_or_none()
        if asset is None:
            return []

        rows = active.execute(
            select(AssetMention, ExtractedEntity, Document, DocumentChunk)
            .outerjoin(
                ExtractedEntity, AssetMention.entity_id == ExtractedEntity.id
            )
            .outerjoin(Document, AssetMention.document_id == Document.id)
            .outerjoin(DocumentChunk, AssetMention.chunk_id == DocumentChunk.id)
            .where(AssetMention.asset_id == asset.id)
            .order_by(
                Document.created_at.desc().nullslast(),
                DocumentChunk.chunk_index.asc().nullslast(),
                AssetMention.created_at.desc(),
            )
        ).all()

        mentions: list[dict[str, Any]] = []
        for mention, entity, document, chunk in rows:
            page_number = mention.page_number
            if page_number is None and entity is not None:
                page_number = entity.page_number
            mentions.append(
                {
                    "id": mention.id,
                    "asset_id": asset.id,
                    "tag": asset.tag,
                    "asset_type": asset.asset_type,
                    "entity_id": mention.entity_id,
                    "raw_value": entity.raw_value if entity is not None else None,
                    "normalized_value": (
                        entity.normalized_value if entity is not None else None
                    ),
                    "document_id": mention.document_id,
                    "filename": (
                        document.original_filename if document is not None else None
                    ),
                    "chunk_id": mention.chunk_id,
                    "chunk_index": chunk.chunk_index if chunk is not None else None,
                    "text": chunk.text if chunk is not None else None,
                    "page_number": page_number,
                    "confidence": mention.confidence,
                    "citation": {
                        "document_id": mention.document_id,
                        "chunk_id": mention.chunk_id,
                        "chunk_index": chunk.chunk_index if chunk is not None else None,
                        "filename": (
                            document.original_filename
                            if document is not None
                            else None
                        ),
                    },
                    "created_at": _iso(mention.created_at),
                }
            )
        return mentions


def list_edges_for_asset(
    asset_id: str, session: Session | None = None
) -> list[dict[str, Any]]:
    """Return knowledge edges where ``asset_id`` is the source or the target.

    The match is on the raw ``asset_id`` (the asset row id, not the tag); edges
    are returned newest first. An empty list is returned when there are none.
    """

    with _unit_of_work(session) as active:
        rows = (
            active.execute(
                select(KnowledgeEdge)
                .where(
                    or_(
                        KnowledgeEdge.source_id == asset_id,
                        KnowledgeEdge.target_id == asset_id,
                    )
                )
                .order_by(KnowledgeEdge.created_at.desc(), KnowledgeEdge.id.desc())
            )
            .scalars()
            .all()
        )
        return [_knowledge_edge_to_dict(row) for row in rows]


def list_asset_documents_by_tag(
    tag: str, session: Session | None = None
) -> list[dict[str, Any]]:
    """Return the unique documents that mention the asset, newest first.

    The tag is normalized case-insensitively. When the asset is unknown or has
    no document-backed mentions an empty list is returned.
    """

    normalized_tag = tag.strip().upper()
    if not normalized_tag:
        return []

    with _unit_of_work(session) as active:
        asset = active.execute(
            select(Asset).where(Asset.tag == normalized_tag)
        ).scalar_one_or_none()
        if asset is None:
            return []

        rows = (
            active.execute(
                select(Document)
                .join(AssetMention, AssetMention.document_id == Document.id)
                .where(AssetMention.asset_id == asset.id)
                .distinct()
                .order_by(Document.created_at.desc(), Document.id.desc())
            )
            .scalars()
            .all()
        )
        return [_document_to_dict(row) for row in rows]


def get_asset_facts_by_tag(
    tag: str, session: Session | None = None
) -> dict[str, Any] | None:
    """Return a compact fact sheet for an asset, or ``None`` when unknown.

    The returned dict contains the asset, a mention count, a distinct document
    count, the list of supporting documents, and the distinct entities linked to
    the asset through its mentions.
    """

    normalized_tag = tag.strip().upper()
    if not normalized_tag:
        return None

    with _unit_of_work(session) as active:
        asset = active.execute(
            select(Asset).where(Asset.tag == normalized_tag)
        ).scalar_one_or_none()
        if asset is None:
            return None

        mention_count = (
            active.execute(
                select(func.count())
                .select_from(AssetMention)
                .where(AssetMention.asset_id == asset.id)
            ).scalar_one()
            or 0
        )

        documents = list_asset_documents_by_tag(normalized_tag, session=active)

        entity_rows = (
            active.execute(
                select(ExtractedEntity)
                .join(AssetMention, AssetMention.entity_id == ExtractedEntity.id)
                .where(AssetMention.asset_id == asset.id)
                .distinct()
                .order_by(ExtractedEntity.created_at.asc(), ExtractedEntity.id.asc())
            )
            .scalars()
            .all()
        )

        return {
            "asset": _asset_to_dict(asset),
            "mention_count": int(mention_count),
            "document_count": len(documents),
            "documents": documents,
            "entities": [_entity_to_dict(row) for row in entity_rows],
        }


def list_asset_timeline_by_tag(
    tag: str, session: Session | None = None
) -> list[dict[str, Any]]:
    """Derive simple timeline events for an asset from its mentions.

    Each mention with a backing document becomes a ``mention`` event, ordered by
    document ``created_at`` descending (newest first). The tag is normalized
    case-insensitively; an unknown asset yields an empty list.
    """

    normalized_tag = tag.strip().upper()
    if not normalized_tag:
        return []

    with _unit_of_work(session) as active:
        asset = active.execute(
            select(Asset).where(Asset.tag == normalized_tag)
        ).scalar_one_or_none()
        if asset is None:
            return []

        rows = active.execute(
            select(AssetMention, Document, DocumentChunk)
            .outerjoin(Document, AssetMention.document_id == Document.id)
            .outerjoin(DocumentChunk, AssetMention.chunk_id == DocumentChunk.id)
            .where(AssetMention.asset_id == asset.id)
            .order_by(
                Document.created_at.desc().nullslast(),
                DocumentChunk.chunk_index.asc().nullslast(),
                AssetMention.created_at.desc(),
            )
        ).all()

        events: list[dict[str, Any]] = []
        for mention, document, chunk in rows:
            filename = document.original_filename if document is not None else None
            text = chunk.text if chunk is not None else None
            text_preview = _text_preview(text)
            event_date = _iso(
                document.created_at if document is not None else mention.created_at
            )
            title = (
                f"{asset.tag} mentioned in {filename}"
                if filename
                else f"{asset.tag} mentioned"
            )
            events.append(
                {
                    "id": mention.id,
                    "asset_tag": asset.tag,
                    "event_type": "mention",
                    "title": title,
                    "date": event_date,
                    "document_id": mention.document_id,
                    "filename": filename,
                    "chunk_id": mention.chunk_id,
                    "chunk_index": chunk.chunk_index if chunk is not None else None,
                    "text_preview": text_preview,
                    "citation": {
                        "document_id": mention.document_id,
                        "chunk_id": mention.chunk_id,
                        "chunk_index": (
                            chunk.chunk_index if chunk is not None else None
                        ),
                        "filename": filename,
                    },
                }
            )
        return events


def get_asset_graph_by_tag(
    tag: str, session: Session | None = None
) -> dict[str, Any] | None:
    """Build a derived knowledge graph for an asset from its mentions.

    The graph is computed on the fly from ``asset_mentions`` (it does not read
    ``knowledge_edges``), with one asset node plus document, chunk, and entity
    nodes, and edges from the asset to each related node. Node IDs are stable and
    namespaced (``asset:<tag>``, ``document:<id>``, ``chunk:<id>``,
    ``entity:<id>``). Returns ``None`` when the asset is unknown.
    """

    normalized_tag = tag.strip().upper()
    if not normalized_tag:
        return None

    with _unit_of_work(session) as active:
        asset = active.execute(
            select(Asset).where(Asset.tag == normalized_tag)
        ).scalar_one_or_none()
        if asset is None:
            return None

        rows = active.execute(
            select(AssetMention, ExtractedEntity, Document, DocumentChunk)
            .outerjoin(
                ExtractedEntity, AssetMention.entity_id == ExtractedEntity.id
            )
            .outerjoin(Document, AssetMention.document_id == Document.id)
            .outerjoin(DocumentChunk, AssetMention.chunk_id == DocumentChunk.id)
            .where(AssetMention.asset_id == asset.id)
            .order_by(
                Document.created_at.desc().nullslast(),
                DocumentChunk.chunk_index.asc().nullslast(),
                AssetMention.created_at.desc(),
            )
        ).all()

        asset_node_id = f"asset:{asset.tag}"
        nodes: dict[str, dict[str, Any]] = {
            asset_node_id: {
                "id": asset_node_id,
                "type": "asset",
                "label": asset.tag,
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
            }
        }
        edges: dict[str, dict[str, Any]] = {}

        def _add_edge(target_id: str, relation_type: str) -> None:
            key = f"{asset_node_id}|{relation_type}|{target_id}"
            if key not in edges:
                edges[key] = {
                    "id": key,
                    "source": asset_node_id,
                    "target": target_id,
                    "relation_type": relation_type,
                }

        for mention, entity, document, chunk in rows:
            if document is not None:
                node_id = f"document:{document.id}"
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "type": "document",
                        "label": document.original_filename,
                        "document_id": document.id,
                    }
                _add_edge(node_id, "mentioned_in")
            if chunk is not None:
                node_id = f"chunk:{chunk.id}"
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "type": "chunk",
                        "label": f"chunk #{chunk.chunk_index}",
                        "chunk_id": chunk.id,
                        "chunk_index": chunk.chunk_index,
                        "document_id": chunk.document_id,
                    }
                _add_edge(node_id, "supported_by_chunk")
            if entity is not None:
                node_id = f"entity:{entity.id}"
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "type": "entity",
                        "label": entity.raw_value,
                        "entity_id": entity.id,
                        "entity_type": entity.entity_type,
                    }
                _add_edge(node_id, "has_entity")

        node_list = list(nodes.values())
        edge_list = list(edges.values())
        return {
            "asset": _asset_to_dict(asset),
            "nodes": node_list,
            "edges": edge_list,
            "counts": {"nodes": len(node_list), "edges": len(edge_list)},
        }


def get_dashboard_summary(session: Session | None = None) -> dict[str, Any]:
    """Return live counts for the dashboard plus the most recent documents."""

    with _unit_of_work(session) as active:
        def _count(model: Any) -> int:
            return int(
                active.execute(select(func.count()).select_from(model)).scalar_one()
                or 0
            )

        recent_rows = (
            active.execute(
                select(Document)
                .order_by(Document.created_at.desc(), Document.id.desc())
                .limit(5)
            )
            .scalars()
            .all()
        )

        return {
            "documents_indexed": _count(Document),
            "chunks_created": _count(DocumentChunk),
            "assets_discovered": _count(Asset),
            "entities_extracted": _count(ExtractedEntity),
            "asset_mentions": _count(AssetMention),
            "knowledge_edges": _count(KnowledgeEdge),
            "recent_documents": [_document_to_dict(row) for row in recent_rows],
        }
