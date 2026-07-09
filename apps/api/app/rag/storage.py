"""Postgres storage for summary-indexed parent-child RAG."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from sqlalchemy import delete, select

from app.db.models import Document, DocumentChunk, DocumentPage
from app.db.session import session_scope
from app.rag import embeddings
from app.rag.chunking import build_parent_chunks
from app.rag.extraction import SUPPORTED_EXTENSIONS, UnsupportedFileTypeError, extract_file
from app.rag.manual_summaries import load_parent_summaries
from app.rag.schemas import ParentChunkSummary
from app.rag.schemas import ParentChunk, RAGIngestResponse, RetrievalUnit
from app.rag.summaries import (
    build_parent_summary,
    build_retrieval_unit,
    summarize_atomic_elements,
)

RAG_STRATEGY = "summary-indexed layout-aware parent-child rag"


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
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(path.suffix.lower(), "application/octet-stream")


def _persist_chunk_entities(session, chunk: ParentChunk) -> None:
    from app.db import repository as repo
    from app.services import entity_extraction

    tags = entity_extraction.extract_equipment_tags(
        chunk.raw_text,
        document_id=chunk.document_id,
        chunk_id=chunk.id,
        page_number=chunk.page_start,
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
            page_number=chunk.page_start,
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
            page_number=chunk.page_start,
            confidence=tag.confidence,
        )


def ingest_dataset(
    path: str,
    *,
    force_reingest: bool = False,
    parent_summaries_path: str | None = None,
    max_parent_chunks: int | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> RAGIngestResponse:
    """Ingest supported files as elements -> parent chunks -> summary embeddings."""

    from app.db import repository as repo

    embeddings.ensure_configured()
    dataset_path = resolve_dataset_path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {dataset_path}")
    if not dataset_path.is_dir():
        raise NotADirectoryError(f"Dataset path is not a directory: {dataset_path}")

    manual_summaries: dict[str, ParentChunkSummary] = {}
    if parent_summaries_path:
        manual_summaries = load_parent_summaries(parent_summaries_path)
    if max_parent_chunks is not None and max_parent_chunks < 1:
        raise ValueError("max_parent_chunks must be at least 1 when provided.")

    documents_ingested = 0
    elements_extracted = 0
    atomic_summaries_created = 0
    chunks_created = 0
    parent_chunks_created = 0
    retrieval_summaries_created = 0
    embeddings_created = 0
    template_summaries_count = 0
    llm_summaries_count = 0
    fallback_summaries_count = 0
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
                if existing and force_reingest:
                    session.execute(delete(Document).where(Document.id == document_id))
                    session.flush()
                elif existing:
                    report(f"Resuming existing document {file_path.name}")

            elements = extract_file(file_path, document_id=document_id)
            elements = summarize_atomic_elements(elements)
            atomic_summary_count = sum(1 for element in elements if element.element_summary)
            report(f"Extracted {len(elements)} document element(s) from {file_path.name}")
            report(
                f"Created {atomic_summary_count} atomic visual summar(y/ies) "
                f"for {file_path.name}"
            )
            if not elements:
                skipped.append(f"{file_path.name}: no extractable text")
                report(f"Skipped {file_path.name}: no extractable text")
                continue

            parent_chunks = build_parent_chunks(document_id, elements)
            if max_parent_chunks is not None:
                remaining = max_parent_chunks - parent_chunks_created
                if remaining <= 0:
                    report("Reached max parent chunk limit; stopping ingestion")
                    break
                parent_chunks = parent_chunks[:remaining]
            report(f"Created {len(parent_chunks)} parent chunk(s) for {file_path.name}")
            if not parent_chunks:
                skipped.append(f"{file_path.name}: no parent chunks created")
                report(f"Skipped {file_path.name}: no parent chunks created")
                continue

            retrieval_units: list[RetrievalUnit] = []
            for parent in parent_chunks:
                parent_summary = _parent_summary_for_ingestion(parent, manual_summaries)
                parent = parent.model_copy(update={"parent_summary": parent_summary})
                parent_chunks[parent.chunk_index] = parent
                retrieval_unit = build_retrieval_unit(parent)
                retrieval_units.append(retrieval_unit)
                if retrieval_unit.summary_strategy in {"template", "parent_template"}:
                    template_summaries_count += 1
                elif retrieval_unit.summary_strategy in {"llm", "parent_llm", "manual_parent_llm"}:
                    llm_summaries_count += 1
                else:
                    fallback_summaries_count += 1
            report(
                f"Created {len(retrieval_units)} retrieval summar(y/ies) "
                f"for {file_path.name}"
            )

            with session_scope() as session:
                _ensure_document_row(
                    session=session,
                    document_id=document_id,
                    file_path=file_path,
                    elements=elements,
                    parent_chunks=parent_chunks,
                )
                page_ids = _ensure_document_pages(
                    session=session,
                    document_id=document_id,
                    elements=elements,
                )

            embedded_for_file = 0
            skipped_for_file = 0
            total_units = len(retrieval_units)
            for index, (parent, retrieval_unit) in enumerate(
                zip(parent_chunks, retrieval_units),
                start=1,
            ):
                with session_scope() as session:
                    chunk = session.get(DocumentChunk, parent.id)
                    if chunk is None:
                        repo.create_document_chunk(
                            session=session,
                            id=parent.id,
                            document_id=document_id,
                            chunk_index=parent.chunk_index,
                            text=parent.raw_text,
                            char_start=None,
                            char_end=None,
                            token_count=len(parent.raw_text.split()),
                            page_id=page_ids.get(parent.page_start or -1),
                            metadata=_chunk_metadata(parent, retrieval_unit),
                        )
                        _persist_chunk_entities(session, parent)
                    elif chunk.embedding is not None:
                        skipped_for_file += 1
                        report(
                            f"Skipped {file_path.name}: retrieval summary "
                            f"{index}/{total_units} already embedded"
                        )
                        continue

                report(
                    f"Embedding {file_path.name}: retrieval summary "
                    f"{index}/{total_units}"
                )
                vector = embeddings.embed_text(retrieval_unit.summary_text)
                with session_scope() as session:
                    repo.store_chunk_embedding(
                        session=session,
                        chunk_id=parent.id,
                        vector=vector,
                        embedding_model=embeddings._embedding_model(),
                    )
                embedded_for_file += 1
                embeddings_created += 1
                report(
                    f"Stored embedding {file_path.name}: retrieval summary "
                    f"{index}/{total_units}"
                )

            documents_ingested += 1
            elements_extracted += len(elements)
            atomic_summaries_created += atomic_summary_count
            chunks_created += len(parent_chunks)
            parent_chunks_created += len(parent_chunks)
            retrieval_summaries_created += len(retrieval_units)
            report(
                f"Stored {file_path.name}: {embedded_for_file} new embedding(s), "
                f"{skipped_for_file} already embedded"
            )
        except UnsupportedFileTypeError as exc:
            skipped.append(f"{file_path.name}: {exc}")
            report(f"Skipped {file_path.name}: {exc}")

    return RAGIngestResponse(
        documents_ingested=documents_ingested,
        elements_extracted=elements_extracted,
        atomic_summaries_created=atomic_summaries_created,
        chunks_created=chunks_created,
        parent_chunks_created=parent_chunks_created,
        retrieval_summaries_created=retrieval_summaries_created,
        embeddings_created=embeddings_created,
        template_summaries_count=template_summaries_count,
        llm_summaries_count=llm_summaries_count,
        fallback_summaries_count=fallback_summaries_count,
        skipped=skipped,
    )


def _ensure_document_row(
    *,
    session,
    document_id: str,
    file_path: Path,
    elements: list,
    parent_chunks: list[ParentChunk],
) -> None:
    document = session.get(Document, document_id)
    metadata = {
        "source_path": str(file_path.resolve()),
        "rag": True,
        "rag_strategy": RAG_STRATEGY,
        "element_count": len(elements),
        "resumable_ingestion": True,
    }
    if document is None:
        document = Document(
            id=document_id,
            original_filename=file_path.name,
            content_type=_content_type(file_path),
            size_bytes=file_path.stat().st_size,
            text_char_count=sum(len(element.text) for element in elements),
            status="processed",
            storage_path=str(file_path.resolve()),
            stored_filename=file_path.name,
            source_type="dataset",
            chunk_count=len(parent_chunks),
            metadata_json=metadata,
        )
        session.add(document)
        session.flush()
        return

    document.original_filename = file_path.name
    document.content_type = _content_type(file_path)
    document.size_bytes = file_path.stat().st_size
    document.text_char_count = sum(len(element.text) for element in elements)
    document.status = "processed"
    document.storage_path = str(file_path.resolve())
    document.stored_filename = file_path.name
    document.source_type = "dataset"
    document.chunk_count = len(parent_chunks)
    document.metadata_json = {**dict(document.metadata_json or {}), **metadata}
    session.flush()


def _ensure_document_pages(*, session, document_id: str, elements: list) -> dict[int, str]:
    page_texts: dict[int, list[str]] = {}
    for element in elements:
        if element.page_number is not None:
            page_texts.setdefault(element.page_number, []).append(element.text)

    existing_pages = session.execute(
        select(DocumentPage).where(DocumentPage.document_id == document_id)
    ).scalars().all()
    page_ids = {page.page_number: page.id for page in existing_pages}

    for page_number, texts in sorted(page_texts.items()):
        page_text = "\n".join(texts)
        existing_page = next(
            (page for page in existing_pages if page.page_number == page_number),
            None,
        )
        if existing_page is not None:
            existing_page.text = page_text
            existing_page.metadata_json = {
                **dict(existing_page.metadata_json or {}),
                "source": "document_elements",
            }
            page_ids[page_number] = existing_page.id
            continue

        page = DocumentPage(
            id=hashlib.sha1(f"{document_id}:{page_number}".encode("utf-8")).hexdigest(),
            document_id=document_id,
            page_number=page_number,
            text=page_text,
            metadata_json={"source": "document_elements"},
        )
        session.add(page)
        session.flush()
        page_ids[page_number] = page.id
    return page_ids


def _chunk_metadata(parent: ParentChunk, retrieval_unit: RetrievalUnit) -> dict:
    return {
        **parent.metadata,
        "chunk_kind": "parent",
        "rag_strategy": RAG_STRATEGY,
        "file_name": parent.source_file,
        "source_path": parent.source_path,
        "source_type": parent.source_type,
        "page_number": parent.page_start,
        "page_start": parent.page_start,
        "page_end": parent.page_end,
        "row_number": parent.row_start,
        "row_index": parent.row_start,
        "row_start": parent.row_start,
        "row_end": parent.row_end,
        "section_title": parent.section_title,
        "parent_chunk_id": parent.parent_chunk_id,
        "retrieval_unit_id": retrieval_unit.retrieval_unit_id,
        "retrieval_summary": retrieval_unit.summary_text,
        "answerable_questions": retrieval_unit.answerable_questions,
        "summary_strategy": retrieval_unit.summary_strategy,
        "parent_summary": (
            parent.parent_summary.model_dump() if parent.parent_summary else None
        ),
        "parent_summary_asset_tags": (
            parent.parent_summary.asset_tags if parent.parent_summary else []
        ),
        "asset_tags": parent.asset_tags,
        "modality": parent.modality,
        "element_ids": parent.element_ids,
        "atomic_element_summaries": [
            summary.model_dump() for summary in parent.element_summaries
        ],
        "visual_elements": [
            element.model_dump() for element in parent.visual_elements
        ],
    }


def _parent_summary_for_ingestion(
    parent: ParentChunk,
    manual_summaries: dict[str, ParentChunkSummary],
) -> ParentChunkSummary:
    if not manual_summaries:
        return build_parent_summary(parent)
    try:
        return manual_summaries[parent.parent_chunk_id]
    except KeyError as exc:
        raise ValueError(
            "Manual parent summaries file is missing summary for "
            f"{parent.parent_chunk_id}. Regenerate summaries from the current "
            "parent_elements_for_summary.jsonl file."
        ) from exc
