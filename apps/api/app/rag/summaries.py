"""Retrieval summary generation for parent-child RAG."""

from __future__ import annotations

from app.core.config import settings
from app.rag.schemas import ParentChunk, RetrievalUnit

SUMMARY_MODEL_FALLBACK = "gemini-3.5-flash"


def build_retrieval_unit(parent: ParentChunk) -> RetrievalUnit:
    """Create one summary-indexed retrieval unit for a raw parent chunk."""

    if parent.source_type == "csv" or parent.modality == "table":
        summary_text = template_summary(parent)
        strategy = "template"
    else:
        summary_text, strategy = llm_summary_or_fallback(parent)

    return RetrievalUnit(
        retrieval_unit_id=f"{parent.parent_chunk_id}:summary:0",
        parent_chunk_id=parent.parent_chunk_id,
        document_id=parent.document_id,
        summary_text=summary_text,
        asset_tags=parent.asset_tags,
        modality=parent.modality,
        source_file=parent.source_file,
        source_path=parent.source_path,
        source_type=parent.source_type,
        page_start=parent.page_start,
        page_end=parent.page_end,
        row_start=parent.row_start,
        row_end=parent.row_end,
        section_title=parent.section_title,
        summary_strategy=strategy,
        metadata={"strategy_version": "retrieval_summary_v1"},
    )


def template_summary(parent: ParentChunk) -> str:
    """Build deterministic retrieval text for structured table/CSV chunks."""

    tags = ", ".join(parent.asset_tags) if parent.asset_tags else "unknown equipment"
    row_range = ""
    if parent.row_start is not None and parent.row_end is not None:
        row_range = f" rows {parent.row_start}-{parent.row_end}"
    section = f" section {parent.section_title}" if parent.section_title else ""
    preview = " ".join(parent.raw_text.split())[:900]
    return (
        f"Structured work-order/table data for {tags} from {parent.source_file}"
        f"{row_range}{section}. Includes equipment IDs, work order descriptions, "
        f"order types, statuses, dates, maintenance actions, work centers, and "
        f"operational events. Raw row details: {preview}"
    )


def llm_summary_or_fallback(parent: ParentChunk) -> tuple[str, str]:
    """Return an LLM retrieval summary, falling back deterministically."""

    key = (settings.gemini_api_key or "").strip()
    if not key:
        return passthrough_summary(parent), "passthrough"

    try:
        from google import genai
    except ImportError:
        return passthrough_summary(parent), "passthrough"

    prompt = f"""
Create a retrieval-optimized summary for an industrial asset RAG index.
This summary is for search only, not final answer evidence.

Include when present:
- asset tags and equipment IDs
- procedure names and SOP/manual references
- limits, thresholds, dates, statuses, and compliance references
- failure modes, actions, checks, and maintenance activities
- likely synonyms users may search with

Source file: {parent.source_file}
Section: {parent.section_title or "unknown"}
Page range: {parent.page_start or ""}-{parent.page_end or ""}
Asset tags: {", ".join(parent.asset_tags) if parent.asset_tags else "none"}

Raw parent chunk:
{parent.raw_text[:7000]}
""".strip()
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=(settings.gemini_generation_model or SUMMARY_MODEL_FALLBACK).strip(),
            contents=prompt,
        )
        text = (getattr(response, "text", "") or "").strip()
        if text:
            return text, "llm"
    except Exception:
        return passthrough_summary(parent), "passthrough"
    return passthrough_summary(parent), "passthrough"


def passthrough_summary(parent: ParentChunk) -> str:
    """Deterministic fallback retrieval summary."""

    tags = ", ".join(parent.asset_tags) if parent.asset_tags else "no explicit asset tags"
    location_parts = []
    if parent.section_title:
        location_parts.append(f"section {parent.section_title}")
    if parent.page_start is not None:
        location_parts.append(f"pages {parent.page_start}-{parent.page_end or parent.page_start}")
    if parent.row_start is not None:
        location_parts.append(f"rows {parent.row_start}-{parent.row_end or parent.row_start}")
    location = ", ".join(location_parts) if location_parts else "source location unknown"
    preview = " ".join(parent.raw_text.split())[:1200]
    return (
        f"{parent.source_file} {location}. Asset tags: {tags}. "
        f"Retrieval text from raw parent chunk: {preview}"
    )
