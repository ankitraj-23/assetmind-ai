"""Atomic visual and parent summary generation for RAG retrieval."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import settings
from app.rag.schemas import (
    AtomicElementSummary,
    DocumentElement,
    ParentChunk,
    ParentChunkSummary,
    RetrievalUnit,
)
from app.services.entity_extraction import extract_equipment_tags

SUMMARY_MODEL_FALLBACK = "gemini-3.5-flash"
QUESTION_COUNT = 5


def summarize_atomic_elements(elements: list[DocumentElement]) -> list[DocumentElement]:
    """Attach summaries to visual atomic elements before parent chunking.

    CSV/Markdown/textual elements are left as-is. Visual summaries intentionally do not
    include generated questions; questions belong only to parent summary metadata.
    """

    summarized: list[DocumentElement] = []
    for element in elements:
        if not _needs_atomic_summary(element):
            summarized.append(element)
            continue
        summary = summarize_atomic_element(element)
        summarized.append(
            element.model_copy(
                update={
                    "element_summary": summary.summary_text,
                    "summary_strategy": summary.summary_strategy,
                    "asset_tags": sorted(set(element.asset_tags) | set(summary.asset_tags)),
                    "metadata": {
                        **element.metadata,
                        "atomic_summary": summary.model_dump(),
                    },
                }
            )
        )
    return summarized


def summarize_atomic_element(element: DocumentElement) -> AtomicElementSummary:
    """Summarize one visual element with model-first fallback behavior."""

    key = (settings.gemini_api_key or "").strip()
    if not key:
        return _fallback_atomic_summary(element, "vision_future")

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return _fallback_atomic_summary(element, "vision_future")

    prompt = f"""
Summarize this atomic visual element for an industrial RAG pipeline.
Do not generate questions. Do not invent facts.
Return concise plain text only.

Element type: {element.element_type}
Modality: {element.modality}
File: {element.file_name}
Page: {element.page_number or ""}
Row: {element.row_index or ""}
Known asset tags: {", ".join(element.asset_tags) if element.asset_tags else "none"}

Element text/caption/OCR representation:
{element.text[:5000]}
""".strip()

    try:
        client = genai.Client(api_key=key)
        contents: object = prompt
        image_part = _image_part_for_element(element, types)
        if image_part is not None:
            contents = [prompt, image_part]
        response = client.models.generate_content(
            model=(settings.gemini_generation_model or SUMMARY_MODEL_FALLBACK).strip(),
            contents=contents,
        )
        text = (getattr(response, "text", "") or "").strip()
        if text:
            return AtomicElementSummary(
                element_id=element.element_id,
                element_type=element.element_type,
                summary_text=text,
                summary_strategy="visual_llm",
                asset_tags=_merge_asset_tags(element.asset_tags, text),
                metadata={"questions_generated": False},
            )
    except Exception:
        return _fallback_atomic_summary(element, "vision_future")
    return _fallback_atomic_summary(element, "vision_future")


def build_parent_summary(parent: ParentChunk) -> ParentChunkSummary:
    """Generate parent-level retrieval summary with questions and asset tags."""

    key = (settings.gemini_api_key or "").strip()
    if not key:
        return _fallback_parent_summary(parent)

    try:
        from google import genai
    except ImportError:
        return _fallback_parent_summary(parent)

    prompt = f"""
Create a retrieval summary for one parent chunk in an industrial asset RAG system.

Important:
- Use text elements directly.
- Use visual atomic summaries instead of original visual elements.
- Return JSON only.
- Include asset_tags as a list, e.g. ["P-101", "P-102"].
- Include exactly {QUESTION_COUNT} questions that can be answered only from this parent chunk.
- Do not invent information not present in the supplied parent evidence.

JSON shape:
{{
  "summary_text": "...",
  "asset_tags": ["..."],
  "answerable_questions": ["...", "..."]
}}

Source file: {parent.source_file}
Section: {parent.section_title or "unknown"}
Page range: {parent.page_start or ""}-{parent.page_end or ""}
Row range: {parent.row_start or ""}-{parent.row_end or ""}
Existing asset tags: {", ".join(parent.asset_tags) if parent.asset_tags else "none"}

