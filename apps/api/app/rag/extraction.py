"""Dataset document extraction for PDF, text, Markdown, and CSV files."""

from __future__ import annotations

import csv
from pathlib import Path

from app.rag.schemas import ExtractedTextUnit

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".csv"}
CSV_UNIT_TARGET_CHARS = 3200


class UnsupportedFileTypeError(ValueError):
    """Raised when a dataset file has an unsupported extension."""


def extract_file(path: Path) -> list[ExtractedTextUnit]:
    """Extract page/row-aware text units from a supported dataset file."""

    path = path.resolve()
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(f"Unsupported file type: {path.name}")

    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".csv":
        return _extract_csv(path)
    return _extract_plain_text(path)


def _extract_pdf(path: Path) -> list[ExtractedTextUnit]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to extract PDF documents.") from exc

    units: list[ExtractedTextUnit] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document):
            text = page.get_text("text").strip()
            if not text:
                continue
            units.append(
                ExtractedTextUnit(
                    file_name=path.name,
                    source_path=str(path),
                    unit_index=index,
                    page_number=index + 1,
                    text=text,
                    metadata={"extension": ".pdf"},
                )
            )
    return units


def _extract_plain_text(path: Path) -> list[ExtractedTextUnit]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    return [
        ExtractedTextUnit(
            file_name=path.name,
            source_path=str(path),
            unit_index=0,
            page_number=1,
            text=text,
            metadata={"extension": path.suffix.lower()},
        )
    ]


def _extract_csv(path: Path) -> list[ExtractedTextUnit]:
    units: list[ExtractedTextUnit] = []
    rows: list[tuple[int, str, dict]] = []
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
                rows.append(
                    (
                        row_index,
                        text,
                        {"extension": ".csv", "headers": reader.fieldnames},
                    )
                )
            return _batch_csv_rows(path, rows)

        handle.seek(0)
        plain_reader = csv.reader(handle, dialect=dialect)
        for row_index, row in enumerate(plain_reader, start=1):
            text = " | ".join(value.strip() for value in row if value.strip())
            if not text:
                continue
            rows.append((row_index, text, {"extension": ".csv"}))
    return _batch_csv_rows(path, rows)


def _batch_csv_rows(
    path: Path,
    rows: list[tuple[int, str, dict]],
    *,
    target_chars: int = CSV_UNIT_TARGET_CHARS,
) -> list[ExtractedTextUnit]:
    """Group consecutive CSV rows into extract units while preserving row ranges."""

    units: list[ExtractedTextUnit] = []
    current: list[str] = []
    row_start: int | None = None
    row_end: int | None = None
    metadata: dict = {"extension": ".csv"}

    def flush() -> None:
        nonlocal current, row_start, row_end, metadata
        if not current or row_start is None or row_end is None:
            return
        units.append(
            ExtractedTextUnit(
                file_name=path.name,
                source_path=str(path),
                unit_index=len(units),
                row_number=row_start,
                text="\n".join(current),
                metadata={
                    **metadata,
                    "row_start": row_start,
                    "row_end": row_end,
                },
            )
        )
        current = []
        row_start = None
        row_end = None
        metadata = {"extension": ".csv"}

    for row_number, row_text, row_metadata in rows:
        proposed_length = sum(len(line) + 1 for line in current) + len(row_text)
        if current and proposed_length > target_chars:
            flush()

        if row_start is None:
            row_start = row_number
        row_end = row_number
        metadata = {**metadata, **row_metadata}
        current.append(f"Row {row_number}: {row_text}")

    flush()
    return units
