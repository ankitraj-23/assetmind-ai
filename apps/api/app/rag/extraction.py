"""Normalized document element extraction for RAG sources."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

from app.rag.schemas import DocumentElement, ElementType, SourceType
from app.services.entity_extraction import extract_equipment_tags

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".csv"}
_LIST_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")


class UnsupportedFileTypeError(ValueError):
    """Raised when a dataset file has an unsupported extension."""


def extract_file(path: Path, document_id: str | None = None) -> list[DocumentElement]:
    """Extract normalized elements from a supported dataset file."""

    path = path.resolve()
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(f"Unsupported file type: {path.name}")

    resolved_document_id = document_id or _document_id_for_path(path)
    if ext == ".pdf":
        return _extract_pdf(path, resolved_document_id)
    if ext == ".csv":
        return _extract_csv(path, resolved_document_id)
    return _extract_text_or_markdown(path, resolved_document_id)


def _document_id_for_path(path: Path) -> str:
    digest = hashlib.sha1(str(path.resolve()).lower().encode("utf-8")).hexdigest()
    return f"rag-{digest[:20]}"


def _source_type(path: Path) -> SourceType:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".csv":
        return "csv"
    if ext == ".txt":
        return "txt"
    if ext in {".md", ".markdown"}:
        return "md"
    return "unknown"


def _asset_tags(text: str) -> list[str]:
    return [tag.normalized_value for tag in extract_equipment_tags(text)]


def _element_id(document_id: str, kind: str, index: int) -> str:
    return f"{document_id}:element:{kind}:{index}"


def _looks_like_heading(line: str) -> bool:
    text = line.strip().strip("#").strip()
    if not text or len(text) > 90:
        return False
    if text.endswith(":"):
        return True
    if text.isupper() and any(char.isalpha() for char in text):
        return True
    heading_words = {
        "procedure",
        "scope",
        "startup",
        "shutdown",
        "inspection",
        "checklist",
        "manual",
        "requirements",
        "findings",
        "limits",
        "maintenance",
    }
    lowered = text.lower()
    return any(word in lowered for word in heading_words) and len(text.split()) <= 10


def _paragraph_elements(
    *,
    document_id: str,
    path: Path,
    text: str,
    source_type: SourceType,
    start_index: int = 0,
    page_number: int | None = None,
) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    section_title: str | None = None
    current: list[str] = []
    current_type: ElementType = "paragraph"

    def flush() -> None:
        nonlocal current, current_type
        if not current:
            return
        body = "\n".join(current).strip()
        if body:
            elements.append(
                DocumentElement(
                    element_id=_element_id(
                        document_id,
                        current_type,
                        start_index + len(elements),
                    ),
                    document_id=document_id,
                    element_type=current_type,
                    text=body,
                    source_type=source_type,
                    file_name=path.name,
                    source_path=str(path),
                    page_number=page_number,
                    section_title=section_title,
                    asset_tags=_asset_tags(body),
                    modality="text",
                    metadata={"extension": path.suffix.lower()},
                )
            )
        current = []
        current_type = "paragraph"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line.startswith("#"):
            flush()
            section_title = line.lstrip("#").strip()
            elements.append(
                DocumentElement(
                    element_id=_element_id(
                        document_id,
                        "heading",
                        start_index + len(elements),
                    ),
                    document_id=document_id,
                    element_type="heading",
                    text=section_title,
                    source_type=source_type,
                    file_name=path.name,
                    source_path=str(path),
                    page_number=page_number,
                    section_title=section_title,
                    asset_tags=_asset_tags(section_title),
                    modality="text",
                    metadata={"extension": path.suffix.lower()},
                )
            )
            continue
        if _looks_like_heading(line):
            flush()
            section_title = line.rstrip(":")
            elements.append(
                DocumentElement(
                    element_id=_element_id(
                        document_id,
                        "heading",
                        start_index + len(elements),
                    ),
                    document_id=document_id,
                    element_type="heading",
                    text=section_title,
                    source_type=source_type,
                    file_name=path.name,
                    source_path=str(path),
                    page_number=page_number,
                    section_title=section_title,
                    asset_tags=_asset_tags(section_title),
                    modality="text",
                    metadata={"extension": path.suffix.lower()},
                )
            )
            continue
        line_type: ElementType = "list_item" if _LIST_RE.match(line) else "paragraph"
        if current and line_type != current_type:
            flush()
        current_type = line_type
        current.append(line)

    flush()
    return elements


def _extract_pdf(path: Path, document_id: str) -> list[DocumentElement]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to extract PDF documents.") from exc

    elements: list[DocumentElement] = []
    with fitz.open(path) as document:
        for page_index, page in enumerate(document):
            text = page.get_text("text").strip()
            if not text:
                continue
            elements.extend(
                _paragraph_elements(
                    document_id=document_id,
                    path=path,
                    text=text,
                    source_type="pdf",
                    start_index=len(elements),
                    page_number=page_index + 1,
                )
            )
    return elements


def _extract_text_or_markdown(path: Path, document_id: str) -> list[DocumentElement]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    return _paragraph_elements(
        document_id=document_id,
        path=path,
        text=text,
        source_type=_source_type(path),
    )


def _extract_csv(path: Path, document_id: str) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(handle, dialect=dialect)
        if reader.fieldnames:
            for row_index, row in enumerate(reader, start=1):
                text = " | ".join(
                    f"{key}: {(value or '').strip()}"
                    for key, value in row.items()
                    if key and (value or "").strip()
                ).strip()
                if not text:
                    continue
                tags = _asset_tags(text)
                elements.append(
                    DocumentElement(
                        element_id=_element_id(document_id, "table_row", len(elements)),
                        document_id=document_id,
                        element_type="table_row",
                        text=text,
                        source_type="csv",
                        file_name=path.name,
                        source_path=str(path),
                        row_index=row_index,
                        asset_tags=tags,
                        modality="table",
                        metadata={
                            "extension": ".csv",
                            "columns": reader.fieldnames,
                            "row": row,
                        },
                    )
                )
            return elements

        handle.seek(0)
        plain_reader = csv.reader(handle, dialect=dialect)
        for row_index, row in enumerate(plain_reader, start=1):
            text = " | ".join(value.strip() for value in row if value.strip())
            if not text:
                continue
            elements.append(
                DocumentElement(
                    element_id=_element_id(document_id, "table_row", len(elements)),
                    document_id=document_id,
                    element_type="table_row",
                    text=text,
                    source_type="csv",
                    file_name=path.name,
                    source_path=str(path),
                    row_index=row_index,
                    asset_tags=_asset_tags(text),
                    modality="table",
                    metadata={"extension": ".csv"},
                )
            )
    return elements
