"""Layout-aware parent chunk building from normalized document elements."""

from __future__ import annotations

from collections import Counter

from app.rag.schemas import (
    AtomicElementSummary,
    DocumentElement,
    ParentChunk,
    VisualElementEvidence,
)

PARENT_TARGET_CHARS = 9000
OVERSIZED_ELEMENT_CHARS = 11000
CSV_ROWS_PER_PARENT = 1


def build_parent_chunks(
    document_id: str,
    elements: list[DocumentElement],
    *,
    target_chars: int = PARENT_TARGET_CHARS,
    csv_rows_per_parent: int = CSV_ROWS_PER_PARENT,
) -> list[ParentChunk]:
    """Group neighboring related elements into raw parent chunks."""

    chunks: list[ParentChunk] = []
    current: list[DocumentElement] = []
    current_key: tuple | None = None

    def flush() -> None:
        nonlocal current, current_key
        if not current:
            return
        chunks.extend(_parent_chunks_from_group(document_id, current, len(chunks)))
        current = []
        current_key = None

    for element in elements:
        for atomic in _split_oversized_element(element):
            key = _group_key(atomic)
            if current and (key != current_key or _should_flush(current, atomic, target_chars, csv_rows_per_parent)):
                flush()
            current.append(atomic)
            current_key = key

    flush()
    return chunks


# Backward-compatible name from the first RAG slice.
def chunk_units(document_id: str, units: list[DocumentElement], **_: object) -> list[ParentChunk]:
    return build_parent_chunks(document_id, units)


def _group_key(element: DocumentElement) -> tuple:
    if element.source_type == "csv":
        return ("csv", element.file_name)
    if element.source_type in {"txt", "md"}:
        return (element.source_type, element.file_name, element.section_title)
    if element.source_type == "pdf":
        return (element.source_type, element.file_name, element.page_number)
    return (element.source_type, element.file_name, element.page_number, element.section_title)


def _should_flush(
    current: list[DocumentElement],
    next_element: DocumentElement,
    target_chars: int,
    csv_rows_per_parent: int,
) -> bool:
    if next_element.source_type == "csv":
        csv_rows = sum(1 for element in current if element.row_index is not None)
        return csv_rows >= csv_rows_per_parent
    current_length = sum(len(element.text) + 2 for element in current)
    return current_length + len(next_element.text) > target_chars


def _split_oversized_element(element: DocumentElement) -> list[DocumentElement]:
    if len(element.text) <= OVERSIZED_ELEMENT_CHARS:
        return [element]

    parts: list[DocumentElement] = []
    start = 0
    index = 0
    while start < len(element.text):
        end = min(start + OVERSIZED_ELEMENT_CHARS, len(element.text))
        part = element.model_copy(
            update={
                "element_id": f"{element.element_id}:part:{index}",
                "text": element.text[start:end].strip(),
                "metadata": {
                    **element.metadata,
                    "split_from_element_id": element.element_id,
                    "split_part_index": index,
                },
            }
        )
        if part.text:
            parts.append(part)
        if end == len(element.text):
            break
        start = end
        index += 1
    return parts


