"""Normalized document element extraction for RAG sources."""

from __future__ import annotations

import csv
import contextlib
import hashlib
import io
import re
import shutil
from pathlib import Path

from app.core.config import settings
from app.rag.schemas import DocumentElement, ElementType, SourceType
from app.services.entity_extraction import extract_equipment_tags

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".csv"} | IMAGE_EXTENSIONS
_LIST_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
_API_ROOT = Path(__file__).resolve().parents[2]
_MIN_VECTOR_VISUAL_AREA = 5000
_MIN_VECTOR_VISUAL_SIZE = 40


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
    if ext in IMAGE_EXTENSIONS:
        return _extract_image(path, resolved_document_id)
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
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "unknown"


def _asset_tags(text: str) -> list[str]:
    return [tag.normalized_value for tag in extract_equipment_tags(text)]


def _element_id(document_id: str, kind: str, index: int) -> str:
    return f"{document_id}:element:{kind}:{index}"


def _visual_storage_root() -> Path:
    configured = Path(settings.rag_visual_storage_dir).expanduser()
    if configured.is_absolute():
        return configured
    return (_API_ROOT / configured).resolve()


def _visual_output_dir(document_id: str) -> Path:
    output_dir = _visual_storage_root() / document_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


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
            page_number = page_index + 1
            text = page.get_text("text").strip()
            if text:
                elements.extend(
                    _paragraph_elements(
                        document_id=document_id,
                        path=path,
                        text=text,
                        source_type="pdf",
                        start_index=len(elements),
                        page_number=page_number,
                    )
                )
            elements.extend(
                _extract_pdf_visual_elements(
                    document=document,
                    page=page,
                    path=path,
                    document_id=document_id,
                    page_number=page_number,
                    start_index=len(elements),
                )
            )
    return elements


def _extract_pdf_visual_elements(
    *,
    document: object,
    page: object,
    path: Path,
    document_id: str,
    page_number: int,
    start_index: int,
) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    elements.extend(
        _extract_embedded_pdf_images(
            document=document,
            page=page,
            path=path,
            document_id=document_id,
            page_number=page_number,
            start_index=start_index + len(elements),
        )
    )
    elements.extend(
        _extract_pdf_table_visuals(
            page=page,
            path=path,
            document_id=document_id,
            page_number=page_number,
            start_index=start_index + len(elements),
        )
    )
    elements.extend(
        _extract_pdf_vector_visuals(
            page=page,
            path=path,
            document_id=document_id,
            page_number=page_number,
            start_index=start_index + len(elements),
        )
    )
    return elements


def _extract_embedded_pdf_images(
    *,
    document: object,
    page: object,
    path: Path,
    document_id: str,
    page_number: int,
    start_index: int,
) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    for image_index, image in enumerate(page.get_images(full=True), start=1):
        xref = image[0]
        extracted = document.extract_image(xref)
        image_bytes = extracted.get("image")
        if not image_bytes:
            continue
        extension = str(extracted.get("ext") or "png").lower()
        mime_type = _mime_type_for_extension(extension)
        rects = page.get_image_rects(xref) or [None]
        for rect_index, rect in enumerate(rects, start=1):
            visual_path = _write_visual_file(
                document_id,
                f"page_{page_number:04d}_image_{image_index}_{rect_index}.{extension}",
                image_bytes,
            )
            text = (
                f"Embedded image extracted from {path.name} page {page_number}; "
                f"visual_path={visual_path}"
            )
            elements.append(
                DocumentElement(
                    element_id=_element_id(
                        document_id,
                        "image",
                        start_index + len(elements),
                    ),
                    document_id=document_id,
                    element_type="image",
                    text=text,
                    source_type="pdf",
                    file_name=path.name,
                    source_path=str(path),
                    page_number=page_number,
                    bbox=_rect_to_dict(rect),
                    asset_tags=_asset_tags(text),
                    modality="image",
                    metadata={
                        "extension": ".pdf",
                        "visual_path": str(visual_path),
                        "mime_type": mime_type,
                        "visual_kind": "embedded_image",
                        "extraction_method": "pymupdf_extract_image",
                        "xref": xref,
                        "width": extracted.get("width"),
                        "height": extracted.get("height"),
                    },
                )
            )
    return elements


