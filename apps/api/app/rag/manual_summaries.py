"""Load externally generated parent summaries for RAG ingestion."""

from __future__ import annotations

import json
from pathlib import Path

from app.rag.schemas import ParentChunkSummary


def load_parent_summaries(path: str | Path) -> dict[str, ParentChunkSummary]:
    """Load manual parent summaries keyed by parent_chunk_id from a JSONL file."""

    summary_path = Path(path).expanduser()
    if not summary_path.exists():
        raise FileNotFoundError(f"Parent summaries file does not exist: {summary_path}")
    if not summary_path.is_file():
        raise ValueError(f"Parent summaries path is not a file: {summary_path}")

    summaries: dict[str, ParentChunkSummary] = {}
    with summary_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in parent summaries file at line {line_number}: {exc}"
                ) from exc

            parent_chunk_id = str(payload.get("parent_chunk_id") or "").strip()
            if not parent_chunk_id:
                raise ValueError(
                    f"Missing parent_chunk_id in parent summaries file at line {line_number}"
                )
            if parent_chunk_id in summaries:
                raise ValueError(
                    f"Duplicate parent_chunk_id in parent summaries file at line {line_number}: "
                    f"{parent_chunk_id}"
                )

            summary_text = str(payload.get("summary_text") or "").strip()
            if not summary_text:
                raise ValueError(
                    f"Missing summary_text for {parent_chunk_id} at line {line_number}"
                )

            metadata = dict(payload.get("metadata") or {})
            summaries[parent_chunk_id] = ParentChunkSummary(
                parent_chunk_id=parent_chunk_id,
                summary_text=summary_text,
                answerable_questions=_clean_strings(metadata.get("answerable_questions") or []),
                asset_tags=_clean_strings(metadata.get("asset_tags") or []),
                summary_strategy="manual_parent_llm",
                metadata={
                    **metadata,
                    "summary_model": metadata.get("summary_model") or "chatgpt-5.5",
                    "summary_strategy": "manual_parent_llm",
                    "source": "manual_parent_summaries_jsonl",
                },
            )
    return summaries


def _clean_strings(values: list[object]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned
