"""Vector retrieval over pgvector-backed document chunks."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import Document, DocumentChunk
from app.db.session import session_scope
from app.rag import embeddings
from app.rag.schemas import RetrievedChunk


def retrieve_relevant_chunks(question: str, top_k: int = 5) -> list[RetrievedChunk]:
    """Embed ``question`` and return the most relevant stored chunks."""

    if not question.strip():
        raise ValueError("Question must not be empty.")
    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20.")

    query_vector = embeddings.embed_query(question)
    return _retrieve_by_vector(query_vector, top_k)


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
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.text,
                score=round(score, 6),
                distance=round(distance_value, 6) if distance_value is not None else None,
                file_name=metadata.get("file_name") or document.original_filename,
                source_path=metadata.get("source_path") or document.storage_path,
                page_number=metadata.get("page_number"),
                row_number=metadata.get("row_number"),
                chunk_index=chunk.chunk_index,
                metadata=metadata,
            )
        )
    return results