Parent evidence for summary:
{_parent_summary_input(parent)[:9000]}
""".strip()

    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=(settings.gemini_generation_model or SUMMARY_MODEL_FALLBACK).strip(),
            contents=prompt,
        )
        payload = _parse_json_response((getattr(response, "text", "") or "").strip())
        summary_text = str(payload.get("summary_text") or "").strip()
        questions = _clean_questions(payload.get("answerable_questions") or [])
        asset_tags = _normalize_asset_tags(payload.get("asset_tags") or [])
        if summary_text:
            return ParentChunkSummary(
                parent_chunk_id=parent.parent_chunk_id,
                summary_text=summary_text,
                answerable_questions=questions or _fallback_questions(parent),
                asset_tags=sorted(set(parent.asset_tags) | set(asset_tags)),
                summary_strategy="parent_llm",
                metadata={"questions_generated": True},
            )
    except Exception:
        return _fallback_parent_summary(parent)
    return _fallback_parent_summary(parent)


def build_retrieval_unit(parent: ParentChunk) -> RetrievalUnit:
    """Create one summary-indexed retrieval unit for a raw parent chunk."""

    parent_summary = parent.parent_summary or build_parent_summary(parent)
    return RetrievalUnit(
        retrieval_unit_id=f"{parent.parent_chunk_id}:summary:0",
        parent_chunk_id=parent.parent_chunk_id,
        document_id=parent.document_id,
        summary_text=parent_summary.summary_text,
        asset_tags=parent_summary.asset_tags,
        modality=parent.modality,
        source_file=parent.source_file,
        source_path=parent.source_path,
        source_type=parent.source_type,
        page_start=parent.page_start,
        page_end=parent.page_end,
        row_start=parent.row_start,
        row_end=parent.row_end,
        section_title=parent.section_title,
        answerable_questions=parent_summary.answerable_questions,
        summary_strategy=parent_summary.summary_strategy,
        metadata={
            "strategy_version": "parent_summary_v2",
            "parent_summary": parent_summary.model_dump(),
            "atomic_element_summaries": [
                summary.model_dump() for summary in parent.element_summaries
            ],
        },
    )


# Backward-compatible helper name used by earlier tests/docs.
def template_summary(parent: ParentChunk) -> str:
    return _fallback_parent_summary(parent).summary_text


def llm_summary_or_fallback(parent: ParentChunk) -> tuple[str, str]:
    summary = build_parent_summary(parent)
    return summary.summary_text, summary.summary_strategy


def passthrough_summary(parent: ParentChunk) -> str:
    return _fallback_parent_summary(parent).summary_text


def _needs_atomic_summary(element: DocumentElement) -> bool:
    if element.source_type in {"csv", "md"}:
        return False
    return (
        element.modality in {"image", "ocr", "table"}
        or element.element_type in {"table_row", "table_block", "image_caption", "ocr_text"}
    )


def _fallback_atomic_summary(
    element: DocumentElement,
    strategy: str,
) -> AtomicElementSummary:
    summary = (
        f"{element.element_type} element from {element.file_name}. "
        f"Asset tags: {', '.join(element.asset_tags) if element.asset_tags else 'none'}. "
        f"Content representation: {' '.join(element.text.split())[:1200]}"
    )
    return AtomicElementSummary(
        element_id=element.element_id,
        element_type=element.element_type,
        summary_text=summary,
        summary_strategy=strategy,
        asset_tags=_merge_asset_tags(element.asset_tags, element.text),
        metadata={"questions_generated": False},
    )


def _fallback_parent_summary(parent: ParentChunk) -> ParentChunkSummary:
    asset_tags = sorted(set(parent.asset_tags) | set(_merge_asset_tags([], parent.raw_text)))
    location_parts = []
    if parent.section_title:
        location_parts.append(f"section {parent.section_title}")
    if parent.page_start is not None:
        location_parts.append(f"pages {parent.page_start}-{parent.page_end or parent.page_start}")
    if parent.row_start is not None:
        location_parts.append(f"rows {parent.row_start}-{parent.row_end or parent.row_start}")
    location = ", ".join(location_parts) if location_parts else "source location unknown"
    summary = (
        f"{parent.source_file} {location}. Asset tags: "
        f"{', '.join(asset_tags) if asset_tags else 'none'}. "
        f"Parent evidence summary input: {_parent_summary_input(parent)[:1600]}"
    )
    return ParentChunkSummary(
        parent_chunk_id=parent.parent_chunk_id,
        summary_text=summary,
        answerable_questions=_fallback_questions(parent),
        asset_tags=asset_tags,
        summary_strategy="parent_passthrough",
        metadata={"questions_generated": False},
    )


def _parent_summary_input(parent: ParentChunk) -> str:
    text_evidence = str(parent.metadata.get("text_evidence") or parent.raw_text).strip()
    if not parent.element_summaries:
        return text_evidence
    lines = ["Text evidence:", text_evidence, "", "Atomic visual summaries:"]
    for summary in parent.element_summaries:
        lines.append(f"- {summary.element_type} {summary.element_id}: {summary.summary_text}")
    return "\n".join(lines)


def _fallback_questions(parent: ParentChunk) -> list[str]:
    tags = ", ".join(parent.asset_tags) if parent.asset_tags else "the referenced asset"
    source = parent.section_title or parent.source_file
    return [
        f"What information does {source} provide about {tags}?",
        f"Which checks, actions, or limits are stated for {tags} in this chunk?",
        f"What source evidence is available for {tags} in {parent.source_file}?",
        f"What status, date, or maintenance detail is mentioned for {tags}?",
        f"What operational or compliance issue can be answered from this chunk?",
    ][:QUESTION_COUNT]


def _merge_asset_tags(existing: list[str], text: str) -> list[str]:
    found = [tag.normalized_value for tag in extract_equipment_tags(text)]
    return sorted(set(existing) | set(found))


def _normalize_asset_tags(values: list[object]) -> list[str]:
    normalized: set[str] = set()
    for value in values:
        text = str(value).strip().upper()
        if text:
            normalized.add(text)
    return sorted(normalized)


def _clean_questions(values: list[object]) -> list[str]:
    questions: list[str] = []
    for value in values:
        question = str(value).strip()
        if question and question not in questions:
            questions.append(question)
    return questions[:QUESTION_COUNT]


def _parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def _image_part_for_element(element: DocumentElement, types: object) -> object | None:
    visual_path = str(element.metadata.get("visual_path") or "").strip()
    if not visual_path:
        return None
    path = Path(visual_path)
    if not path.exists() or not path.is_file():
        return None
    mime_type = str(element.metadata.get("mime_type") or "image/png")
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
