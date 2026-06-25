"""Document ingestion: save uploads, extract text, and persist metadata.

This is the first Week 1 slice. It deliberately uses local filesystem storage
and a flat JSON metadata file — no database, embeddings, or chunking yet.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core import config
from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.embedding import ChunkEmbedding
from app.services import chunking, embeddings

_EXTENSION_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}
_SUPPORTED_CONTENT_TYPES = set(_EXTENSION_CONTENT_TYPES.values())
_METADATA_FILENAME = "metadata.json"


def _storage_dir() -> Path:
    """Return the storage directory, creating it if necessary."""
    path = Path(settings.storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _metadata_path() -> Path:
    return _storage_dir() / _METADATA_FILENAME


def _sanitize_filename(filename: str | None) -> str:
    """Strip any directory components and unsafe characters from a filename."""
    name = Path(filename or "").name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    name = name.lstrip(".")  # avoid hidden/relative names like ".." or ".env"
    return name[:200] or "upload"


def _resolve_type(sanitized_name: str, content_type: str | None) -> tuple[str, str]:
    """Determine the file extension and a normalized content type.

    Raises 415 if the file type is not supported.
    """
    ext = Path(sanitized_name).suffix.lower()
    if ext in _EXTENSION_CONTENT_TYPES:
        return ext, _EXTENSION_CONTENT_TYPES[ext]
    if content_type in _SUPPORTED_CONTENT_TYPES:
        # Recover the extension from the declared content type.
        for known_ext, known_type in _EXTENSION_CONTENT_TYPES.items():
            if known_type == content_type:
                return known_ext, known_type
    raise HTTPException(
        status_code=415,
        detail="Unsupported file type. Only PDF (.pdf) and plain text (.txt) are accepted.",
    )


def _extract_text(path: Path, ext: str) -> str:
    """Extract raw text from a saved file based on its extension."""
    if ext == ".pdf":
        try:
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
        except (PdfReadError, OSError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to read PDF: {exc}",
            ) from exc
        return "\n".join(pages).strip()

    # Plain text.
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _load_metadata() -> list[dict]:
    path = _metadata_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _append_metadata(document: Document) -> None:
    records = _load_metadata()
    records.append(document.model_dump())
    _metadata_path().write_text(json.dumps(records, indent=2), encoding="utf-8")


def _document_from_record(record: dict) -> Document:
    """Map a repository document dict onto the API ``Document`` schema."""
    return Document(
        id=record["id"],
        filename=record.get("filename") or record.get("original_filename") or "",
        content_type=record.get("content_type") or "",
        size_bytes=record.get("size_bytes") or 0,
        text_char_count=record.get("text_char_count") or 0,
        status=record.get("status") or "",
        storage_path=record.get("storage_path") or "",
        created_at=record.get("created_at") or "",
        chunk_count=record.get("chunk_count") or 0,
    )


def _persist_chunk_entities(session, document_id: str, chunk: Chunk) -> None:
    """Extract equipment tags from one chunk and persist the asset graph.

    For each unique tag in the chunk this writes an ``extracted_entities`` row,
    upserts the corresponding ``assets`` row, and links them with an
    ``asset_mentions`` row. All writes share the caller's ``session`` so they
    commit (or roll back) together with the chunk/embedding writes.
    """
    from app.db import repository as repo
    from app.services import entity_extraction

    tags = entity_extraction.extract_equipment_tags(
        chunk.text,
        document_id=document_id,
        chunk_id=chunk.id,
    )
    for tag in tags:
        entity = repo.store_extracted_entity(
            session=session,
            entity_type=tag.entity_type,
            raw_value=tag.raw_value,
            normalized_value=tag.normalized_value,
            confidence=tag.confidence,
            document_id=document_id,
            chunk_id=chunk.id,
            page_number=tag.page_number,
            char_start=tag.char_start,
            char_end=tag.char_end,
            extraction_method=tag.extraction_method,
        )
        asset = repo.upsert_asset_from_tag(
            tag.normalized_value,
            asset_type=tag.asset_type,
            display_name=tag.normalized_value,
            session=session,
        )
        repo.create_asset_mention(
            session=session,
            asset_id=asset["id"],
            entity_id=entity["id"],
            document_id=document_id,
            chunk_id=chunk.id,
            page_number=tag.page_number,
            confidence=tag.confidence,
        )


def _persist_postgres(
    document: Document,
    chunks: list[Chunk],
    chunk_embeddings: list[ChunkEmbedding],
) -> None:
    """Write document metadata, chunks, and embeddings to Postgres atomically.

    The raw upload is still saved to local storage by the caller; only the
    derived metadata/chunks/embeddings (and extracted equipment assets) live in
    the database.
    """
    # Imported lazily so JSON mode never touches the database layer.
    from app.db import repository as repo
    from app.db.session import session_scope

    embeddings_by_chunk = {emb.chunk_id: emb for emb in chunk_embeddings}

    with session_scope() as session:
        repo.create_document(
            session=session,
            id=document.id,
            original_filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            text_char_count=document.text_char_count,
            status=document.status,
            storage_path=document.storage_path,
            stored_filename=Path(document.storage_path).name,
            source_type="upload",
            chunk_count=document.chunk_count,
        )
        for chunk in chunks:
            repo.create_document_chunk(
                session=session,
                id=chunk.id,
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
            )
            emb = embeddings_by_chunk.get(chunk.id)
            if emb is not None:
                repo.store_chunk_embedding(
                    session=session,
                    chunk_id=chunk.id,
                    vector=emb.vector,
                    embedding_model=emb.model,
                )
            # Deterministic equipment-tag extraction -> assets + mentions.
            _persist_chunk_entities(session, document.id, chunk)


async def ingest_upload(upload: UploadFile) -> Document:
    """Save an uploaded file, extract its text, and record metadata."""
    sanitized = _sanitize_filename(upload.filename)
    ext, content_type = _resolve_type(sanitized, upload.content_type)

    raw = await upload.read()

    doc_id = uuid.uuid4().hex
    storage_dir = _storage_dir()
    dest = storage_dir / f"{doc_id}_{sanitized}"

    # Path-traversal guard: the destination must stay inside the storage dir.
    if storage_dir.resolve() not in dest.resolve().parents:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    dest.write_bytes(raw)

    text = _extract_text(dest, ext)
    char_count = len(text)

    chunks = chunking.chunk_text(doc_id, text)
    chunk_embeddings = embeddings.embed_chunks(doc_id, chunks)

    document = Document(
        id=doc_id,
        filename=sanitized,
        content_type=content_type,
        size_bytes=len(raw),
        text_char_count=char_count,
        status="extracted" if char_count > 0 else "empty",
        storage_path=str(dest),
        created_at=datetime.now(timezone.utc).isoformat(),
        chunk_count=len(chunks),
    )

    if config.use_postgres():
        # Raw file already saved above; metadata/chunks/embeddings go to Postgres.
        _persist_postgres(document, chunks, chunk_embeddings)
    else:
        chunking.save_chunks(doc_id, chunks)
        embeddings.save_embeddings(doc_id, chunk_embeddings)
        _append_metadata(document)
    return document


def list_documents() -> list[Document]:
    """Return all documents from the active persistence backend."""
    if config.use_postgres():
        from app.db import repository as repo

        return [_document_from_record(record) for record in repo.list_documents()]
    return [Document(**record) for record in _load_metadata()]
