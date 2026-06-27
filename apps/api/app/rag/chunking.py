"""Deterministic page/row-aware chunking for RAG ingestion."""

from __future__ import annotations

from app.rag.schemas import ExtractedTextUnit, RAGChunk

CHUNK_SIZE_CHARS = 3500
CHUNK_OVERLAP_CHARS = 500
_STRIDE = CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS


def chunk_units(
    document_id: str,
    units: list[ExtractedTextUnit],
    *,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[RAGChunk]:
    """Split extracted units into stable overlapping chunks."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size.")

    chunks: list[RAGChunk] = []
    stride = chunk_size - overlap
    chunk_index = 0

    for unit in units:
        text = unit.text.strip()
        if not text:
            continue
        start = 0
        length = len(text)
        while start < length:
            end = min(start + chunk_size, length)
            content = text[start:end].strip()
            if content:
                chunks.append(
                    RAGChunk(
                        document_id=document_id,
                        file_name=unit.file_name,
                        source_path=unit.source_path,
                        chunk_index=chunk_index,
                        content=content,
                        char_start=start,
                        char_end=end,
                        token_count=len(content.split()),
                        page_number=unit.page_number,
                        row_number=unit.row_number,
                        metadata={
                            **unit.metadata,
                            "unit_index": unit.unit_index,
                            "source_page": unit.page_number,
                            "source_row": unit.row_number,
                        },
                    )
                )
                chunk_index += 1
            if end == length:
                break
            start += stride

    return chunks