def _parent_chunks_from_group(
    document_id: str,
    elements: list[DocumentElement],
    start_index: int,
) -> list[ParentChunk]:
    if not elements:
        return []

    chunk_index = start_index
    raw_text = _raw_text(elements)
    source_types = {element.source_type for element in elements}
    modalities = [element.modality for element in elements]
    source_type = elements[0].source_type if len(source_types) == 1 else "unknown"
    modality = Counter(modalities).most_common(1)[0][0] if modalities else "text"
    pages = [element.page_number for element in elements if element.page_number is not None]
    rows = [element.row_index for element in elements if element.row_index is not None]
    section_title = next((element.section_title for element in elements if element.section_title), None)
    asset_tags = sorted({tag for element in elements for tag in element.asset_tags})
    element_summaries = _element_summaries(elements)
    visual_elements = _visual_elements(elements)
    parent_chunk_id = f"{document_id}:parent:{chunk_index}"

    return [
        ParentChunk(
            document_id=document_id,
            parent_chunk_id=parent_chunk_id,
            chunk_index=chunk_index,
            raw_text=raw_text,
            source_file=elements[0].file_name,
            source_path=elements[0].source_path,
            source_type=source_type,
            page_start=min(pages) if pages else None,
            page_end=max(pages) if pages else None,
            row_start=min(rows) if rows else None,
            row_end=max(rows) if rows else None,
            section_title=section_title,
            element_ids=[element.element_id for element in elements],
            asset_tags=asset_tags,
            modality=modality,
            element_summaries=element_summaries,
            visual_elements=visual_elements,
            metadata={
                "element_count": len(elements),
                "element_types": sorted({element.element_type for element in elements}),
                "strategy": "layout_parent_chunk_v1",
                "text_evidence": _text_evidence(elements),
                "visual_element_ids": [element.element_id for element in visual_elements],
                "elements": [
                    {
                        "element_id": element.element_id,
                        "element_type": element.element_type,
                        "page_number": element.page_number,
                        "row_index": element.row_index,
                        "section_title": element.section_title,
                    }
                    for element in elements
                ],
            },
        )
    ]


def _raw_text(elements: list[DocumentElement]) -> str:
    lines: list[str] = []
    for element in elements:
        if element.element_type == "heading":
            lines.append(element.text)
        elif _is_visual_element(element):
            lines.append(
                f"{element.element_type} original evidence for {element.element_id}: "
                f"{element.text}"
            )
        elif element.source_type == "csv" and element.row_index is not None:
            lines.append(f"Row {element.row_index}: {element.text}")
        elif element.element_type == "list_item":
            lines.append(element.text)
        else:
            lines.append(element.text)
    return "\n".join(line.strip() for line in lines if line.strip())


def _text_evidence(elements: list[DocumentElement]) -> str:
    lines: list[str] = []
    for element in elements:
        if _is_visual_element(element) and element.element_summary:
            continue
        if element.element_type == "heading":
            lines.append(element.text)
        elif element.source_type == "csv" and element.row_index is not None:
            lines.append(f"Row {element.row_index}: {element.text}")
        elif not _is_visual_element(element):
            lines.append(element.text)
    return "\n".join(line.strip() for line in lines if line.strip())


def _element_summaries(elements: list[DocumentElement]) -> list[AtomicElementSummary]:
    summaries: list[AtomicElementSummary] = []
    for element in elements:
        raw_summary = element.metadata.get("atomic_summary")
        if raw_summary:
            summaries.append(AtomicElementSummary(**raw_summary))
        elif element.element_summary:
            summaries.append(
                AtomicElementSummary(
                    element_id=element.element_id,
                    element_type=element.element_type,
                    summary_text=element.element_summary,
                    summary_strategy=element.summary_strategy or "passthrough",
                    asset_tags=element.asset_tags,
                    metadata={"questions_generated": False},
                )
            )
    return summaries


def _visual_elements(elements: list[DocumentElement]) -> list[VisualElementEvidence]:
    visual_elements: list[VisualElementEvidence] = []
    for element in elements:
        if not _is_visual_element(element):
            continue
        visual_elements.append(
            VisualElementEvidence(
                element_id=element.element_id,
                element_type=element.element_type,
                text=element.text,
                source_type=element.source_type,
                file_name=element.file_name,
                source_path=element.source_path,
                page_number=element.page_number,
                row_index=element.row_index,
                section_title=element.section_title,
                bbox=element.bbox,
                asset_tags=element.asset_tags,
                modality=element.modality,
                metadata=element.metadata,
            )
        )
    return visual_elements


def _is_visual_element(element: DocumentElement) -> bool:
    if element.source_type in {"csv", "md"}:
        return False
    return (
        element.modality in {"image", "ocr", "table"}
        or element.element_type in {"table_row", "table_block", "image_caption", "ocr_text"}
    )