def _extract_pdf_table_visuals(
    *,
    page: object,
    path: Path,
    document_id: str,
    page_number: int,
    start_index: int,
) -> list[DocumentElement]:
    find_tables = getattr(page, "find_tables", None)
    if not callable(find_tables):
        return []

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            tables = list(find_tables().tables)
    except Exception:
        return []

    elements: list[DocumentElement] = []
    for table_index, table in enumerate(tables, start=1):
        rect = getattr(table, "bbox", None)
        if not _is_significant_rect(rect):
            continue
        visual_path = _render_page_clip(
            page,
            rect,
            document_id,
            f"page_{page_number:04d}_table_{table_index}.png",
        )
        table_text = _table_text(table)
        text = (
            f"Table visual extracted from {path.name} page {page_number}; "
            f"visual_path={visual_path}"
        )
        if table_text:
            text = f"{text}\nExtracted table text:\n{table_text}"
        elements.append(
            DocumentElement(
                element_id=_element_id(
                    document_id,
                    "table_block",
                    start_index + len(elements),
                ),
                document_id=document_id,
                element_type="table_block",
                text=text,
                source_type="pdf",
                file_name=path.name,
                source_path=str(path),
                page_number=page_number,
                bbox=_rect_to_dict(rect),
                asset_tags=_asset_tags(text),
                modality="table",
                metadata={
                    "extension": ".pdf",
                    "visual_path": str(visual_path),
                    "mime_type": "image/png",
                    "visual_kind": "table_region",
                    "extraction_method": "pymupdf_find_tables",
                    "table_index": table_index,
                    "table_text": table_text,
                },
            )
        )
    return elements


def _extract_pdf_vector_visuals(
    *,
    page: object,
    path: Path,
    document_id: str,
    page_number: int,
    start_index: int,
) -> list[DocumentElement]:
    try:
        rects = [
            drawing.get("rect")
            for drawing in page.get_drawings()
            if _is_significant_rect(drawing.get("rect"))
        ]
    except Exception:
        return []

    if not rects:
        return []

    union = _union_rects(rects)
    if not _is_significant_rect(union):
        return []

    visual_path = _render_page_clip(
        page,
        union,
        document_id,
        f"page_{page_number:04d}_vector_visual_1.png",
    )
    text = (
        f"Vector visual region extracted from {path.name} page {page_number}; "
        f"visual_path={visual_path}"
    )
    return [
        DocumentElement(
            element_id=_element_id(document_id, "image", start_index),
            document_id=document_id,
            element_type="image",
            text=text,
            source_type="pdf",
            file_name=path.name,
            source_path=str(path),
            page_number=page_number,
            bbox=_rect_to_dict(union),
            asset_tags=_asset_tags(text),
            modality="image",
            metadata={
                "extension": ".pdf",
                "visual_path": str(visual_path),
                "mime_type": "image/png",
                "visual_kind": "vector_region",
                "extraction_method": "pymupdf_drawings_clip",
                "drawing_region_count": len(rects),
            },
        )
    ]


def _write_visual_file(document_id: str, file_name: str, data: bytes) -> Path:
    output_path = _visual_output_dir(document_id) / file_name
    output_path.write_bytes(data)
    return output_path


def _copy_visual_file(document_id: str, path: Path, file_name: str) -> Path:
    output_path = _visual_output_dir(document_id) / file_name
    shutil.copyfile(path, output_path)
    return output_path


def _render_page_clip(page: object, rect: object, document_id: str, file_name: str) -> Path:
    import fitz

    output_path = _visual_output_dir(document_id) / file_name
    clip = fitz.Rect(rect)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
    pixmap.save(str(output_path))
    return output_path


