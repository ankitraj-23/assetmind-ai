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

from app.core.config import settings
from app.models.document import Document

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

    document = Document(
        id=doc_id,
        filename=sanitized,
        content_type=content_type,
        size_bytes=len(raw),
        text_char_count=char_count,
        status="extracted" if char_count > 0 else "empty",
        storage_path=str(dest),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _append_metadata(document)
    return document


def list_documents() -> list[Document]:
    """Return all documents recorded in local metadata storage."""
    return [Document(**record) for record in _load_metadata()]
