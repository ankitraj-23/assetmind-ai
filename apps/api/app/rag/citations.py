"""Citation helpers for RAG responses."""

from __future__ import annotations

from app.rag.schemas import RAGCitation, RetrievedChunk

SNIPPET_CHARS = 220


def snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "..."


def citation_from_chunk(chunk: RetrievedChunk) -> RAGCitation:
    raw_text = chunk.raw_text or chunk.content
    return RAGCitation(
        file_name=chunk.file_name,
        page=chunk.page_start or chunk.page_number,
        row=chunk.row_start or chunk.row_index or chunk.row_number,
        section_title=chunk.section_title,
        parent_chunk_id=chunk.parent_chunk_id,
        retrieval_unit_id=chunk.retrieval_unit_id,
        chunk_id=chunk.chunk_id,
        source_path=chunk.source_path,
        snippet=snippet(raw_text),
    )


def citations_from_chunks(chunks: list[RetrievedChunk]) -> list[RAGCitation]:
    seen: set[str] = set()
    citations: list[RAGCitation] = []
    for chunk in chunks:
        key = chunk.chunk_id
        if key in seen:
            continue
        seen.add(key)
        citations.append(citation_from_chunk(chunk))
    return citations

