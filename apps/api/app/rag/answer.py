"""Grounded Gemini answer generation over retrieved RAG chunks."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.rag import citations
from app.rag.embeddings import MissingGeminiApiKeyError
from app.rag.retrieval import retrieve_relevant_chunks
from app.rag.schemas import RAGQueryResponse, RetrievedChunk

INSUFFICIENT_ANSWER = "I could not find enough evidence in the uploaded documents."
MIN_CONTEXT_SCORE = 0.15
MAX_VISUALS_PER_ANSWER = 8


def _gemini_available() -> bool:
    return bool((settings.gemini_api_key or "").strip())


def _api_key() -> str:
    key = (settings.gemini_api_key or "").strip()
    if not key:
        raise MissingGeminiApiKeyError(
            "GEMINI_API_KEY is not set. Set it before calling /rag/query."
        )
    return key


def _generation_model() -> str:
    return (settings.gemini_generation_model or "gemini-2.5-flash").strip()


def _client():
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is required for Gemini answer generation. "
            "Run 'pip install -r requirements.txt' from apps/api."
        ) from exc

    return genai.Client(api_key=_api_key())


def _confidence(chunks: list[RetrievedChunk]) -> float:
    if not chunks:
        return 0.0
    top_score = max(0.0, min(1.0, chunks[0].score))
    coverage_bonus = min(len(chunks), 5) * 0.03
    return round(min(1.0, top_score + coverage_bonus), 2)


def _context(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        location = f"page {chunk.page_start or chunk.page_number}" if (chunk.page_start or chunk.page_number) else ""
        if chunk.row_start or chunk.row_number:
            row_start = chunk.row_start or chunk.row_number
            row_end = chunk.row_end or row_start
            location = f"rows {row_start}-{row_end}" if row_end != row_start else f"row {row_start}"
        summary = chunk.retrieval_summary or ""
        raw_text = chunk.raw_text or chunk.content
        lines = [
            (
                f"[{index}] file={chunk.file_name} {location} "
                f"section={chunk.section_title or 'n/a'} "
                f"parent_chunk_id={chunk.parent_chunk_id or chunk.chunk_id}"
            ),
            f"Retrieval summary label (not evidence): {summary}",
            "Raw parent chunk evidence:",
            raw_text,
        ]
        if chunk.visual_elements:
            lines.extend(["Original visual element evidence:"])
            for element in chunk.visual_elements:
                metadata = dict(element.get("metadata") or {})
                lines.append(
                    (
                        f"- element_id={element.get('element_id')} "
                        f"type={element.get('element_type')} "
                        f"modality={element.get('modality')} "
                        f"page={element.get('page_number') or 'n/a'} "
                        f"bbox={element.get('bbox') or 'n/a'} "
                        f"visual_path={metadata.get('visual_path') or 'n/a'} "
                        f"text_or_reference={element.get('text') or ''}"
                    ).strip()
                )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _conversation_context(messages: list[dict[str, str]] | None) -> str:
    if not messages:
        return "No prior conversation context."
    lines: list[str] = []
    for message in messages:
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "No prior conversation context."


def _chunk_location(chunk: RetrievedChunk) -> str:
    page = chunk.page_start or chunk.page_number
    row = chunk.row_start or chunk.row_number
    if row:
        return f"row {row}"
    if page:
        return f"page {page}"
    return ""


def _fallback_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Deterministic, grounded answer used when Gemini is not configured.

    No LLM is available, so this faithfully reports the strongest retrieved
    evidence verbatim (with source markers) instead of synthesising prose. The
    evidence itself carries the factual content, and citations provide full
    provenance.
    """

    evidence_blocks: list[str] = []
    for index, chunk in enumerate(chunks[:3], start=1):
        raw_text = (chunk.raw_text or chunk.content or "").strip()
        if not raw_text:
            continue
        location = _chunk_location(chunk)
        header = f"[{index}] {chunk.file_name}" + (f" ({location})" if location else "")
        evidence_blocks.append(f"{header}\n{snippet_for_fallback(raw_text)}")

    if not evidence_blocks:
        return INSUFFICIENT_ANSWER

    return (
        "Based on the indexed documents, the most relevant evidence is "
        "(deterministic extraction — no LLM configured; see citations for full "
        "provenance):\n\n" + "\n\n".join(evidence_blocks)
    )


