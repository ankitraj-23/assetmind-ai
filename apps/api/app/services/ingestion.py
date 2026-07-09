"""Document ingestion: save uploads, extract text, and persist metadata.

Supported formats
-----------------
- PDF  (.pdf)  — text extracted page-by-page via pypdf
- Text (.txt)  — read as UTF-8
- CSV  (.csv)  — each row becomes one chunk; facts extracted from columns
- XLSX (.xlsx) — each row across all sheets becomes one chunk; facts extracted
"""

from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)


def _progress(message: str) -> None:
    """Emit a user-visible ingestion progress line.

    The project has no logging configuration, so uvicorn/script consumers would
    never see ``logger.info`` output. Printing to stdout (flushed) makes bulk
    ingestion progress visible in both the API console and the seeding scripts,
    matching the print-based convention used across ``scripts/``.
    """
    print(message, flush=True)
    logger.info(message)


# ── supported file types ─────────────────────────────────────────────────────

_EXTENSION_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_SUPPORTED_CONTENT_TYPES = set(_EXTENSION_CONTENT_TYPES.values())
_METADATA_FILENAME = "metadata.json"
_FACTS_FILENAME = "facts.json"


# ── storage helpers ───────────────────────────────────────────────────────────

def _storage_dir() -> Path:
    path = Path(settings.storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _metadata_path() -> Path:
    return _storage_dir() / _METADATA_FILENAME


def _facts_path() -> Path:
    return _storage_dir() / _FACTS_FILENAME


def _sanitize_filename(filename: str | None) -> str:
    name = Path(filename or "").name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    name = name.lstrip(".")
    return name[:200] or "upload"


def _resolve_type(sanitized_name: str, content_type: str | None) -> tuple[str, str]:
    ext = Path(sanitized_name).suffix.lower()
    if ext in _EXTENSION_CONTENT_TYPES:
        return ext, _EXTENSION_CONTENT_TYPES[ext]
    if content_type in _SUPPORTED_CONTENT_TYPES:
        for known_ext, known_type in _EXTENSION_CONTENT_TYPES.items():
            if known_type == content_type:
                return known_ext, known_type
    raise HTTPException(
        status_code=415,
        detail=(
            "Unsupported file type. Accepted: PDF (.pdf), plain text (.txt), "
            "CSV (.csv), Excel (.xlsx)."
        ),
    )


# ── PDF / TXT text extraction ─────────────────────────────────────────────────

def _extract_text(path: Path, ext: str) -> str:
    """Extract text from a PDF or plain-text file.

    PDF pages are joined with ``[Page N]`` markers so downstream code can
    recover the source page number from any text chunk.
    """
    if ext == ".pdf":
        try:
            reader = PdfReader(str(path))
            page_blocks: list[str] = []
            for i, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    page_blocks.append(f"[Page {i}]\n{page_text}")
        except (PdfReadError, OSError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to read PDF: {exc}",
            ) from exc
        return "\n\n".join(page_blocks).strip()
    return path.read_text(encoding="utf-8", errors="replace").strip()


# ── JSON metadata store ───────────────────────────────────────────────────────

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


# ── facts store (JSON mode only) ──────────────────────────────────────────────

def _load_facts() -> dict[str, dict]:
    path = _facts_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_chunk_facts(chunk_facts: dict[str, dict]) -> None:
    """Merge new chunk_id→facts entries into the persistent facts store."""
    store = _load_facts()
    store.update(chunk_facts)
    _facts_path().write_text(json.dumps(store, indent=2), encoding="utf-8")


def get_chunk_facts(chunk_id: str) -> dict:
    """Return stored facts for a chunk, or an empty dict if none."""
    return _load_facts().get(chunk_id, {})


# ── structured fact extraction from tabular rows ──────────────────────────────

# Maps each fact key to a ranked list of column-name keywords (case/space
# insensitive). First keyword match per row wins.
_FACT_COLUMN_KEYWORDS: dict[str, list[str]] = {
    "equipment_tag": [
        "equipment_id", "equipmentid", "asset_tag", "assettag",
        "equipment", "asset_id", "assetid", "tag",
    ],
    "asset_type": [
        "asset_type", "assettype", "equipment_type", "equipmenttype",
        "type", "category",
    ],
    "failure_mode": [
        "failure_mode", "failuremode", "fault_type", "faulttype",
        "failure", "problem", "issue", "workorderdescription",
        "work_order_description", "fault_description",
    ],
    "maintenance_action": [
        "maintenance_action", "maintenanceaction", "corrective_action",
        "correctiveaction", "operationdescription", "operation_description",
        "action", "repair", "work_done", "workdone", "ordertype",
    ],
    "inspection_reading": [
        "inspection_reading", "inspectionreading", "reading",
        "measurement", "sensor_value", "sensorvalue", "measured_value",
        "measuredvalue", "value",
    ],
    "date": [
        "order_date", "orderdate", "inspection_date", "inspectiondate",
        "event_date", "eventdate", "created_at", "createdat",
        "timestamp", "date",
    ],
    "sop_reference": [
        "sop_reference", "sopreference", "sop_id", "sopid",
        "procedure", "sop",
    ],
    "compliance_reference": [
        "compliance_reference", "compliancereference", "compliance_ref",
        "complianceref", "standard", "regulation", "oisd", "compliance",
    ],
    "spare_part": [
        "spare_part", "sparepart", "part_number", "partnumber",
        "part_no", "partno", "spare", "component", "bom",
    ],
    "risk_phrase": [
        "risk_phrase", "riskphrase", "risk_level", "risklevel",
        "severity", "priority", "criticality", "risk",
    ],
    "open_action": [
        "open_action", "openaction", "pending_action", "pendingaction",
        "next_action", "nextaction", "recommendation", "status",
    ],
}


def _normalize_col(col: str) -> str:
    """Lowercase and strip all spaces/underscores for loose matching."""
    return re.sub(r"[\s_]", "", col.lower())


def _extract_row_facts(row: dict) -> dict:
    """Map row column values to structured fact keys.

    Uses fuzzy column-name matching (case/space/underscore insensitive).
    Returns only fact keys for which a non-empty value was found.
    """
    # Build a lookup: normalized_col_name -> value
    normalized: dict[str, str] = {}
    for col, val in row.items():
        v = str(val).strip()
        if v and v.lower() not in ("nan", "none", ""):
            normalized[_normalize_col(col)] = v

    facts: dict[str, str] = {}
    for fact_key, keywords in _FACT_COLUMN_KEYWORDS.items():
        for kw in keywords:
            norm_kw = _normalize_col(kw)
            if norm_kw in normalized:
                facts[fact_key] = normalized[norm_kw]
                break
    return facts


def _row_to_text(row: dict, sheet_name: str | None = None) -> str:
    """Convert a single DataFrame row to a human-readable, embeddable text block."""
    parts: list[str] = []
    if sheet_name:
        parts.append(f"Sheet: {sheet_name}")
    for col, val in row.items():
        v = str(val).strip()
        if v and v.lower() not in ("nan", "none", ""):
            parts.append(f"{col}: {v}")
    return "\n".join(parts)


# ── Postgres persistence (shared by all formats) ──────────────────────────────

def _persist_chunk_entities(session, document_id: str, chunk: Chunk) -> None:
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
            _persist_chunk_entities(session, document.id, chunk)


def _persist_postgres_bulk(
    document: Document,
    chunks: list[Chunk],
    chunk_embeddings: list[ChunkEmbedding],
) -> None:
    """Persist a tabular document (CSV/XLSX) with a few batched flushes.

    The generic :func:`_persist_postgres` path flushes and refreshes once per
    chunk/entity/mention, which is ~10 round-trips per row — prohibitively slow
    for a many-row spreadsheet against a remote database. This bulk path builds
    the ORM rows in memory and flushes them a table at a time, cutting a whole
    document down to a handful of round-trips.

    Knowledge edges are intentionally *not* created here; the derived
    graph/dashboard views read from ``asset_mentions`` and stay correct, and the
    edges can be materialised afterwards with
    :mod:`scripts.backfill_knowledge_edges`.
    """
    from uuid import uuid4

    from sqlalchemy import select

    from app.db import models as m
    from app.db import repository as repo
    from app.db.session import session_scope
    from app.services import entity_extraction

    embeddings_by_chunk = {emb.chunk_id: emb for emb in chunk_embeddings}

    _progress(
        f"  Bulk-persisting '{document.filename}': {len(chunks)} chunk(s), "
        f"knowledge edges deferred to backfill…"
    )

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

        # 1) Chunks (+ embeddings inline) — one batched insert.
        for chunk in chunks:
            emb = embeddings_by_chunk.get(chunk.id)
            session.add(
                m.DocumentChunk(
                    id=chunk.id,
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    embedding=list(emb.vector) if emb is not None else None,
                    embedding_model=emb.model if emb is not None else None,
                )
            )
        session.flush()

        # Extract equipment tags for every chunk up front.
        tagged_chunks = [
            (
                chunk,
                entity_extraction.extract_equipment_tags(
                    chunk.text, document_id=document.id, chunk_id=chunk.id
                ),
            )
            for chunk in chunks
        ]

        # 2) Assets — resolve all referenced tags in one SELECT, insert only the
        # tags that do not yet exist (deduplicated across the whole document).
        wanted_tags = {
            tag.normalized_value.strip().upper()
            for _chunk, tags in tagged_chunks
            for tag in tags
        }
        tag_to_asset_id: dict[str, str] = {}
        if wanted_tags:
            for asset in (
                session.execute(
                    select(m.Asset).where(m.Asset.tag.in_(wanted_tags))
                )
                .scalars()
                .all()
            ):
                tag_to_asset_id[asset.tag] = asset.id

        new_assets: list[m.Asset] = []
        for _chunk, tags in tagged_chunks:
            for tag in tags:
                norm_tag = tag.normalized_value.strip().upper()
                if norm_tag and norm_tag not in tag_to_asset_id:
                    asset_id = uuid4().hex
                    tag_to_asset_id[norm_tag] = asset_id
                    new_assets.append(
                        m.Asset(
                            id=asset_id,
                            tag=norm_tag,
                            asset_type=tag.asset_type,
                            display_name=tag.normalized_value,
                        )
                    )
        if new_assets:
            session.add_all(new_assets)
            session.flush()

        # 3) Entities, then 4) mentions — batched inserts. Entities flush before
        # mentions so the mention -> entity foreign key is satisfied.
        entities: list[m.ExtractedEntity] = []
        pending: list[tuple] = []  # (chunk, extracted_tag, entity_id)
        for chunk, tags in tagged_chunks:
            for tag in tags:
                norm_tag = tag.normalized_value.strip().upper()
                if not norm_tag:
                    continue
                entity_id = uuid4().hex
                entities.append(
                    m.ExtractedEntity(
                        id=entity_id,
                        entity_type=tag.entity_type,
                        raw_value=tag.raw_value,
                        normalized_value=tag.normalized_value,
                        confidence=tag.confidence,
                        document_id=document.id,
                        chunk_id=chunk.id,
                        page_number=tag.page_number,
                        char_start=tag.char_start,
                        char_end=tag.char_end,
                        extraction_method=tag.extraction_method,
                    )
                )
                pending.append((chunk, tag, entity_id))
        if entities:
            session.add_all(entities)
            session.flush()

        mentions = [
            m.AssetMention(
                id=uuid4().hex,
                asset_id=tag_to_asset_id[tag.normalized_value.strip().upper()],
                entity_id=entity_id,
                document_id=document.id,
                chunk_id=chunk.id,
                page_number=tag.page_number,
                confidence=tag.confidence,
            )
            for chunk, tag, entity_id in pending
        ]
        if mentions:
            session.add_all(mentions)
            session.flush()

    _progress(
        f"  Bulk-persisted '{document.filename}': {len(chunks)} chunk(s), "
        f"{len(mentions)} asset mention(s) persisted."
    )


# ── CSV ingestion ─────────────────────────────────────────────────────────────

async def ingest_csv(upload: UploadFile) -> Document:
    """Ingest a CSV file — each row becomes one chunk with extracted facts.

    Facts are extracted from column names using fuzzy matching and stored
    in a JSON facts store (JSON mode) or alongside the chunk text (Postgres
    mode, where entity extraction picks up equipment tags from the text).
    """
    import pandas as pd

    sanitized = _sanitize_filename(upload.filename)
    raw = await upload.read()

    doc_id = uuid.uuid4().hex
    storage_dir = _storage_dir()
    dest = storage_dir / f"{doc_id}_{sanitized}"

    if storage_dir.resolve() not in dest.resolve().parents:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    dest.write_bytes(raw)

    # Try UTF-8 first; fall back to latin-1 for files with Windows encoding.
    try:
        df = pd.read_csv(dest, dtype=str, keep_default_na=False, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(dest, dtype=str, keep_default_na=False, encoding="latin-1")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse CSV: {exc}") from exc

    df = df.fillna("").astype(str)

    chunks: list[Chunk] = []
    chunk_facts: dict[str, dict] = {}
    char_cursor = 0

    for row_index, (_, row) in enumerate(df.iterrows()):
        row_dict = row.to_dict()
        text = _row_to_text(row_dict)
        if not text.strip():
            continue

        chunk_id = f"{doc_id}-{row_index}"
        facts = _extract_row_facts(row_dict)

        chunks.append(
            Chunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=row_index,
                text=text,
                char_start=char_cursor,
                char_end=char_cursor + len(text),
            )
        )
        chunk_facts[chunk_id] = {
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "page_number": row_index,
            "source_type": "csv",
            "filename": sanitized,
            "facts": facts,
        }
        char_cursor += len(text) + 1  # +1 for the newline between chunks

    chunk_embeddings = embeddings.embed_chunks(doc_id, chunks)
    total_chars = sum(len(c.text) for c in chunks)

    document = Document(
        id=doc_id,
        filename=sanitized,
        content_type="text/csv",
        size_bytes=len(raw),
        text_char_count=total_chars,
        status="extracted" if chunks else "empty",
        storage_path=str(dest),
        created_at=datetime.now(timezone.utc).isoformat(),
        chunk_count=len(chunks),
    )

    _progress(
        f"CSV ingestion '{sanitized}': parsed {len(chunks)} row-chunk(s), "
        f"embedding + persisting…"
    )

    if config.use_postgres():
        _persist_postgres_bulk(document, chunks, chunk_embeddings)
    else:
        chunking.save_chunks(doc_id, chunks)
        embeddings.save_embeddings(doc_id, chunk_embeddings)
        _save_chunk_facts(chunk_facts)
        _append_metadata(document)

    _progress(f"CSV ingestion '{sanitized}' complete: {len(chunks)} chunk(s).")
    return document


# ── XLSX ingestion ────────────────────────────────────────────────────────────

async def ingest_xlsx(upload: UploadFile) -> Document:
    """Ingest an XLSX file — each row across all sheets becomes one chunk.

    Multiple sheets are supported: the sheet name is prepended to each chunk's
    text so search results carry sheet provenance. Facts are extracted from
    column names using the same fuzzy mapping as CSV ingestion.
    """
    import pandas as pd

    sanitized = _sanitize_filename(upload.filename)
    raw = await upload.read()

    doc_id = uuid.uuid4().hex
    storage_dir = _storage_dir()
    dest = storage_dir / f"{doc_id}_{sanitized}"

    if storage_dir.resolve() not in dest.resolve().parents:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    dest.write_bytes(raw)

    try:
        # sheet_name=None reads all sheets; returns {sheet_name: DataFrame}
        sheet_map: dict = pd.read_excel(
            dest, sheet_name=None, dtype=str, keep_default_na=False, engine="openpyxl"
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse XLSX: {exc}") from exc

    chunks: list[Chunk] = []
    chunk_facts: dict[str, dict] = {}
    char_cursor = 0
    global_index = 0

    for sheet_name, df in sheet_map.items():
        df = df.fillna("").astype(str)

        for row_index, (_, row) in enumerate(df.iterrows()):
            row_dict = row.to_dict()
            text = _row_to_text(row_dict, sheet_name=str(sheet_name))
            if not text.strip():
                continue

            chunk_id = f"{doc_id}-{global_index}"
            facts = _extract_row_facts(row_dict)

            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=doc_id,
                    chunk_index=global_index,
                    text=text,
                    char_start=char_cursor,
                    char_end=char_cursor + len(text),
                )
            )
            chunk_facts[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "page_number": row_index,
                "sheet_name": str(sheet_name),
                "source_type": "xlsx",
                "filename": sanitized,
                "facts": facts,
            }
            char_cursor += len(text) + 1
            global_index += 1

    chunk_embeddings = embeddings.embed_chunks(doc_id, chunks)
    total_chars = sum(len(c.text) for c in chunks)

    document = Document(
        id=doc_id,
        filename=sanitized,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size_bytes=len(raw),
        text_char_count=total_chars,
        status="extracted" if chunks else "empty",
        storage_path=str(dest),
        created_at=datetime.now(timezone.utc).isoformat(),
        chunk_count=len(chunks),
    )

    _progress(
        f"XLSX ingestion '{sanitized}': parsed {len(chunks)} row-chunk(s), "
        f"embedding + persisting…"
    )

    if config.use_postgres():
        _persist_postgres_bulk(document, chunks, chunk_embeddings)
    else:
        chunking.save_chunks(doc_id, chunks)
        embeddings.save_embeddings(doc_id, chunk_embeddings)
        _save_chunk_facts(chunk_facts)
        _append_metadata(document)

    _progress(f"XLSX ingestion '{sanitized}' complete: {len(chunks)} chunk(s).")
    return document


