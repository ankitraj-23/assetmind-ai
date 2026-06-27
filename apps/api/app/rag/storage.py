"""Postgres storage for dataset documents, chunks, embeddings, and tags."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from sqlalchemy import delete

from app.db.models import Document
from app.db.session import session_scope
from app.rag import embeddings
from app.rag.chunking import chunk_units
from app.rag.extraction import SUPPORTED_EXTENSIONS, UnsupportedFileTypeError, extract_file
from app.rag.schemas import RAGChunk, RAGIngestResponse


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_dataset_path(path: str) -> Path:
    requested = Path(path).expanduser()
    if requested.is_absolute():
        return requested.resolve()

    candidates = [
        Path.cwd() / requested,
        repo_root() / requested,
        Path.cwd().parent.parent / requested,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (repo_root() / requested).resolve()


def stable_document_id(source_path: Path) -> str:
    digest = hashlib.sha1(str(source_path.resolve()).lower().encode("utf-8")).hexdigest()
    return f"rag-{digest[:20]}"


def _content_type(path: Path) -> str:
    return {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".csv": "text/csv",
    }.get(path.suffix.lower(), "application/octet-stream")


def _persist_chunk_entities(session, chunk: RAGChunk) -> None:
    from app.db import repository as repo
    from app.services import entity_extraction

    tags = entity_extraction.extract_equipment_tags(
        chunk.content,
        document_id=chunk.document_id,
        chunk_id=chunk.id,
        page_number=chunk.page_number,
    )
    for tag in tags:
        entity = repo.store_extracted_entity(
            session=session,
            entity_type=tag.entity_type,
            raw_value=tag.raw_value,
            normalized_value=tag.normalized_value,
            confidence=tag.confidence,
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            page_number=chunk.page_number,
            char_start=tag.char_start,
            char_end=tag.char_end,
            extraction_method=tag.extraction_method,
            metadata={"source": "rag_dataset"},
        )
        asset = repo.upsert_asset_from_tag(
            tag.normalized_value,
            asset_type=tag.asset_type,
            display_name=tag.normalized_value,
            metadata={"source": "rag_dataset"},
            session=session,
        )
        repo.create_asset_mention(
            session=session,
            asset_id=asset["id"],
            entity_id=entity["id"],
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            page_number=chunk.page_number,
            confidence=tag.confidence,
        )


def ingest_dataset(
    path: str,
    *,
    force_reingest: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> RAGIngestResponse:
    """Ingest supported dataset files into Postgres with Gemini embeddings."""

    from app.db import repository as repo

    embeddings.ensure_configured()
    dataset_path = resolve_dataset_path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {dataset_path}")
    if not dataset_path.is_dir():
        raise NotADirectoryError(f"Dataset path is not a directory: {dataset_path}")

    documents_ingested = 0
    chunks_created = 0
    embeddings_created = 0
    skipped: list[str] = []

    files = sorted(file for file in dataset_path.iterdir() if file.is_file())
    if not files:
        raise ValueError(f"No documents found in dataset path: {dataset_path}")

    def report(message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    report(f"Scanning dataset: {dataset_path}")
    for file_path in files:
        report(f"Processing {file_path.name}")
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            skipped.append(f"{file_path.name}: unsupported file type")
            report(f"Skipped {file_path.name}: unsupported file type")
            continue

        document_id = stable_document_id(file_path)
        try:
            with session_scope() as session:
                existing = repo.get_document(document_id, session=session)
                if existing and not force_reingest:
                    skipped.append(f"{file_path.name}: already ingested")
                    report(f"Skipped {file_path.name}: already ingested")
                    continue
                if existing and force_reingest:
                    session.execute(delete(Document).where(Document.id == document_id))
                    session.flush()

            units = extract_file(file_path)
            report(f"Extracted {len(units)} text unit(s) from {file_path.name}")
            if not units:
                skipped.append(f"{file_path.name}: no extractable text")
                report(f"Skipped {file_path.name}: no extractable text")
                continue

            chunks = chunk_units(document_id, units)
            report(f"Created {len(chunks)} chunk(s) for {file_path.name}")
            if not chunks:
                skipped.append(f"{file_path.name}: no chunks created")
                report(f"Skipped {file_path.name}: no chunks created")
                continue

            vectors = embeddings.embed_texts(
                [chunk.content for chunk in chunks],
                progress_callback=lambda index, total, name=file_path.name: report(
                    f"Embedding {name}: chunk {index}/{total}"
                ),
            )

            with session_scope() as session:
                repo.create_document(
                    session=session,
                    id=document_id,
                    original_filename=file_path.name,
                    content_type=_content_type(file_path),
                    size_bytes=file_path.stat().st_size,
                    text_char_count=sum(len(unit.text) for unit in units),
                    status="processed",
                    storage_path=str(file_path.resolve()),
                    stored_filename=file_path.name,
                    source_type="dataset",
                    chunk_count=len(chunks),
                    metadata={"source_path": str(file_path.resolve()), "rag": True},
                )

                page_ids: dict[int, str] = {}
                for unit in units:
                    if unit.page_number is None:
                        continue
                    page = repo.create_document_page(
                        session=session,
                        document_id=document_id,
                        page_number=unit.page_number,
                        text=unit.text,
                        metadata=unit.metadata,
                    )
                    page_ids[unit.page_number] = page["id"]

                for chunk, vector in zip(chunks, vectors):
                    repo.create_document_chunk(
                        session=session,
                        id=chunk.id,
                        document_id=document_id,
                        chunk_index=chunk.chunk_index,
                        text=chunk.content,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        token_count=chunk.token_count,
                        page_id=page_ids.get(chunk.page_number or -1),
                        metadata={
                            **chunk.metadata,
                            "file_name": chunk.file_name,
                            "source_path": chunk.source_path,
                            "page_number": chunk.page_number,
                            "row_number": chunk.row_number,
                        },
                    )
                    repo.store_chunk_embedding(
                        session=session,
                        chunk_id=chunk.id,
                        vector=vector,
                        embedding_model=embeddings._embedding_model(),
                    )
                    _persist_chunk_entities(session, chunk)

            documents_ingested += 1
            chunks_created += len(chunks)
            embeddings_created += len(vectors)
            report(f"Stored {file_path.name}: {len(chunks)} chunk(s)")
        except UnsupportedFileTypeError as exc:
            skipped.append(f"{file_path.name}: {exc}")
            report(f"Skipped {file_path.name}: {exc}")

    return RAGIngestResponse(
        documents_ingested=documents_ingested,
        chunks_created=chunks_created,
        embeddings_created=embeddings_created,
        skipped=skipped,
    )