def snippet_for_fallback(text: str, limit: int = 600) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "..."


def _generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    standalone_question: str | None = None,
    conversation_messages: list[dict[str, str]] | None = None,
) -> str:
    standalone_block = (
        standalone_question.strip()
        if standalone_question and standalone_question.strip() != question.strip()
        else question.strip()
    )
    if not _gemini_available():
        return _fallback_answer(question, chunks)
    prompt = f"""
You answer questions for AssetMind AI using only the supplied document context.
If the context does not contain enough evidence, answer exactly:
{INSUFFICIENT_ANSWER}

Rules:
- Do not use outside knowledge.
- Use only "Raw parent chunk evidence" and "Original visual element evidence" as evidence.
- Retrieval summary labels are search hints only; do not cite them as evidence.
- Keep the answer concise and factual.
- Mention source numbers like [1] or [2] beside supported claims.
- Use recent conversation only to understand pronouns/follow-ups; factual claims must still come from the document context.

Recent conversation:
{_conversation_context(conversation_messages)}

Current user question:
{question}

Standalone retrieval question:
{standalone_block}

Context:
{_context(chunks)}
""".strip()
    client = _client()
    contents = _gemini_contents(prompt, chunks)
    response = client.models.generate_content(
        model=_generation_model(),
        contents=contents,
    )
    text = getattr(response, "text", "") or ""
    return text.strip() or INSUFFICIENT_ANSWER


def _gemini_contents(prompt: str, chunks: list[RetrievedChunk]) -> object:
    visual_parts = _visual_parts(chunks)
    if not visual_parts:
        return prompt

    contents: list[object] = [prompt]
    for label, image_part in visual_parts:
        contents.append(label)
        contents.append(image_part)
    return contents


def _visual_parts(chunks: list[RetrievedChunk]) -> list[tuple[str, object]]:
    try:
        from google.genai import types
    except ImportError:
        return []

    parts: list[tuple[str, object]] = []
    for chunk_index, chunk in enumerate(chunks, start=1):
        for element in chunk.visual_elements:
            if len(parts) >= MAX_VISUALS_PER_ANSWER:
                return parts
            metadata = dict(element.get("metadata") or {})
            visual_path = str(metadata.get("visual_path") or element.get("visual_path") or "").strip()
            if not visual_path:
                continue
            path = Path(visual_path)
            if not path.exists() or not path.is_file():
                continue
            mime_type = str(metadata.get("mime_type") or element.get("mime_type") or "image/png")
            label = (
                f"Image for source [{chunk_index}], visual element "
                f"{element.get('element_id') or 'unknown'} "
                f"from {chunk.file_name} page {element.get('page_number') or chunk.page_start or 'n/a'}."
            )
            parts.append(
                (
                    label,
                    types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type),
                )
            )
    return parts


def answer_with_chunks(
    question: str,
    retrieved: list[RetrievedChunk],
    *,
    standalone_question: str | None = None,
    conversation_messages: list[dict[str, str]] | None = None,
) -> RAGQueryResponse:
    if not retrieved or retrieved[0].score < MIN_CONTEXT_SCORE:
        return RAGQueryResponse(
            answer=INSUFFICIENT_ANSWER,
            citations=[],
            confidence=0.0,
            missing_info=["No sufficiently relevant chunks were retrieved."],
            retrieved_chunks=retrieved,
        )

    answer = _generate_answer(
        question,
        retrieved,
        standalone_question=standalone_question,
        conversation_messages=conversation_messages,
    )
    response_citations = citations.citations_from_chunks(retrieved)
    missing_info: list[str] = []
    if answer.strip() == INSUFFICIENT_ANSWER:
        response_citations = []
        missing_info.append("Gemini judged the retrieved context insufficient.")

    return RAGQueryResponse(
        answer=answer,
        citations=response_citations,
        confidence=_confidence(retrieved),
        missing_info=missing_info,
        retrieved_chunks=retrieved,
    )


def answer_question(question: str, top_k: int = 5) -> RAGQueryResponse:
    retrieved = retrieve_relevant_chunks(question, top_k=top_k)
    return answer_with_chunks(question, retrieved)