# ── main upload entry point ───────────────────────────────────────────────────

async def ingest_upload(upload: UploadFile) -> Document:
    """Save an uploaded file, extract its text/rows, and record metadata.

    Routes CSV and XLSX to dedicated ingestors; PDF and plain text go through
    the character-based chunking pipeline.
    """
    sanitized = _sanitize_filename(upload.filename)
    ext, _content_type = _resolve_type(sanitized, upload.content_type)

    # Tabular formats — row-per-chunk ingestors handle saving + parsing.
    if ext == ".csv":
        return await ingest_csv(upload)
    if ext == ".xlsx":
        return await ingest_xlsx(upload)

    # PDF and plain text — character-based chunking pipeline.
    raw = await upload.read()

    doc_id = uuid.uuid4().hex
    storage_dir = _storage_dir()
    dest = storage_dir / f"{doc_id}_{sanitized}"

    if storage_dir.resolve() not in dest.resolve().parents:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    dest.write_bytes(raw)

    text = _extract_text(dest, ext)
    char_count = len(text)
    source_type = ext.lstrip(".")

    chunks = chunking.chunk_text(doc_id, text)
    chunk_embeddings = embeddings.embed_chunks(doc_id, chunks)

    # Extract structured facts from each chunk's text and record page numbers
    # derived from the [Page N] markers embedded by _extract_text for PDFs.
    from app.services import fact_extraction

    chunk_facts: dict[str, dict] = {}
    for chunk in chunks:
        facts = fact_extraction.extract_facts_from_text(chunk.text)
        page_number = fact_extraction.page_number_from_text(chunk.text)
        chunk_facts[chunk.id] = {
            "chunk_id": chunk.id,
            "document_id": doc_id,
            "page_number": page_number,
            "source_type": source_type,
            "filename": sanitized,
            "facts": facts,
        }

    document = Document(
        id=doc_id,
        filename=sanitized,
        content_type=_content_type,
        size_bytes=len(raw),
        text_char_count=char_count,
        status="extracted" if char_count > 0 else "empty",
        storage_path=str(dest),
        created_at=datetime.now(timezone.utc).isoformat(),
        chunk_count=len(chunks),
    )

    if config.use_postgres():
        _persist_postgres(document, chunks, chunk_embeddings)
    else:
        chunking.save_chunks(doc_id, chunks)
        embeddings.save_embeddings(doc_id, chunk_embeddings)
        _save_chunk_facts(chunk_facts)
        _append_metadata(document)
    return document


# ── document listing ──────────────────────────────────────────────────────────

def list_documents() -> list[Document]:
    """Return all documents from the active persistence backend."""
    if config.use_postgres():
        from app.db import repository as repo

        return [_document_from_record(record) for record in repo.list_documents()]
    return [Document(**record) for record in _load_metadata()]