def _table_text(table: object) -> str:
    extract = getattr(table, "extract", None)
    if not callable(extract):
        return ""
    try:
        rows = extract()
    except Exception:
        return ""
    lines: list[str] = []
    for row in rows or []:
        values = [str(value).strip() for value in row if value is not None and str(value).strip()]
        if values:
            lines.append(" | ".join(values))
    return "\n".join(lines)


def _is_significant_rect(rect: object) -> bool:
    if rect is None:
        return False
    width = float(getattr(rect, "width", 0.0) or 0.0)
    height = float(getattr(rect, "height", 0.0) or 0.0)
    area = width * height
    return (
        width >= _MIN_VECTOR_VISUAL_SIZE
        and height >= _MIN_VECTOR_VISUAL_SIZE
        and area >= _MIN_VECTOR_VISUAL_AREA
    )


def _rect_to_dict(rect: object) -> dict | None:
    if rect is None:
        return None
    return {
        "x0": float(getattr(rect, "x0", 0.0)),
        "y0": float(getattr(rect, "y0", 0.0)),
        "x1": float(getattr(rect, "x1", 0.0)),
        "y1": float(getattr(rect, "y1", 0.0)),
    }


def _union_rects(rects: list[object]) -> object:
    import fitz

    union = fitz.Rect(rects[0])
    for rect in rects[1:]:
        union.include_rect(fitz.Rect(rect))
    return union


def _mime_type_for_extension(extension: str) -> str:
    normalized = extension.lower().lstrip(".")
    if normalized in {"jpg", "jpeg"}:
        return "image/jpeg"
    if normalized == "png":
        return "image/png"
    if normalized == "webp":
        return "image/webp"
    if normalized in {"tif", "tiff"}:
        return "image/tiff"
    return f"image/{normalized or 'png'}"


def _extract_image(path: Path, document_id: str) -> list[DocumentElement]:
    extension = path.suffix.lower()
    mime_type = _mime_type_for_extension(extension)
    visual_path = _copy_visual_file(
        document_id,
        path,
        f"image_0001{extension}",
    )
    text = f"Direct image file {path.name}; visual_path={visual_path}"
    return [
        DocumentElement(
            element_id=_element_id(document_id, "image", 0),
            document_id=document_id,
            element_type="image",
            text=text,
            source_type="image",
            file_name=path.name,
            source_path=str(path),
            asset_tags=_asset_tags(path.stem),
            modality="image",
            metadata={
                "extension": extension,
                "visual_path": str(visual_path),
                "original_visual_path": str(path),
                "mime_type": mime_type,
                "visual_kind": "direct_image",
                "extraction_method": "direct_image_file",
            },
        )
    ]


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


def _csv_cell_text(key: str, value: str) -> str:
    cleaned = value.strip()
    suffix = "" if cleaned.endswith((".", "!", "?", ";", ":")) else "."
    return f"'{key}': {cleaned}{suffix}"


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
                text = " ".join(
                    _csv_cell_text(key, value or "")
                    for key, value in row.items()
                    if key and (value or "").strip()
                ).strip()
                if not text:
                    continue
                tags = _asset_tags(text)
                elements.append(
                    DocumentElement(
                        element_id=_element_id(document_id, "csv_row", len(elements)),
                        document_id=document_id,
                        element_type="paragraph",
                        text=text,
                        source_type="csv",
                        file_name=path.name,
                        source_path=str(path),
                        row_index=row_index,
                        asset_tags=tags,
                        modality="text",
                        metadata={
                            "extension": ".csv",
                            "columns": reader.fieldnames,
                            "row": row,
                            "csv_row_text_format": "quoted_column_labels",
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
                    element_id=_element_id(document_id, "csv_row", len(elements)),
                    document_id=document_id,
                    element_type="paragraph",
                    text=text,
                    source_type="csv",
                    file_name=path.name,
                    source_path=str(path),
                    row_index=row_index,
                    asset_tags=_asset_tags(text),
                    modality="text",
                    metadata={"extension": ".csv", "csv_row_text_format": "plain_row"},
                )
            )
    return elements
