"""Summary-indexed retrieval over pgvector-backed parent chunks."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import Document, DocumentChunk
from app.db.session import session_scope
from app.rag import embeddings
from app.rag.schemas import RetrievedChunk


def retrieve_relevant_chunks(question: str, top_k: int = 5) -> list[RetrievedChunk]:
    """Embed ``question`` and return raw parent chunks via summary retrieval."""

    if not question.strip():
        raise ValueError("Question must not be empty.")
    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20.")

    query_vector = embeddings.embed_query(question)
    return _dedupe_parent_chunks(_retrieve_by_vector(query_vector, top_k))


def _retrieve_by_vector(query_vector: list[float], top_k: int) -> list[RetrievedChunk]:
    distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
    statement = (
        select(DocumentChunk, Document, distance)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.embedding.isnot(None))
        .order_by(distance.asc(), DocumentChunk.document_id.asc(), DocumentChunk.chunk_index.asc())
        .limit(top_k)
    )

    with session_scope() as session:
        rows = session.execute(statement).all()

    results: list[RetrievedChunk] = []
    for chunk, document, raw_distance in rows:
        metadata = dict(chunk.metadata_json or {})
        distance_value = float(raw_distance) if raw_distance is not None else None
        score = 0.0 if distance_value is None else max(0.0, 1.0 - distance_value)
        parent_chunk_id = metadata.get("parent_chunk_id") or chunk.id
        retrieval_unit_id = metadata.get("retrieval_unit_id") or f"{chunk.id}:summary:0"
        raw_text = chunk.text
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                parent_chunk_id=parent_chunk_id,
                retrieval_unit_id=retrieval_unit_id,
                content=raw_text,
                raw_text=raw_text,
                retrieval_summary=metadata.get("retrieval_summary"),
                summary_strategy=metadata.get("summary_strategy"),
                score=round(score, 6),
                distance=round(distance_value, 6) if distance_value is not None else None,
                file_name=metadata.get("file_name") or document.original_filename,
                source_path=metadata.get("source_path") or document.storage_path,
                source_type=metadata.get("source_type"),
                page_number=metadata.get("page_number"),
                page_start=metadata.get("page_start"),
                page_end=metadata.get("page_end"),
                row_number=metadata.get("row_number"),
                row_index=metadata.get("row_index"),
                row_start=metadata.get("row_start"),
                row_end=metadata.get("row_end"),
                section_title=metadata.get("section_title"),
                asset_tags=list(metadata.get("asset_tags") or []),
                modality=metadata.get("modality"),
                chunk_index=chunk.chunk_index,
                metadata=metadata,
            )
        )
    return results


def _dedupe_parent_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: set[str] = set()
    deduped: list[RetrievedChunk] = []
    for chunk in chunks:
        key = chunk.parent_chunk_id or chunk.chunk_id
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped

